"""LLM router in chat intent and khata reminder drafts: valid, invalid, error and offline answers are all mocked.

No network and no API keys: providers are plain functions.
"""
import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("langgraph")

from app.services import chat_intent, reminders
from app.services.llm import LLMRouter


def router(fn, name="gemini"):
    return LLMRouter([(name, fn)], lambda p: "offline text")


def boom(_):
    raise RuntimeError("provider down")


# ---- chat intent: pure logic ----

@pytest.mark.parametrize("text,intent", [
    ("Rahul bhai ko udhaar du?", "udhaar_check"), ("khata check", "udhaar_check"),
    ("Kaunsa maal expire hoga?", "swap"), ("swap karna hai", "swap"),
    ("Diwali ka maal plan karo", "plan_order"), ("stock kitna chahiye", "plan_order"),  # "stock" was always plan_order
    ("Bikri kaisi chal rahi hai?", "pulse"), ("sales gir gayi", "pulse"),
    ("namaste", "unknown"), ("", "unknown"),
])
def test_keyword_routing_is_the_old_chat_page_logic(text, intent):
    assert chat_intent.keyword_intent(text) == intent


def test_valid_llm_answer_is_used():
    r = router(lambda p: '{"intent": "price_check", "entities": {"customer_name": null, "product": "Atta"}}')
    assert chat_intent.detect_intent(r, "atta ka rate?") == {
        "intent": "price_check", "entities": {"product": "Atta"}, "source": "gemini"}


def test_fenced_json_is_accepted():
    r = router(lambda p: '```json\n{"intent": "stock", "entities": {}}\n```')
    assert chat_intent.detect_intent(r, "kya bacha hai")["intent"] == "stock"


@pytest.mark.parametrize("bad", [
    "not json at all",
    '{"intent": "plan_order"}',  # entities missing
    '{"intent": "delete_everything", "entities": {}}',  # not in the fixed list
    '{"intent": "swap", "entities": {}, "price": 5}',  # extra key
    '{"intent": "swap", "entities": {"discount": "50"}}',  # unknown entity
    '{"intent": "swap", "entities": {"product": 5}}',  # wrong type
    '{"intent": "swap", "entities": {"product": "' + "x" * 80 + '"}}',  # too long
    '{"intent": ["swap"], "entities": {}}',
    '["swap"]',
    "Sure! " + '{"intent": "swap", "entities": {}}',
])
def test_invalid_llm_answers_fall_back_to_keywords(bad):
    out = chat_intent.detect_intent(router(lambda p: bad), "Kaunsa maal expire hoga?")
    assert out == {"intent": "swap", "entities": {}, "source": "keyword"}


def test_llm_error_and_offline_fall_back_to_keywords():
    assert chat_intent.detect_intent(router(boom), "udhaar?")["source"] == "keyword"
    assert chat_intent.detect_intent(LLMRouter([], lambda p: '{"intent": "stock", "entities": {}}'), "udhaar?") == {
        "intent": "udhaar_check", "entities": {}, "source": "keyword"}  # no API key: offline text is never trusted


def test_slow_llm_times_out_and_keywords_answer(monkeypatch):
    import time

    monkeypatch.setattr("app.tuning.LLM_TIMEOUT_S", 0.2)
    out = chat_intent.detect_intent(router(lambda p: time.sleep(1.5) or '{"intent": "stock", "entities": {}}'),
                                    "bikri?")
    assert out["source"] == "keyword" and out["intent"] == "pulse"


def test_phone_numbers_never_reach_the_llm():
    seen = []
    r = router(lambda p: seen.append(p) or '{"intent": "udhaar_check", "entities": {}}')
    chat_intent.detect_intent(r, "9810011111 ko udhaar du? ya +91 98100 22222")
    assert "9810011111" not in seen[0] and "98100" not in seen[0] and "[number]" in seen[0]


# ---- khata reminder wording: pure logic ----

