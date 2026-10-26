from urllib.parse import quote


def build_upi_link(vpa: str, payee_name: str, amount: float, note: str = "") -> str:
    """Standard UPI deep link. Opens any UPI app with the amount prefilled."""
    return (f"upi://pay?pa={quote(vpa)}&pn={quote(payee_name)}&am={amount:.2f}&cu=INR"
            f"&tn={quote(note or 'Khata payment')}")
