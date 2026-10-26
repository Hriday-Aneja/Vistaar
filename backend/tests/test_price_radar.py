from app.services.price_radar import benchmark, flag_quote, run_reverse_auction


def test_benchmark_needs_enough_samples():
    assert benchmark([100, 101, 99]) is None
    assert benchmark([100, 101, 99, 98, 102]) == 100


def test_flags_only_inflated_quotes():
    assert flag_quote(100, 100) is None
    f = flag_quote(120, 100)
    assert f["level"] == "inflated" and f["pct_over"] == 20.0
    assert flag_quote(120, None) is None  # no benchmark, no claim


def test_reverse_auction_lowers_prices_but_respects_floors():
    final, events = run_reverse_auction({"a": 100, "b": 98, "c": 105}, {"a": 90, "b": 96, "c": 99})
    assert final["a"] < 100 and final["c"] < 105
    assert all(final[k] >= f for k, f in {"a": 90, "b": 96, "c": 99}.items())
    assert min(final.values()) < 98 and events


def test_auction_terminates_when_floors_block():
    final, events = run_reverse_auction({"a": 100, "b": 100}, {"a": 100, "b": 100})
    assert final == {"a": 100, "b": 100} and events == []
