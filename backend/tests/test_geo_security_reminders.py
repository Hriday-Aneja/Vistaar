from app.security import hash_password, normalize_phone, phone_hash, verify_password
from app.services.geo import haversine_km
from app.services.reminders import draft_message
from app.services.upi import build_upi_link


def test_haversine():
    assert haversine_km(28.5, 77.2, 28.5, 77.2) == 0
    assert 110 < haversine_km(28.0, 77.0, 29.0, 77.0) < 112  # 1 degree latitude ~ 111 km


def test_phone_hash_is_stable_and_format_insensitive():
    assert normalize_phone("+91 98100-11111") == "9810011111"
    assert phone_hash("+91 98100 11111") == phone_hash("9810011111")


def test_password_roundtrip():
    h = hash_password("secret1")
    assert verify_password("secret1", h) and not verify_password("wrong", h)


def test_upi_link_and_reminder():
    link = build_upi_link("shop@paytm", "Sharma General Store", 500, "Khata")
    assert link.startswith("upi://pay?pa=shop%40paytm") and "am=500.00" in link
    assert "Rs 500" in draft_message("Sharma General Store", "Rahul Verma", 500, 10, link)
