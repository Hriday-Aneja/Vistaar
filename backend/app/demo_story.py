"""The SIMULATED 31-day story for the real demo mohalla (app/demo_real.py). Pure: no HTTP, no DB.

Everything here is generated from a fixed seed, so a run always produces the same numbers. None of it is real
merchant history: demo_real.py sends it through the normal API as backdated stock, sales and udhaar entries.

Who plays what (shop numbers are 0-based positions in SHOP_NAMES):
  0-3  sales spike on the last day for SPIKE_PRODUCT        -> GET /api/pulse
  5    sales drop over the last DROP_DAYS days               -> GET /api/pulse/drops
  1    one udhaar customer, credit entered 20 days ago       -> GET /api/khata/drafts
  1    near-expiry long-life milk that is not selling        -> GET /api/swaps/suggestions
  2    next door: sells that milk fast and is nearly out     -> (receives the swap)
"""
import random

SEED = 20261028
# Daily sales run from 30 days ago up to and including today: 30 full days of history before today, which is what
# services/ml_forecast.py needs (ML_MIN_HISTORY_DAYS) before it trains the XGBoost forecast for a shop.
HISTORY_DAYS = 31
OPENING_DAYS_AGO = 31    # the opening batch of every product was received this many days ago
LEFTOVER_DAYS = 2        # each product ends the 30 days with about this many days of cover

SHOP_NAMES = ["Sharma General Store", "Gupta Kirana", "Verma Provision", "Khan Mart", "Singh Traders", "Joshi Stores"]

# name, category, selling price (also the MRP when the product is created), cost price
PRODUCTS = [
    ("Demo Atta 5kg", "Staples", 300.0, 240.0),
    ("Demo Sunflower Oil 1L", "Staples", 150.0, 120.0),
    ("Demo Glucose Biscuit 800g", "Biscuits", 80.0, 62.0),
]
BASE_DAILY = {"Demo Atta 5kg": 8, "Demo Sunflower Oil 1L": 6, "Demo Glucose Biscuit 800g": 10}

SPIKE_PRODUCT = "Demo Atta 5kg"
SPIKE_SHOPS = (0, 1, 2, 3)
SPIKE_FACTOR = 3         # last-day units = 3x the shop's normal daily units

DROP_SHOP = 5
DROP_DAYS = 4            # today and the 3 days before it
DROP_FACTOR = 0.3

# Long-life milk (category Dairy, but with an explicit expiry date, so the 3-day Dairy default is not used)
MILK = ("Demo UHT Milk 1L", "Dairy", 72.0, 62.0)
MILK_SENDER, MILK_RECEIVER = 1, 2
MILK_SENDER_QTY = 40
MILK_SENDER_RECEIVED_DAYS_AGO = 2
MILK_EXPIRES_IN_DAYS = 3                 # the sender's batch: nobody sells it, so most of it is at risk
MILK_RECEIVER_DAYS = 14                  # the receiver sells it for 14 days (the forecast window)
MILK_RECEIVER_BASE = 10
MILK_RECEIVER_LEFT = 8                   # about 0.8 day of cover: nearly out
MILK_RECEIVER_EXPIRES_IN_DAYS = 5

UDHAAR_SHOP = 1
UDHAAR_CUSTOMER = ("Demo Customer Ramesh", "9876500011")
UDHAAR_AMOUNT = 1200
UDHAAR_DAYS_AGO = 20


def _rng(shop: int, product: str) -> random.Random:
    return random.Random(f"{SEED}:{shop}:{product}")  # string seeds are stable across runs and machines


def base_daily(shop: int, product: str) -> int:
    return BASE_DAILY[product] + shop % 3


def leftover(shop: int, product: str) -> int:
    return LEFTOVER_DAYS * base_daily(shop, product)


def daily_sales(shop: int, product: str) -> dict[int, int]:
    """{days_ago: units} for the 31 days up to today (days_ago 0 = today). One sale per product per day."""
    rng, base, out = _rng(shop, product), base_daily(shop, product), {}
    for days_ago in range(HISTORY_DAYS - 1, -1, -1):
        qty = max(1, base + rng.randint(-1, 1))
        if shop == DROP_SHOP and days_ago < DROP_DAYS:
            qty = max(1, round(base * DROP_FACTOR + rng.uniform(-0.5, 0.5)))
        if product == SPIKE_PRODUCT and shop in SPIKE_SHOPS and days_ago == 0:
            qty = SPIKE_FACTOR * base
        out[days_ago] = qty
    return out


def opening_qty(shop: int, product: str) -> int:
    return sum(daily_sales(shop, product).values()) + leftover(shop, product)


def milk_receiver_sales() -> dict[int, int]:
    rng = _rng(MILK_RECEIVER, MILK[0])
    return {d: max(1, MILK_RECEIVER_BASE + rng.randint(-1, 1)) for d in range(MILK_RECEIVER_DAYS - 1, -1, -1)}


def milk_receiver_opening_qty() -> int:
    return sum(milk_receiver_sales().values()) + MILK_RECEIVER_LEFT


def shop_totals(shop: int) -> dict[int, int]:
    """Total units per day for one shop over all HISTORY_DAYS days (the sales-drop check only looks at the last 30), incl. the milk."""
    totals = {d: 0 for d in range(HISTORY_DAYS)}
    for name, *_ in PRODUCTS:
        for d, q in daily_sales(shop, name).items():
            totals[d] += q
    if shop == MILK_RECEIVER:
        for d, q in milk_receiver_sales().items():
            totals[d] += q
    return totals


def story_state(units_now: int, opening: int, final: int) -> str:
    """Where a (shop, product) is in the story, judged only from the units on hand (so it works over HTTP):
    absent  nothing on hand yet                          -> create the opening batch, then the sales
    fresh   exactly the opening batch, nothing sold      -> post the sales
    done    exactly what the finished story leaves       -> nothing to do (this is what makes re-runs safe)
    changed anything else (partly built, or the owner used the app) -> leave it alone and warn
    """
    if units_now == 0:
        return "absent"
    if units_now == opening:
        return "fresh"
    if units_now == final:
        return "done"
    return "changed"