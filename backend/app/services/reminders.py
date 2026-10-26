"""Khata reminder drafts. Template-based Hinglish today; swap in LLMRouter for tone variation.

Reminders are only ever *drafted* here. A merchant must press send (routers/khata.py).
"""


def draft_message(shop_name: str, customer_name: str, pending: float, overdue_days: int, upi_link: str) -> str:
    first = customer_name.split(" ")[0]
    if overdue_days >= 30:
        ask = f"Rs {pending:.0f} kaafi din se baaki hai. Jab suvidha ho, neeche link se de dijiye."
    else:
        ask = f"Rs {pending:.0f} baaki hai. Jab suvidha ho, neeche link se de dijiye."
    return f"Namaste {first} ji, {shop_name} se. {ask}\n{upi_link}\nDhanyavaad!"
