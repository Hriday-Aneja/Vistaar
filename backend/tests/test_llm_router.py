from app.services.llm import LLMRouter


def boom(_):
    raise RuntimeError("down")


def test_falls_back_in_order():
    assert LLMRouter([("a", boom), ("b", lambda p: "from b")], lambda p: "offline").complete("hi") == ("b", "from b")


def test_offline_when_all_fail():
    assert LLMRouter([("a", boom)], lambda p: "offline").complete("hi") == ("offline", "offline")
