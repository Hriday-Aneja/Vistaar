import re
from difflib import SequenceMatcher

STOPWORDS = {
    "ko", "ka", "ki", "ke", "udhaar", "udhar", "du", "dun", "dena", "de", "do", "dedu", "kya", "kitna", "hai",
    "liye", "ji", "bhai", "bhaiya", "sir", "aunty", "uncle", "madam", "mam", "didi", "bhabhi", "shri", "smt",
}
THRESHOLD = 0.8


def fold(token: str) -> str:
    token = re.sub(r"(.)\1+", r"\1", token.lower())
    return token.replace("w", "v")


def tokens(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z\u0900-\u097F]+", text or "")
    return [fold(w) for w in words if w.lower() not in STOPWORDS]


def _token_score(query: str, candidate: str) -> float:
    if query == candidate:
        return 1.0
    if len(query) >= 3 and candidate.startswith(query):
        return 1.0
    if len(query) < 3:
        return 0.0
    return SequenceMatcher(None, query, candidate).ratio()


def _name_score(query_tokens: list[str], name: str) -> float:
    candidate_tokens = tokens(name)
    if not query_tokens or not candidate_tokens:
        return 0.0
    return sum(max(_token_score(q, c) for c in candidate_tokens) for q in query_tokens) / len(query_tokens)


def match_customers(query: str, customers) -> list[dict]:
    query_tokens = tokens(query)
    results = []
    for customer in customers:
        best, reason = _name_score(query_tokens, customer.display_name), "naam"
        for alias in customer.aliases:
            score = _name_score(query_tokens, alias)
            if score > best:
                best, reason = score, "nickname"
        if best >= THRESHOLD:
            results.append({"customer": customer, "score": round(best, 2), "reason": reason})
    return sorted(results, key=lambda item: item["score"], reverse=True)


def suggested_name(query: str) -> str:
    return " ".join(w.capitalize() for w in re.findall(r"[A-Za-z\u0900-\u097F]+", query or "")
                    if w.lower() not in STOPWORDS)
