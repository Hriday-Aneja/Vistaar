from types import SimpleNamespace as NS

from app.services.name_matching import match_customers, suggested_name


def cust(name, *aliases):
    return NS(display_name=name, aliases=list(aliases))


def test_ignores_filler_words_and_matches_alias():
    people = [cust("Rahul Verma", "Rahul bhai"), cust("Sunita Devi", "Sunita aunty")]
    hits = match_customers("Rahul bhai ko udhaar du?", people)
    assert hits and hits[0]["customer"].display_name == "Rahul Verma"


def test_matches_customeralias_like_objects():
    people = [cust("Rahul Verma", NS(alias="Rahul bhai")), cust("Sunita Devi", NS(alias="Sunita aunty"))]
    hits = match_customers("Rahul bhai ko udhaar du?", people)
    assert hits and hits[0]["customer"].display_name == "Rahul Verma"


def test_spelling_variants_match():
    assert match_customers("Raahul", [cust("Rahul Verma")])


def test_two_rahuls_are_ambiguous():
    people = [cust("Rahul Verma"), cust("Rahul Kumar")]
    assert len(match_customers("Rahul", people)) == 2


def test_unknown_name_has_no_match_and_a_suggestion():
    assert match_customers("Zorro", [cust("Rahul Verma")]) == []
    assert suggested_name("Zorro ko udhaar du") == "Zorro"
