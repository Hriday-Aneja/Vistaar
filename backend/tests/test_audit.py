from app.services.audit import AuditLog


def test_chain_verifies():
    log = AuditLog()
    log.append({"a": 1})
    log.append({"b": 2})
    assert log.verify()


def test_tampering_detected():
    log = AuditLog()
    log.append({"a": 1})
    log.append({"b": 2})
    log.entries[0]["payload"]["a"] = 999
    assert not log.verify()
