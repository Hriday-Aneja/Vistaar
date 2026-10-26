from app.services.pricing_rules import Quote, best_quote, clamp_counter_offer, margin_pct


def q(dist, price, days=2):
    return Quote(dist, "ghee", price, 20, days)


def test_margin():
    assert round(margin_pct(100, 80), 1) == 20.0


def test_best_quote_respects_min_margin():
    assert best_quote([q("a", 95), q("b", 80), q("c", 70)], 100, 8).distributor_id == "c"
    assert best_quote([q("a", 99)], 100, 8) is None


def test_counter_offer_clamped():
    assert clamp_counter_offer(100, 50, 15) == 85.0
