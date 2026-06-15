from tools import search_listings


def _size_tokens(size: str) -> list[str]:
    """Split a listing size into comparable tokens (e.g. 'S/M' -> ['S', 'M'])."""
    return (
        size.upper().replace("/", " ").replace("(", " ").replace(")", " ").split()
    )


# ── The three scenarios from planning.md (Tool 1 verification strategy) ────────

# 1. Happy path: a specific query using all three filters ("a medium shirt under
#    $50") returns matching listings, and EVERY result genuinely satisfies the
#    keyword, size, and price constraints.
def test_search_happy_path():
    results = search_listings("shirt", size="M", max_price=50)

    assert isinstance(results, list)
    assert len(results) > 0
    for item in results:
        assert item["price"] <= 50                       # price ceiling respected
        assert "M" in _size_tokens(item["size"])         # size M actually matched
        haystack = (item["title"] + " " + item["description"]).lower()
        assert "shirt" in haystack                       # keyword actually present


# 2. Broad query with the optional parameters set to None — the size and price
#    filters are skipped gracefully. Proven by comparison: the unfiltered query
#    returns strictly more items than the same query with a filter applied.
def test_search_optional_none():
    broad = search_listings("vintage", size=None, max_price=None)
    price_filtered = search_listings("vintage", size=None, max_price=25)
    size_filtered = search_listings("vintage", size="M", max_price=None)

    assert isinstance(broad, list)
    assert len(broad) > 0
    assert len(broad) > len(price_filtered)   # price filter was skipped when None
    assert len(broad) > len(size_filtered)    # size filter was skipped when None


# 3. Impossible query (a designer gown for $5) — returns an empty list cleanly,
#    NOT an exception.
def test_search_impossible_returns_empty():
    results = search_listings("designer gown", size="XXS", max_price=5)
    assert results == []


# ── Additional coverage ───────────────────────────────────────────────────────

# Price math holds on real items (Track Jacket $45, Denim Jacket $42).
def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=45)
    assert len(results) > 0
    assert all(item["price"] <= 45 for item in results)


# Relevance: the best keyword-overlap match is ranked first.
def test_search_description_relevance():
    results = search_listings("vintage navy crewneck", size=None, max_price=None)
    assert len(results) > 0

    top_result = results[0]
    combined_text = (top_result["title"] + " " + top_result["description"]).lower()
    assert all(kw in combined_text for kw in ["vintage", "navy", "crewneck"])
