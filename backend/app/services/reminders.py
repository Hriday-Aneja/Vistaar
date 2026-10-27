"""Khata reminder drafts: the wording comes from the LLM router when it answers, else from the fixed template.

Reminders are only ever *drafted* here. A merchant must press send (api/khata.py).

What the LLM sees: the shop's own name, the customer's first name, the amount owed and whether it is long overdue.
Never a phone number, a UPI id or link (only the placeholder [UPI_LINK], replaced afterwards), and never another
shop's data. What the LLM may decide: only the wording. The amount and link are ours, and a draft is used only if
it passes validate_reminder(): the amount is the only number in it, the customer's name is in it, the placeholder is
in it once, and it has no other link. Otherwise the template is used.
"""
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait as wait_futures
from dataclasses import dataclass

from app import tuning

log = logging.getLogger(__name__)

PLACEHOLDER = "[UPI_LINK]"
MAX_LLM_DRAFTS = 10  # per request; the rest use the template
MAX_MESSAGE_CHARS = 280
_CACHE_TTL_S = 600.0
_FAILED_TTL_S = 60.0
_DIGITS = re.compile(r"\d[\d,]*")


def draft_message(shop_name: str, customer_name: str, pending: float, overdue_days: int, upi_link: str) -> str:
    first = customer_name.split(" ")[0]
    if overdue_days >= 30:
        ask = f"Rs {pending:.0f} kaafi din se baaki hai. Jab suvidha ho, neeche link se de dijiye."
    else:
        ask = f"Rs {pending:.0f} baaki hai. Jab suvidha ho, neeche link se de dijiye."
    return f"Namaste {first} ji, {shop_name} se. {ask}\n{upi_link}\nDhanyavaad!"


@dataclass(frozen=True)
class ReminderJob:
    shop_id: int
    customer_id: int
    shop_name: str
    customer_name: str
    pending: float
    overdue_days: int
    upi_link: str  # only used to fill the placeholder afterwards, never put in a prompt


def _first(name: str) -> str:
    return name.split(" ")[0]


def build_reminder_prompt(job: ReminderJob) -> str:
    tone = "gentle, it has been a long time" if job.overdue_days >= 30 else "gentle"
    return (
        "Write a WhatsApp payment reminder in polite Hinglish (Hindi in Roman letters), 1 or 2 short sentences.\n"
        f"Use exactly these facts: customer first name: {_first(job.customer_name)}; shop: {job.shop_name}; "
        f"amount due: Rs {job.pending:.0f}; the payment link must appear as the literal text {PLACEHOLDER}.\n"
        f"Tone: {tone}. No threats.\n"
        "Do not write any other number, date, phone number or link. Output only the message text."
    )


def validate_reminder(text: str, customer_name: str, pending: float) -> str | None:
    """The cleaned message (still holding the placeholder), or None if it breaks any rule."""
    message = text.strip().strip('"').strip()
    amount = f"{pending:.0f}"
    if not message or len(message) > MAX_MESSAGE_CHARS or message.count(PLACEHOLDER) != 1:
        return None
    rest = message.replace(PLACEHOLDER, " ")
    lowered = rest.lower()
    if "http" in lowered or "upi:" in lowered or "@" in rest or _first(customer_name).lower() not in lowered:
        return None
    numbers = [n.replace(",", "") for n in _DIGITS.findall(rest)]
    if not numbers or any(n != amount for n in numbers):  # the amount must be there, and nothing else numeric
        return None
    return message


_cache: dict[tuple, tuple[float, tuple[str, str] | None]] = {}
_cache_lock = threading.Lock()
_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="khata-llm")


def _key(job: ReminderJob) -> tuple:
    return (job.shop_id, job.customer_id, f"{job.pending:.0f}", job.overdue_days >= 30)


def _generate(router, job: ReminderJob) -> tuple[str, str] | None:
    """(provider, message with placeholder) or None. Runs in a worker thread and touches no DB session."""
    try:
        provider, raw = router.complete_within(build_reminder_prompt(job))
    except Exception as exc:  # noqa: BLE001 - any LLM failure means the template
        log.warning("khata reminder: LLM failed (%s), using the template", type(exc).__name__)
        return None
    if provider == "offline":
        return None
    message = validate_reminder(raw, job.customer_name, job.pending)
    if message is None:
        log.warning("khata reminder: %s gave a draft that failed validation, using the template", provider)
        return None
    log.info("khata reminder for customer %s worded by %s", job.customer_id, provider)
    return provider, message


def draft_messages_llm(router, jobs: list[ReminderJob]) -> dict[int, tuple[str, str]]:
    """customer_id -> (provider, finished message). Customers not in the result get the template. Answers are cached
    for a few minutes so reloading the page does not call the LLM again, and the whole batch waits at most about
    one LLM timeout."""
    now = time.monotonic()
    found: dict[int, tuple[str, str]] = {}
    pending_jobs: list[ReminderJob] = []
    with _cache_lock:
        for job in jobs[:MAX_LLM_DRAFTS]:
            hit = _cache.get(_key(job))
            if hit is not None and hit[0] > now:
                if hit[1] is not None:
                    found[job.customer_id] = (hit[1][0], hit[1][1].replace(PLACEHOLDER, job.upi_link))
            else:
                pending_jobs.append(job)
    futures = {_pool.submit(_generate, router, job): job for job in pending_jobs}
    done, _ = wait_futures(futures, timeout=tuning.LLM_TIMEOUT_S + 1)
    with _cache_lock:
        if len(_cache) > 1000:
            _cache.clear()
        for future in done:
            job = futures[future]
            result = future.result()
            _cache[_key(job)] = (now + (_CACHE_TTL_S if result else _FAILED_TTL_S), result)
            if result is not None:
                found[job.customer_id] = (result[0], result[1].replace(PLACEHOLDER, job.upi_link))
    return found


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()
