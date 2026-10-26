"""Tamper-evident, hash-chained audit log for every order action.

Each entry hashes (previous hash + timestamp + payload). Editing any past entry
breaks verification of everything after it.
"""
import hashlib
import json
import time

GENESIS = "0" * 64


def _digest(prev_hash: str, ts: float, payload: dict) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{prev_hash}|{ts}|{body}".encode()).hexdigest()


class AuditLog:
    def __init__(self) -> None:
        self.entries: list[dict] = []

    def append(self, payload: dict) -> str:
        prev = self.entries[-1]["hash"] if self.entries else GENESIS
        ts = time.time()
        entry = {
            "index": len(self.entries),
            "ts": ts,
            "payload": payload,
            "prev_hash": prev,
            "hash": _digest(prev, ts, payload),
        }
        self.entries.append(entry)
        return entry["hash"]

    def verify(self) -> bool:
        prev = GENESIS
        for e in self.entries:
            if e["prev_hash"] != prev or e["hash"] != _digest(prev, e["ts"], e["payload"]):
                return False
            prev = e["hash"]
        return True


audit_log = AuditLog()  # in-memory for now; move to Postgres later
