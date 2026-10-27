"""XGBoost demand forecast with SHAP reasons for the bulk plan.

The model only *suggests* a horizon demand. services/bulk.shop_needs still subtracts stock on hand, keeps only
need > 0 and clamps the suggestion to a band around the rule-based number, so a bad model cannot inflate an order.
Anything that goes wrong (under 30 days of history, xgboost/shap missing, a training or prediction error) makes
the public functions return None and the caller uses the rule-based path. This module never raises to its callers.

Model: one small regressor per shop, trained on all of that shop's products. Each product's sales are divided by
its own average daily sales, so the model learns "how much above or below normal" and SHAP contributions read as
percentages. Features: day-of-week, rolling 7/14-day mean, lag-7, days to the next festival, festival flag.
Festivals come from EventCalendar rows with kind "festival" (same demo/real world as the shop) whose categories
include the product's category. Today is left out of training because the owner may not have entered it yet.
"""
from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import tuning
from app.db.models import EventCalendar, Product, Sale, Shop

log = logging.getLogger(__name__)

ML_METHOD = "xgboost+shap"

try:  # optional: any failure here (missing package, missing libgomp) just means rule-based forecasting
    import numpy as np
    import shap
    import xgboost as xgb
except Exception:  # noqa: BLE001
    np = shap = xgb = None

FEATURES = ("dow", "roll7", "roll14", "lag7", "days_to_festival", "festival_flag")
_DOW, _ROLL7, _ROLL14, _LAG7, _DTF, _FLAG = range(6)
FESTIVAL_CAP_DAYS = 60  # "no festival soon" is encoded as this many days
MAX_TRAIN_DAYS = 120
MIN_REASON_PCT = 5.0  # factors that move the forecast by less than this are not worth mentioning
_CACHE_MAX = 128


@dataclass
class _Entry:
    horizon: int
    model: Any
    units: dict[int, float]
    features: dict[int, Any]  # product_id -> (horizon, len(FEATURES)) array used for the forecast
    festival_today: dict[int, tuple[str | None, int, bool]]  # product_id -> (label, days to start, ongoing)
    horizon_dates: list[date]
    explainer: Any = field(default=None)


_MISS = object()
_cache: OrderedDict[tuple, _Entry | None] = OrderedDict()
_lock = threading.Lock()


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def available() -> bool:
    return tuning.ML_FORECAST_ENABLED and np is not None and xgb is not None and shap is not None


def _festival_info(events: list[EventCalendar], category: str, d: date) -> tuple[str | None, int, bool]:
    """(label, days until it starts, is it on today) for the nearest festival that touches this category."""
    best: tuple[int, EventCalendar] | None = None
    for e in events:
        if e.categories and category not in e.categories:
            continue
        if e.end_date < d:
            continue
        days = max(0, (e.start_date - d).days)
        if best is None or days < best[0]:
            best = (days, e)
    if best is None or best[0] > FESTIVAL_CAP_DAYS:
        return None, FESTIVAL_CAP_DAYS, False
    days, e = best
    return e.label, days, e.start_date <= d <= e.end_date


def _fingerprint(db: Session, shop_id: int, is_demo: bool) -> tuple:
    sales = db.execute(select(func.count(Sale.id), func.coalesce(func.max(Sale.id), 0),
                              func.coalesce(func.sum(Sale.qty), 0)).where(Sale.shop_id == shop_id)).one()
    events = db.execute(select(func.count(EventCalendar.id), func.coalesce(func.max(EventCalendar.id), 0))
                        .where(EventCalendar.kind == "festival", EventCalendar.is_demo == is_demo)).one()
    return tuple(sales), tuple(events)


