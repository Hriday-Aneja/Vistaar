"""The simulated 30-day story (app/demo_story.py) must trip the real detectors. Pure: no DB, no web stack.

These feed the story's own numbers into the same pure functions the endpoints use (detect_spike, detect_drop,
assess, score_swap, solve). They do not call the endpoints; the DB-backed check is in test_api_flow.py.
"""
from datetime import date, timedelta
from math import ceil, floor

from app import demo_story as story
from app.services.backdate import MAX_BACKDATE_DAYS
from app.services.drop_stats import MIN_BASELINE_DAYS, RECENT_DAYS as DROP_RECENT, detect_drop
from app.services.expiry import assess
from app.services.geo import haversine_km
from app.services.pulse_stats import WINDOW_DAYS, detect_spike
from app.services.swap_scoring import SHORTAGE_COVER_DAYS, score_swap
from app.services.swap_solver import solve
from app.tuning import ML_MIN_HISTORY_DAYS, NEARBY_RADIUS_KM

TODAY = date(2026, 10, 28)
N_SHOPS = len(story.SHOP_NAMES)


def _oldest_first(by_days_ago: dict) -> list:
    return [by_days_ago[d] for d in sorted(by_days_ago, reverse=True)]


def test_history_is_daily_sales_up_to_today_and_repeatable():
    for shop in range(N_SHOPS):
        for name, *_ in story.PRODUCTS:
            sales = story.daily_sales(shop, name)
            assert sorted(sales) == list(range(story.HISTORY_DAYS))
            assert sales == story.daily_sales(shop, name)  # fixed seed: same numbers every run
    assert story.OPENING_DAYS_AGO >= story.HISTORY_DAYS  # stock arrives before the first sale


def test_there_is_enough_history_for_the_xgboost_forecast():
    # services/ml_forecast.py counts the days from the first sale up to YESTERDAY
    assert story.HISTORY_DAYS - 1 >= ML_MIN_HISTORY_DAYS


def test_every_product_ends_with_a_little_stock_and_never_sells_more_than_it_has():
    for shop in range(N_SHOPS):
        for name, *_ in story.PRODUCTS:
            left = story.opening_qty(shop, name) - sum(story.daily_sales(shop, name).values())
            assert left == story.leftover(shop, name) > 0


def test_all_backdated_days_are_inside_the_60_day_rule():
    assert story.HISTORY_DAYS - 1 <= MAX_BACKDATE_DAYS
    assert story.UDHAAR_DAYS_AGO <= MAX_BACKDATE_DAYS
    assert story.MILK_SENDER_RECEIVED_DAYS_AGO <= MAX_BACKDATE_DAYS


def test_the_spike_fires_at_exactly_the_four_spike_shops_and_nothing_else_spikes():
    spiking = set()
    for shop in range(N_SHOPS):
        for name, *_ in story.PRODUCTS:
            if detect_spike(_oldest_first(story.daily_sales(shop, name))):
                spiking.add((shop, name))
    assert spiking == {(shop, story.SPIKE_PRODUCT) for shop in story.SPIKE_SHOPS}
    assert len(story.SPIKE_SHOPS) >= 4


def test_the_sales_drop_fires_only_at_the_drop_shop_with_enough_data():
    for shop in range(N_SHOPS):
        totals = story.shop_totals(shop)
        # what sales_drop_for sees: the last WINDOW_DAYS days, and today is left out
        through_yesterday = [totals[d] for d in sorted(totals, reverse=True) if 1 <= d <= WINDOW_DAYS - 1]
        assert len(through_yesterday) >= DROP_RECENT + MIN_BASELINE_DAYS and len(through_yesterday) >= 17
        found = detect_drop(through_yesterday)
        assert (found is not None) == (shop == story.DROP_SHOP), shop


def test_the_milk_story_produces_a_swap_from_the_sender_to_the_neighbour():
    name, _cat, sell, cost = story.MILK
    expiry = TODAY + timedelta(days=story.MILK_EXPIRES_IN_DAYS)
    sender = assess(story.MILK_SENDER_QTY, 0.0, TODAY, expiry, TODAY - timedelta(days=story.MILK_SENDER_RECEIVED_DAYS_AGO))
    assert sender["level"] == "high" and sender["days_left"] >= 2 and sender["at_risk_qty"] > 0

    rate = round(sum(story.milk_receiver_sales().values()) / 14, 2)
    own = assess(story.MILK_RECEIVER_LEFT, rate, TODAY, TODAY + timedelta(days=story.MILK_RECEIVER_EXPIRES_IN_DAYS),
                 TODAY - timedelta(days=13))
    assert own["level"] not in ("high", "medium")  # the receiver's own batch must not look like supply

    cover = story.MILK_RECEIVER_LEFT / rate
    assert cover < SHORTAGE_COVER_DAYS
    need = ceil(rate * 7 - story.MILK_RECEIVER_LEFT)
    cap = min(sender["at_risk_qty"], need, floor(rate * sender["days_left"] - story.MILK_RECEIVER_LEFT))
    assert cap > 0
    km = haversine_km(28.6139 + story.MILK_SENDER * 0.002, 77.2090, 28.6139 + story.MILK_RECEIVER * 0.002, 77.2090)
    assert km <= NEARBY_RADIUS_KM
    score, _ = score_swap(km, NEARBY_RADIUS_KM, sender["days_left"], cover, cap / need, (sell - cost) / sell)
    assert solve({"b": sender["at_risk_qty"]}, {"s": need}, {("b", "s"): (score, cap)}) == [("b", "s", cap)]


def test_the_udhaar_credit_is_old_enough_for_a_khata_draft():
    assert story.UDHAAR_DAYS_AGO >= 7  # api/khata.py MIN_OVERDUE_DAYS
    assert story.UDHAAR_AMOUNT > 0


def test_story_state_tells_a_rerun_what_to_do():
    assert story.story_state(0, 100, 10) == "absent"
    assert story.story_state(100, 100, 10) == "fresh"
    assert story.story_state(10, 100, 10) == "done"
    assert story.story_state(55, 100, 10) == "changed"