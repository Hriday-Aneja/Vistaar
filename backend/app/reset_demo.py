"""Reset the demo to the seeded story: python -m app.reset_demo

Re-creates every table and reloads the demo data, which also clears pending plans and orders.
It refuses to run if real (non-demo) shops exist, unless --force is given.
"""
import sys

from sqlalchemy import func, inspect, select

from app import seed
from app.db import models as m
from app.db.session import SessionLocal, engine


def main(force: bool = False) -> int:
    if inspect(engine).has_table("shops") and not force:
        with SessionLocal() as db:
            real = db.scalar(select(func.count()).select_from(m.Shop).where(m.Shop.is_demo.is_(False)))
        if real:
            print(f"Refusing to reset: {real} real (non-demo) shop(s) exist. Use --force only if you are sure.")
            return 1
    seed.build()
    print("Demo reset. Logins (phone / password):")
    for i, (name, *_rest) in enumerate(seed.SHOPS):
        print(f"  {seed.OWNER_PHONES[i]} / {seed.DEMO_PASSWORD}  ->  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(force="--force" in sys.argv))