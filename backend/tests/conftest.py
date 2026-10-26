import os
import tempfile

# Use a throwaway SQLite file for DB-backed tests (set before any app import).
_tmp = tempfile.mkdtemp(prefix="vistaar-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
