"""Rules for dates the merchant types in by hand (backdated sales and udhaar entries). Pure: no DB."""
from datetime import date, datetime, time

MAX_BACKDATE_DAYS = 60


def check_backdate(value: date, today: date, max_days: int = MAX_BACKDATE_DAYS) -> None:
    """Raise ValueError (Hinglish message) if value is in the future or more than max_days old."""
    if value > today:
        raise ValueError("Aane wali date nahi chalegi")
    if (today - value).days > max_days:
        raise ValueError(f"{max_days} din se purani date nahi chalegi")


def noon_of(day: date) -> datetime:
    """Backdated rows are stamped at 12:00 on that day (the seed data uses the same convention)."""
    return datetime.combine(day, time(12, 0))