JOB = reminders.ReminderJob(1, 7, "Sharma Kirana", "Rahul Verma", 850.0, 25, "upi://pay?pa=a@upi&am=850.00")


def test_valid_reminder_gets_the_real_link():
    ok = "Namaste Rahul ji, Sharma Kirana se Rs 850 baaki hai. Kripya yahan se de dijiye: [UPI_LINK]"
    reminders.clear_cache()
    out = reminders.draft_messages_llm(router(lambda p: ok), [JOB])
    assert out[7] == ("gemini", ok.replace("[UPI_LINK]", JOB.upi_link))


@pytest.mark.parametrize("bad", [
    "Namaste Rahul ji, Rs 900 baaki hai [UPI_LINK]",  # wrong amount
    "Namaste Rahul ji, Rs 850 baaki hai, 5 din se. [UPI_LINK]",  # extra number
    "Namaste Rahul ji, Rs 850 baaki hai.",  # no placeholder
    "Namaste Rahul ji, Rs 850 [UPI_LINK] [UPI_LINK]",  # placeholder twice
    "Namaste Rahul ji, Rs 850 https://pay.example.com [UPI_LINK]",  # own link
    "Namaste ji, Rs 850 baaki hai [UPI_LINK]",  # customer name missing
    "Namaste Rahul ji, Rs 850, call 9810011111 [UPI_LINK]",  # phone number
    "Rahul " + "x" * 300 + " Rs 850 [UPI_LINK]",  # too long
])
def test_bad_reminders_are_rejected(bad):
    reminders.clear_cache()
    assert reminders.draft_messages_llm(router(lambda p: bad), [JOB]) == {}


def test_reminder_prompt_has_no_phone_or_link():
    seen = []
    reminders.clear_cache()
    reminders.draft_messages_llm(router(lambda p: seen.append(p) or "x"), [JOB])
    assert "Rahul" in seen[0] and "850" in seen[0] and "[UPI_LINK]" in seen[0]
    assert "upi://" not in seen[0] and "a@upi" not in seen[0] and "Verma" not in seen[0]


# ---- API ----

@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app import seed
    from app.main import app

    seed.build()
    with TestClient(app) as c:
        yield c


