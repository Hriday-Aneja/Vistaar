"""Auth helpers. Stdlib only.

phone_hash uses HMAC with a secret that lives outside the database, so a leaked DB alone
cannot be used to brute-force phone numbers (only 10^10 possibilities).
"""
import hashlib
import hmac
import re
import secrets

from app import tuning


def normalize_phone(raw: str) -> str:
    return re.sub(r"\D", "", raw or "")[-10:]


def phone_hash(raw: str) -> str:
    return hmac.new(tuning.PHONE_SECRET.encode(), normalize_phone(raw).encode(), hashlib.sha256).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return salt.hex() + "$" + key.hex()


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, key_hex = stored.split("$")
        key = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
        return hmac.compare_digest(key.hex(), key_hex)
    except ValueError:
        return False