def _row_features(series, scale, dates: list[date], dtf, flag, t: int):
    """Feature matrix (products x features) for day index t. Needs t >= 7 (lag-7)."""
    x = np.empty((series.shape[0], len(FEATURES)))
    x[:, _DOW] = dates[t].weekday()
    x[:, _ROLL7] = series[:, t - 7:t].mean(axis=1) / scale
    x[:, _ROLL14] = series[:, max(0, t - 14):t].mean(axis=1) / scale
    x[:, _LAG7] = series[:, t - 7] / scale
    x[:, _DTF] = dtf[:, t]
    x[:, _FLAG] = flag[:, t]
    return x


def _train(x, y):
    model = xgb.XGBRegressor(n_estimators=80, max_depth=3, learning_rate=0.08, subsample=1.0, colsample_bytree=1.0,
                             objective="reg:squarederror", tree_method="hist", n_jobs=1,
                             random_state=tuning.ML_SEED)
    model.fit(x, y)
    return model


def _build(db: Session, shop: Shop, today: date, horizon: int) -> _Entry | None:
    yesterday = today - timedelta(days=1)
    first = db.scalar(select(func.min(Sale.sold_at)).where(Sale.shop_id == shop.id))
    history_days = (yesterday - first.date()).days + 1 if first is not None else 0
    if history_days < tuning.ML_MIN_HISTORY_DAYS:
        log.info("ML forecast skipped for shop %s: %s days of history", shop.id, history_days)
        return None

    start = max(first.date(), today - timedelta(days=MAX_TRAIN_DAYS))
    n = (yesterday - start).days + 1
    day = func.date(Sale.sold_at)
    rows = db.execute(
        select(Sale.product_id, day, func.sum(Sale.qty))
        .where(Sale.shop_id == shop.id, Sale.sold_at >= datetime.combine(start, time.min),
               Sale.sold_at < datetime.combine(today, time.min))
        .group_by(Sale.product_id, day)
    ).all()
    per_product: dict[int, dict[int, float]] = {}
    for pid, d, qty in rows:
        idx = (date.fromisoformat(str(d)[:10]) - start).days
        per_product.setdefault(pid, {})[idx] = float(qty)

    categories = dict(db.execute(select(Product.id, Product.category)).all())
    pids = sorted(p for p, days in per_product.items() if sum(days.values()) > 0 and p in categories)
    if not pids:
        return None
    hist = np.zeros((len(pids), n))
    for i, pid in enumerate(pids):
        for idx, qty in per_product[pid].items():
            hist[i, idx] = qty
    scale = hist.mean(axis=1)

    dates = [start + timedelta(days=i) for i in range(n + horizon)]
    events = list(db.scalars(select(EventCalendar).where(EventCalendar.kind == "festival",
                                                         EventCalendar.is_demo == shop.is_demo)))
    dtf = np.empty((len(pids), len(dates)))
    flag = np.empty_like(dtf)
    festival_today: dict[int, tuple[str | None, int, bool]] = {}
    for i, pid in enumerate(pids):
        for j, d in enumerate(dates):
            _, days, ongoing = _festival_info(events, categories[pid], d)
            dtf[i, j], flag[i, j] = days, float(ongoing)
        festival_today[pid] = _festival_info(events, categories[pid], today)

    xs, ys = [], []
    for t in range(7, n):
        xs.append(_row_features(hist, scale, dates, dtf, flag, t))
        ys.append(hist[:, t] / scale)
    model = _train(np.vstack(xs), np.concatenate(ys))

    series = np.concatenate([hist, np.zeros((len(pids), horizon))], axis=1)
    feats = np.empty((len(pids), horizon, len(FEATURES)))
    for h in range(horizon):
        t = n + h
        x = _row_features(series, scale, dates, dtf, flag, t)
        feats[:, h, :] = x
        series[:, t] = np.clip(model.predict(x), 0.0, None) * scale
    units = series[:, n:].sum(axis=1)
    if not np.all(np.isfinite(units)):
        raise ValueError("non-finite forecast")
    return _Entry(horizon=horizon, model=model, units={pid: float(units[i]) for i, pid in enumerate(pids)},
                  features={pid: feats[i] for i, pid in enumerate(pids)}, festival_today=festival_today,
                  horizon_dates=dates[n:])


