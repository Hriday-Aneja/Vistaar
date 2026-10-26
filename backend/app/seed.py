import random
from datetime import date, datetime, timedelta

from app.db import models as m
from app.db.session import Base, SessionLocal, engine
from app.security import hash_password, normalize_phone, phone_hash
from app.services.audit_db import append_audit

DEMO_PASSWORD = "vistaar123"
TODAY = date.today()

PRODUCTS = [
    ("Marie Gold Biscuits", "मैरी गोल्ड बिस्कुट", "Biscuits", "pack", 120, 10, 5),
    ("Cream Biscuits", "क्रीम बिस्कुट", "Biscuits", "pack", 90, 20, 4),
    ("Ice Cream Cone", "आइसक्रीम कोन", "Frozen", "piece", 180, 30, 6),
    ("Cold Drink 600ml", "कोल्ड ड्रिंक", "Beverages", "bottle", 180, 40, 8),
    ("Packaged Milk 500ml", "दूध", "Dairy", "pack", 3, 30, 20),
    ("Bread Loaf", "ब्रेड", "Bakery", "loaf", 4, 45, 10),
    ("Atta 5kg", "आटा 5kg", "Staples", "bag", 180, 260, 3),
    ("Basmati Rice 1kg", "बासमती चावल", "Staples", "pack", 365, 120, 3),
    ("Toor Dal 1kg", "अरहर दाल", "Staples", "pack", 365, 160, 3),
    ("Sunflower Oil 1L", "सनफ्लावर तेल", "Staples", "pouch", 270, 150, 4),
    ("Maggi Noodles", "मैगी", "Instant food", "pack", 270, 14, 9),
    ("Namkeen Bhujia", "भुजिया", "Snacks", "pack", 120, 20, 5),
    ("Tea 250g", "चाय पत्ती", "Beverages", "pack", 365, 120, 2),
    ("Detergent Powder 1kg", "डिटर्जेंट", "Household", "pack", 730, 110, 2),
]

SHOPS = [
    ("Sharma General Store", "Rakesh Sharma", "Dwarka Sec 12", 28.5921, 77.0460, "demo.sharma@paytm", 1.0),
    ("Gupta Kirana", "Anil Gupta", "Dwarka Sec 12", 28.5985, 77.0512, "demo.gupta@paytm", 1.1),
    ("Singh Provision Store", "Harpreet Singh", "Dwarka Sec 11", 28.5880, 77.0395, "demo.singh@paytm", 1.0),
    ("Mohalla Mart", "Deepa Nair", "Dwarka Sec 11", 28.5950, 77.0390, "demo.mohallamart@paytm", 0.9),
    ("Anita Daily Needs", "Anita Rawat", "Dwarka Sec 13", 28.5890, 77.0525, "demo.anita@paytm", 1.0),
    ("Bansal Super Store", "Sanjay Bansal", "Dwarka Sec 10", 28.6030, 77.0450, "demo.bansal@paytm", 1.2),
]

OWNER_PHONES = ["9000000001", "9000000002", "9000000003", "9000000004", "9000000005", "9000000006"]

CUSTOMERS = {
    0: [
        ("Rahul Verma", "9810011111", ["Rahul bhai", "Raahul"], [(40, 600), (25, 500), (25, -250)], 3),
        ("Rahul Kumar", "9810022222", ["Rahul painter"], [(20, 420), (10, -100)], 10),
        ("Sunita Devi", "9810033333", ["Sunita aunty"], [(15, 300), (12, -300)], 12),
        ("Mohan Lal", "9810044444", [], [(30, 540)], 30),
    ],
    1: [("Sunita Devi", "9810033333", [], [(30, 300), (28, -300)], 28)],
    2: [("Rahul Verma", "9810011111", [], [(50, 900), (30, -200)], 30)],
    3: [("Rahul Verma", "9810011111", [], [(70, 500), (45, -100)], 45)],
}

EVENTS = [
    ("heatwave", "Heatwave, 43C expected in Delhi (demo calendar)", -2, 4, ["Frozen", "Beverages"],
     "Ice cream aur cold drink ka stock badhao"),
    ("cricket", "India vs Australia ODI (demo calendar)", 3, 3, ["Snacks", "Beverages"],
     "Namkeen aur cold drink match se pehle rakho"),
    ("wedding_season", "Wedding season (demo calendar)", 10, 60, ["Staples", "Dairy"],
     "Atta, chawal, tel ka bulk order plan karo"),
]


