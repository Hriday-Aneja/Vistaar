"""XGBoost + SHAP forecast for the bulk plan: determinism, reasons, every fallback, and the order-quantity bounds.

The unit tests use their own in-memory SQLite database and a fixed date, so they need no network and no seed.
"""
import random
from datetime import date, datetime, time, timedelta
from math import ceil

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from app import tuning
from app.db import models as m
from app.db.session import Base
from app.services import bulk, ml_forecast
from app.services.inventory import daily_rate

needs_ml_libs = pytest.mark.skipif(ml_forecast.np is None, reason="xgboost/shap/numpy not installed")
TODAY = date(2026, 11, 10)  # a Tuesday; fixed so the tests never depend on the real date
HORIZON = tuning.BULK_HORIZON_DAYS


@pytest.fixture
def ml_on(monkeypatch):
    if ml_forecast.np is None:
        pytest.skip("xgboost/shap/numpy not installed")
    monkeypatch.setattr(tuning, "ML_FORECAST_ENABLED", True)
    ml_forecast.clear_cache()
    yield
    ml_forecast.clear_cache()


def make_db(history_days: int = 60, festival: bool = True):
    """One real shop, a sweet that sells more on weekends and during Diwali, and a flat staple."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = Session(engine)
    shop = m.Shop(name="Test Kirana", owner_name="Asha", area="Rohini", lat=28.7, lng=77.1, upi_vpa="a@upi")
    sweet = m.Product(name="Mithai Box", category="Sweets", default_shelf_days=30, mrp=100)
    atta = m.Product(name="Atta 5kg", category="Staples", default_shelf_days=90, mrp=250)
    db.add_all([shop, sweet, atta])
    db.flush()
    if festival:
        for start, end in ((-30, -27), (12, 14)):  # one Diwali window in the history, one coming up
            db.add(m.EventCalendar(kind="festival", label="Diwali", start_date=TODAY + timedelta(days=start),
                                   end_date=TODAY + timedelta(days=end), categories=["Sweets"],
                                   suggested_action="stock up", is_demo=False))
    rng = random.Random(7)
    for back in range(history_days, 0, -1):
        day = TODAY - timedelta(days=back)
        sweet_qty = 10 * (1.8 if day.weekday() >= 5 else 1.0) * (3.0 if festival and 27 <= back <= 30 else 1.0)
        for product, qty in ((sweet, sweet_qty), (atta, 8)):
            db.add(m.Sale(shop_id=shop.id, product_id=product.id, qty=max(1, round(rng.gauss(qty, 0.5))),
                          amount=0, sold_at=datetime.combine(day, time(12))))
    db.commit()
    return db, shop, sweet, atta


@needs_ml_libs
def test_forecast_is_deterministic_and_sane(ml_on):
    db, shop, sweet, atta = make_db()
    first = ml_forecast.forecast_units(db, shop.id, TODAY, HORIZON)
    ml_forecast.clear_cache()
    second = ml_forecast.forecast_units(db, shop.id, TODAY, HORIZON)
    assert first is not None and first == second  # fixed seed, single thread, no subsampling
    assert abs(first[atta.id] - 8 * HORIZON) < 0.15 * 8 * HORIZON  # a flat product stays near its average
    assert first[sweet.id] > first[atta.id]  # weekends and Diwali lift the sweet


@needs_ml_libs
def test_shap_reason_names_the_festival_and_the_weekend(ml_on):
    db, shop, sweet, atta = make_db()
    reason = ml_forecast.explain_reason(db, shop.id, sweet.id, TODAY, HORIZON)
    assert reason is not None
    assert "Diwali 12 din me: +" in reason  # festival is the top factor, with its sign and percentage
    assert len(reason.split(", ")) <= 2
    flat = ml_forecast.explain_reason(db, shop.id, atta.id, TODAY, HORIZON)
    assert "Diwali" not in flat and "yohaar" not in flat  # no festival touches Staples, so none is blamed


@needs_ml_libs
def test_ml_forecast_is_cached_per_shop_and_data(ml_on, monkeypatch):
    db, shop, sweet, _ = make_db()
    calls = []
    real = ml_forecast._train
    monkeypatch.setattr(ml_forecast, "_train", lambda x, y: calls.append(1) or real(x, y))
    ml_forecast.forecast_units(db, shop.id, TODAY, HORIZON)
    ml_forecast.explain_reason(db, shop.id, sweet.id, TODAY, HORIZON)
    ml_forecast.forecast_units(db, shop.id, TODAY, HORIZON)
    assert len(calls) == 1
    db.add(m.Sale(shop_id=shop.id, product_id=sweet.id, qty=5, amount=0,
                  sold_at=datetime.combine(TODAY - timedelta(days=1), time(18))))
    db.commit()
    ml_forecast.forecast_units(db, shop.id, TODAY, HORIZON)  # new sale -> new fingerprint -> retrain
    assert len(calls) == 2


def _rule_needs(db, shop, mult):
    return {p.id: ceil(daily_rate(db, shop.id, p.id, TODAY) * HORIZON * mult)
            for p in db.query(m.Product) if daily_rate(db, shop.id, p.id, TODAY) > 0}


def test_short_history_uses_the_rule_based_path(ml_on):
    db, shop, *_ = make_db(history_days=20, festival=False)  # fewer than 30 days
    assert ml_forecast.forecast_units(db, shop.id, TODAY, HORIZON) is None
    needs, method = bulk.shop_needs_with_method(db, shop.id, TODAY, 1.3)
    assert method == "rule-based" and needs == _rule_needs(db, shop, 1.3)
    assert bulk.shop_needs(db, shop.id, TODAY, 1.3) == needs  # the old entry point is unchanged


@needs_ml_libs
def test_thirty_days_is_enough(ml_on):
    db, shop, *_ = make_db(history_days=31, festival=False)  # 30 complete days before today
    assert bulk.shop_needs_with_method(db, shop.id, TODAY, 1.3)[1] == "xgboost+shap"


def test_training_error_falls_back_without_raising(ml_on, monkeypatch):
    db, shop, sweet, _ = make_db()

    def boom(*_):
        raise RuntimeError("training blew up")

    monkeypatch.setattr(ml_forecast, "_train", boom)
    needs, method = bulk.shop_needs_with_method(db, shop.id, TODAY, 1.3)
    assert method == "rule-based" and needs == _rule_needs(db, shop, 1.3)
    assert ml_forecast.explain_reason(db, shop.id, sweet.id, TODAY, HORIZON) is None


@needs_ml_libs
def test_prediction_or_shap_error_falls_back(ml_on, monkeypatch):
    db, shop, sweet, _ = make_db()
    assert ml_forecast.forecast_units(db, shop.id, TODAY, HORIZON) is not None
    monkeypatch.setattr(ml_forecast.shap, "TreeExplainer", lambda *_: (_ for _ in ()).throw(ValueError("shap")))
    assert ml_forecast.explain_reason(db, shop.id, sweet.id, TODAY, HORIZON) is None  # caller keeps the rule reason

    ml_forecast.clear_cache()

    class BrokenModel:
        def fit(self, *_):
            return self

        def predict(self, *_):
            raise RuntimeError("predict failed")

    monkeypatch.setattr(ml_forecast, "_train", lambda x, y: BrokenModel())
    assert ml_forecast.forecast_units(db, shop.id, TODAY, HORIZON) is None


def test_missing_libraries_fall_back(ml_on, monkeypatch):
    db, shop, *_ = make_db()
    for name in ("xgb", "shap"):
        monkeypatch.setattr(ml_forecast, name, None)
        assert ml_forecast.forecast_units(db, shop.id, TODAY, HORIZON) is None
        assert bulk.shop_needs_with_method(db, shop.id, TODAY, 1.3)[1] == "rule-based"
        monkeypatch.undo()
        monkeypatch.setattr(tuning, "ML_FORECAST_ENABLED", True)


def test_switch_off_means_rule_based(monkeypatch):
    db, shop, *_ = make_db()
    monkeypatch.setattr(tuning, "ML_FORECAST_ENABLED", False)
    assert bulk.shop_needs_with_method(db, shop.id, TODAY, 1.3)[1] == "rule-based"


def test_model_only_suggests_the_order_is_bounded_by_stock_and_the_band(monkeypatch):
    db, shop, sweet, atta = make_db(festival=False)
    plain = {p.id: daily_rate(db, shop.id, p.id, TODAY) * HORIZON for p in (sweet, atta)}
    db.add(m.Batch(shop_id=shop.id, product_id=sweet.id, qty_received=60, qty_left=60, cost_price=80,
                   sell_price=100, received_on=TODAY))
    db.commit()

    def suggest(units):
        monkeypatch.setattr(ml_forecast, "forecast_units", lambda *_: dict.fromkeys((sweet.id, atta.id), units))
        return bulk.shop_needs_with_method(db, shop.id, TODAY, 1.3)

    needs, method = suggest(1e6)  # a runaway model is clamped to the band, then stock is subtracted
    assert method == "xgboost+shap"
    assert needs[sweet.id] == ceil(tuning.ML_MAX_RATIO * plain[sweet.id] - 60)
    assert needs[atta.id] == ceil(tuning.ML_MAX_RATIO * plain[atta.id])
    needs, _ = suggest(0.0)  # a model that says "sell nothing" cannot zero out a real need
    assert needs[atta.id] == ceil(tuning.ML_MIN_RATIO * plain[atta.id])
    assert sweet.id not in needs or needs[sweet.id] == ceil(tuning.ML_MIN_RATIO * plain[sweet.id] - 60)


# ---- API level: /api/orders/plan with the seeded demo data ----

@pytest.fixture(scope="module")
def client():
    pytest.importorskip("langgraph")
    from fastapi.testclient import TestClient

    from app import seed
    from app.main import app

    seed.build()
    with TestClient(app) as c:
        yield c


def _login(client, phone="9000000001"):
    r = client.post("/api/auth/login", json={"phone": phone, "password": "vistaar123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


@needs_ml_libs
def test_plan_reports_xgboost_and_still_needs_approval(client, ml_on):
    h = _login(client)
    plan = client.post("/api/orders/plan", headers=h).json()
    assert plan["forecast_method"] == "xgboost+shap" and plan["forecast_engine"] == "xgboost+shap"
    assert plan["status"] == "awaiting_approval" and plan["cohort_size"] >= 5
    mine = [ln for ln in plan["lines"] if ln["my_qty"] > 0]
    assert mine and all(ln["reason"] for ln in mine)
    done = client.post(f"/api/orders/{plan['thread_id']}/approve", headers=h).json()
    assert done["status"] == "ordered" and done["order_ids"]


def test_plan_never_breaks_when_ml_fails(client, ml_on, monkeypatch):
    def boom(*_):
        raise RuntimeError("model exploded")

    monkeypatch.setattr(ml_forecast, "_train", boom)
    r = client.post("/api/orders/plan", headers=_login(client))
    assert r.status_code == 200
    plan = r.json()
    assert plan["forecast_engine"] == "rule-based" and plan["forecast_method"].startswith("rule-based")
    mine = [ln for ln in plan["lines"] if ln["my_qty"] > 0]
    assert mine and all("aur chahiye" in ln["reason"] for ln in mine)