def _get_entry(db: Session, shop_id: int, today: date, horizon: int) -> _Entry | None:
    if not available():
        return None
    try:
        shop = db.get(Shop, shop_id)
        if shop is None:
            return None
        key = (shop_id, today, horizon, tuning.ML_MIN_HISTORY_DAYS, _fingerprint(db, shop_id, shop.is_demo))
        with _lock:
            hit = _cache.get(key, _MISS)
            if hit is not _MISS:
                _cache.move_to_end(key)
                return hit  # type: ignore[return-value]
        entry = _build(db, shop, today, horizon)
        with _lock:
            _cache[key] = entry
            while len(_cache) > _CACHE_MAX:
                _cache.popitem(last=False)
        return entry
    except Exception:  # ML must never break the plan
        log.warning("ML forecast failed for shop %s, falling back to rule-based", shop_id, exc_info=True)
        return None


def forecast_units(db: Session, shop_id: int, today: date, horizon_days: int) -> dict[int, float] | None:
    """product_id -> predicted units over the horizon, or None when the rule-based path should be used."""
    entry = _get_entry(db, shop_id, today, horizon_days)
    return None if entry is None else entry.units


def _clean_label(label: str) -> str:
    return label.replace("(demo calendar)", "").strip()


def _reason(entry: _Entry, pid: int) -> str | None:
    if entry.explainer is None:
        entry.explainer = shap.TreeExplainer(entry.model)
    x = entry.features[pid]
    sv = np.asarray(entry.explainer.shap_values(x))  # (horizon, features), in "times normal sales" units
    horizon = x.shape[0]
    total = float(np.ravel(entry.explainer.expected_value)[0]) * horizon + float(sv.sum())
    if total <= 1e-6:
        return None

    def effect(cols: list[int]) -> float:
        contrib = float(sv[:, cols].sum())
        rest = total - contrib
        return contrib / rest * 100 if rest > 1e-6 else 0.0

    candidates: list[tuple[float, str]] = []
    label, days, ongoing = entry.festival_today.get(pid, (None, FESTIVAL_CAP_DAYS, False))
    if label is not None:  # no festival near this product's category -> nothing to say about festivals
        pct = effect([_DTF, _FLAG])
        when = "chal raha hai" if ongoing else f"{days} din me"
        candidates.append((abs(pct), f"{_clean_label(label)} {when}: {pct:+.0f}%"))

    pct = effect([_ROLL7, _ROLL14, _LAG7])
    candidates.append((abs(pct), f"pichhle hafte bikri {'tez' if pct > 0 else 'dheemi'} rahi: {pct:+.0f}%"))

    weekend = np.array([d.weekday() >= 5 for d in entry.horizon_dates])
    if weekend.any() and (~weekend).any():
        mean_ratio = total / horizon
        gap = (float(sv[weekend, _DOW].mean()) - float(sv[~weekend, _DOW].mean())) / mean_ratio * 100
        text = "weekend par bikri zyada" if gap > 0 else "hafte ke beech bikri zyada"
        candidates.append((abs(gap), f"{text} (~{abs(gap):.0f}%)"))

    top = sorted((c for c in candidates if c[0] >= MIN_REASON_PCT), key=lambda c: c[0], reverse=True)[:2]
    if not top:
        return "Bikri aam jaisi chal rahi hai, koi bada tyohaar ya trend nahi dikha"
    return ", ".join(text for _, text in top)


def explain_reason(db: Session, shop_id: int, product_id: int, today: date, horizon_days: int) -> str | None:
    """Short Hinglish reason from the top 2 SHAP factors, or None (the caller keeps the rule-based reason)."""
    try:
        entry = _get_entry(db, shop_id, today, horizon_days)
        if entry is None or product_id not in entry.features:
            return None
        return _reason(entry, product_id)
    except Exception:
        log.warning("SHAP reason failed for shop %s product %s", shop_id, product_id, exc_info=True)
        return None
