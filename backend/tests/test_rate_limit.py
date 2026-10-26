from app.services.rate_limit import SlidingWindowLimiter


def test_allows_below_limit_and_blocks_at_limit():
    lim = SlidingWindowLimiter(limit=3, window_s=100)
    for t in (0, 1, 2):
        assert lim.retry_after("a", now=t) == 0
        lim.add("a", now=t)
    assert lim.retry_after("a", now=3) == 97  # the oldest hit (t=0) leaves the window at t=100


def test_unblocks_after_the_window():
    lim = SlidingWindowLimiter(limit=2, window_s=10)
    lim.add("a", now=0)
    lim.add("a", now=1)
    assert lim.retry_after("a", now=5) == 5   # first hit (t=0) leaves the window at t=10
    assert lim.retry_after("a", now=9) == 1
    assert lim.retry_after("a", now=10) == 0  # one hit left in the window, below the limit of 2


def test_keys_are_independent_and_clear_resets():
    lim = SlidingWindowLimiter(limit=1, window_s=100)
    lim.add("a", now=0)
    assert lim.retry_after("a", now=1) > 0
    assert lim.retry_after("b", now=1) == 0
    lim.clear("a")
    assert lim.retry_after("a", now=1) == 0


def test_memory_stays_bounded():
    lim = SlidingWindowLimiter(limit=1, window_s=10, max_keys=5)
    for i in range(50):
        lim.add(f"k{i}", now=i * 100)  # every earlier key has expired by the time the next arrives
    assert len(lim._hits) <= 6