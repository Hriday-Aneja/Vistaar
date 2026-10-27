import os
import tempfile

# Use a throwaway SQLite file for DB-backed tests (set before any app import).
_tmp = tempfile.mkdtemp(prefix="vistaar-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
# The seeded API flow tests assert the rule-based plan wording. ML tests switch the forecast on explicitly.
os.environ.setdefault("VISTAAR_ML_FORECAST", "0")
# Nothing in the tests may talk to a real Redis. Alert tests plug in an in-memory bus with alert_bus.set_bus().
os.environ.setdefault("VISTAAR_ALERTS_REDIS", "0")