def _auth(client, phone="9000000001"):
    r = client.post("/api/auth/login", json={"phone": phone, "password": "vistaar123"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_intent_endpoint_needs_login_and_validates_input(client):
    assert client.post("/api/chat/intent", json={"text": "hi"}).status_code == 401
    assert client.post("/api/chat/intent", json={"text": ""}, headers=_auth(client)).status_code == 422


def test_intent_endpoint_without_api_keys_uses_keywords(client):
    r = client.post("/api/chat/intent", json={"text": "Diwali ka maal plan karo"}, headers=_auth(client))
    assert r.json() == {"intent": "plan_order", "entities": {}, "source": "keyword"}


def test_intent_endpoint_valid_invalid_and_error(client, monkeypatch):
    h = _auth(client)
    ask = lambda t: client.post("/api/chat/intent", json={"text": t}, headers=h).json()
    monkeypatch.setattr("app.api.chat.get_router", lambda: router(
        lambda p: '{"intent": "udhaar_check", "entities": {"customer_name": "Rahul"}}'))
    assert ask("Rahul ka hisaab?") == {"intent": "udhaar_check", "entities": {"customer_name": "Rahul"},
                                       "source": "gemini"}
    monkeypatch.setattr("app.api.chat.get_router", lambda: router(lambda p: "{{{"))
    assert ask("Bikri kaisi hai") == {"intent": "pulse", "entities": {}, "source": "keyword"}
    monkeypatch.setattr("app.api.chat.get_router", lambda: router(boom))
    assert ask("expire hone wala maal") == {"intent": "swap", "entities": {}, "source": "keyword"}


def test_intent_rate_limit_switches_to_keywords_not_errors(client, monkeypatch):
    from app.api import chat

    monkeypatch.setattr(chat, "_limiter", chat.SlidingWindowLimiter(limit=1, window_s=60))
    monkeypatch.setattr(chat, "get_router", lambda: router(lambda p: '{"intent": "stock", "entities": {}}'))
    h = _auth(client, "9000000002")
    first = client.post("/api/chat/intent", json={"text": "bikri"}, headers=h).json()
    second = client.post("/api/chat/intent", json={"text": "bikri"}, headers=h).json()
    assert first["source"] == "gemini" and second == {"intent": "pulse", "entities": {}, "source": "keyword"}


def _drafts(client):
    return client.get("/api/khata/drafts", headers=_auth(client)).json()


def test_khata_drafts_use_the_template_when_offline(client):
    reminders.clear_cache()
    drafts = _drafts(client)
    assert drafts and all(d["message_source"] == "template" for d in drafts)
    assert all("Dhanyavaad" in d["message"] and d["upi_link"] in d["message"] for d in drafts)  # the old template


def test_khata_drafts_are_worded_by_the_llm_with_the_real_amount_and_link(client, monkeypatch):
    prompts = []

    def fake(prompt):
        prompts.append(prompt)
        first = prompt.split("customer first name: ")[1].split(";")[0]
        amount = prompt.split("amount due: Rs ")[1].split(";")[0]
        return f"Namaste {first} ji, Rs {amount} baaki hai. Yahan se de dijiye: [UPI_LINK]"

    reminders.clear_cache()
    monkeypatch.setattr("app.api.khata.get_router", lambda: router(fake, "groq"))
    drafts = _drafts(client)
    assert drafts and all(d["message_source"] == "groq" for d in drafts)
    for d in drafts:
        assert d["upi_link"] in d["message"] and f"Rs {d['pending']:.0f}" in d["message"]
        assert "[UPI_LINK]" not in d["message"]
    from sqlalchemy import select

    from app.db.models import Customer
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        phones = [c.phone for c in db.scalars(select(Customer))]
    assert prompts and not any(ph in p for p in prompts for ph in phones)  # no customer phone numbers
    assert not any("upi://" in p for p in prompts)


def test_khata_drafts_fall_back_when_the_llm_errors_or_lies(client, monkeypatch):
    for fn in (boom, lambda p: "Namaste, Rs 1 baaki hai [UPI_LINK]"):
        reminders.clear_cache()
        monkeypatch.setattr("app.api.khata.get_router", lambda fn=fn: router(fn))
        drafts = _drafts(client)
        assert drafts and all(d["message_source"] == "template" and "Dhanyavaad" in d["message"] for d in drafts)


def test_drafting_sends_nothing_and_send_still_needs_the_merchant(client, monkeypatch):
    from sqlalchemy import func, select

    from app.db.models import KhataReminder
    from app.db.session import SessionLocal

    def count():
        with SessionLocal() as db:
            return db.scalar(select(func.count(KhataReminder.id)))

    reminders.clear_cache()
    monkeypatch.setattr("app.api.khata.get_router", lambda: router(
        lambda p: "Namaste ji [UPI_LINK]"))
    before = count()
    d = _drafts(client)[0]
    assert count() == before  # a draft is not a sent reminder
    r = client.post("/api/khata/send", json={"customer_id": d["customer_id"], "message": d["message"]},
                    headers=_auth(client))
    assert r.status_code == 201 and r.json()["status"] == "sent (simulated)" and count() == before + 1


def test_router_logs_the_provider_and_hides_api_keys(caplog):
    import logging

    def leaky(_):
        raise RuntimeError("https://x/?key=SECRET")

    with caplog.at_level(logging.INFO, logger="app.services.llm"):
        LLMRouter([("a", leaky), ("b", lambda p: "ok")], lambda p: "off").complete("hi")
    text = caplog.text
    assert "answered via b" in text and "provider a failed (RuntimeError)" in text and "SECRET" not in text
    json.dumps(text)