def build():
    rng = random.Random(42)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()

    products = {}
    base_rate = {}
    for name, name_hi, cat, unit, shelf, mrp, rate in PRODUCTS:
        p = m.Product(name=name, name_hi=name_hi, category=cat, unit=unit, default_shelf_days=shelf, mrp=mrp)
        db.add(p)
        products[name] = p
        base_rate[name] = rate

    shops = []
    for i, (name, owner, area, lat, lng, vpa, factor) in enumerate(SHOPS):
        s = m.Shop(name=name, owner_name=owner, area=area, lat=lat, lng=lng, upi_vpa=vpa, is_demo=True)
        db.add(s)
        shops.append((s, factor))
    db.flush()

    for i, (s, _) in enumerate(shops):
        db.add(m.User(phone=OWNER_PHONES[i], name=s.owner_name, password_hash=hash_password(DEMO_PASSWORD), shop_id=s.id))

    rate_override = {(0, "Marie Gold Biscuits"): 2, (1, "Marie Gold Biscuits"): 9}
    spike_shops = {2, 3, 4}

    def rate_for(si, pname):
        return rate_override.get((si, pname), base_rate[pname] * shops[si][1])

    for si, (s, _) in enumerate(shops):
        for pname, p in products.items():
            rate = rate_for(si, pname)
            received = TODAY - timedelta(days=rng.randint(5, 20))
            qty_left = max(2, round(rate * rng.uniform(3, 9)))
            expiry_source = "entered" if p.category in ("Dairy", "Bakery", "Biscuits") else "default"
            expiry = received + timedelta(days=p.default_shelf_days)
            if (si, pname) == (0, "Marie Gold Biscuits"):
                received, qty_left, expiry, expiry_source = TODAY - timedelta(days=60), 140, TODAY + timedelta(days=9), "entered"
            if (si, pname) == (1, "Marie Gold Biscuits"):
                qty_left = 10
            if pname == "Ice Cream Cone" and si in spike_shops:
                qty_left = round(rate * 1.5)
            db.add(m.Batch(
                shop_id=s.id, product_id=p.id, qty_received=qty_left + round(rate * 5), qty_left=qty_left,
                cost_price=round(p.mrp * 0.8, 2), sell_price=p.mrp, received_on=received,
                expiry_date=expiry, expiry_source=expiry_source, source="manual",
            ))
            for d in range(30, -1, -1):
                r = rate
                if pname == "Ice Cream Cone" and si in spike_shops and d <= 1:
                    r = rate * 3.2
                qty = max(0, round(rng.gauss(r, max(0.6, rate * 0.12))))
                if qty:
                    db.add(m.Sale(
                        shop_id=s.id, product_id=p.id, qty=qty, amount=qty * p.mrp,
                        sold_at=datetime.combine(TODAY - timedelta(days=d), datetime.min.time()) + timedelta(hours=12),
                        is_simulated=1,
                    ))

    db.flush()
    for si, rows in CUSTOMERS.items():
        s = shops[si][0]
        for name, phone, aliases, entries, last_visit_days in rows:
            c = m.Customer(shop_id=s.id, phone=normalize_phone(phone), phone_hash=phone_hash(phone),
                           display_name=name, last_visit=TODAY - timedelta(days=last_visit_days))
            c.aliases = [m.CustomerAlias(alias=a) for a in aliases]
            db.add(c)
            db.flush()
            for days_ago, amount in entries:
                db.add(m.KhataEntry(shop_id=s.id, customer_id=c.id, amount=amount,
                                    note="udhaar" if amount > 0 else "payment", created_on=TODAY - timedelta(days=days_ago)))

    for kind, label, start, end, cats, action in EVENTS:
        db.add(m.EventCalendar(kind=kind, label=label, start_date=TODAY + timedelta(days=start),
                               end_date=TODAY + timedelta(days=end), categories=cats, suggested_action=action))

    distributors = [m.Distributor(name="Agarwal Wholesale", phone="9100000001", floor_ratio=0.90),
                    m.Distributor(name="Delhi Bulk Traders", phone="9100000002", floor_ratio=0.88),
                    m.Distributor(name="Sai Distributors", phone="9100000003", floor_ratio=0.92)]
    db.add_all(distributors)
    db.flush()
    # (price factor vs MRP, min qty, delivery days). min_qty is why pooling matters: a lone shop
    # rarely reaches it, a mohalla pool does.
    terms = [(0.80, 50, 2), (0.76, 100, 3), (0.78, 60, 1)]
    for di, (d, (price_f, min_qty, days)) in enumerate(zip(distributors, terms)):
        for p in products.values():
            factor = price_f * rng.uniform(0.98, 1.02)
            if di == 2 and p.name == "Atta 5kg":
                factor = 0.97  # deliberately inflated quote for the Fair-Price Radar demo
            db.add(m.DistributorQuote(distributor_id=d.id, product_id=p.id, unit_price=round(p.mrp * factor, 2),
                                      min_qty=min_qty, delivery_days=days, valid_till=TODAY + timedelta(days=7)))

    # Past purchase orders from other pools: the benchmark the Price Radar compares quotes against.
    db.flush()
    for k in range(8):
        d = distributors[k % 2]
        lines = []
        for p in products.values():
            paid = round(p.mrp * terms[k % 2][0] * rng.uniform(0.96, 1.0), 2)
            lines.append({"product_id": p.id, "shop_id": shops[k % len(shops)][0].id, "qty": rng.randint(20, 80), "unit_price": paid})
        db.add(m.PurchaseOrder(distributor_id=d.id, lines=lines, status="approved", thread_id="seed",
                               total=round(sum(l["qty"] * l["unit_price"] for l in lines), 2),
                               created_at=m.utcnow() - timedelta(days=rng.randint(2, 25))))

    append_audit(db, "system", 0, {"event": "demo data seeded", "shops": len(shops)})
    db.commit()
    db.close()


if __name__ == "__main__":
    build()
    print("Seed done. Demo logins (phone / password):")
    for i, (name, *_rest) in enumerate(SHOPS):
        print(f"  {OWNER_PHONES[i]} / {DEMO_PASSWORD}  ->  {name}")
