"""
Unit tests for the planning loop in agent.py (see planning.md Milestone 4,
verification strategy lines 273-278).

These tests verify the AGENT'S ORCHESTRATION LOGIC in isolation: every external
dependency (the query parser and the three tools) is mocked at the `agent`
module level via monkeypatch, so the suite is deterministic, fast, and runs
offline — no LLM, API key, or network involved. We assert how state flows
through the session and that the loop short-circuits correctly on failure.
"""

import agent
from agent import run_agent


# Two stand-in listings; run_agent should pick the FIRST as the top match.
SAMPLE_RESULTS = [
    {"id": "lst_006", "title": "Graphic Tee", "price": 24.0, "platform": "depop",
     "size": "L", "description": "faded vintage graphic tee"},
    {"id": "lst_033", "title": "Band Tee", "price": 19.0, "platform": "depop",
     "size": "L", "description": "distressed band tee"},
]

WARDROBE = {"items": [{"id": "w1", "name": "Baggy jeans", "category": "bottoms"}]}


# 1. Successful State Pipeline Flow: parse -> search_listings (full array stored,
#    top match selected) -> suggest_outfit (item passed in, text captured) ->
#    create_fit_card (suggestion + item passed in, caption saved).
def test_successful_state_pipeline(monkeypatch):
    calls = {}

    monkeypatch.setattr(
        agent, "_parse_query",
        lambda q: {"description": "graphic tee", "size": None, "max_price": 30.0},
    )

    def fake_search(description, size, max_price):
        calls["search"] = {"description": description, "size": size, "max_price": max_price}
        return list(SAMPLE_RESULTS)

    def fake_suggest(new_item, wardrobe):
        calls["suggest"] = {"new_item": new_item, "wardrobe": wardrobe}
        return "Pair it with your baggy jeans and combat boots."

    def fake_card(outfit, new_item):
        calls["card"] = {"outfit": outfit, "new_item": new_item}
        return "Scored this Graphic Tee for $24 on depop — grunge vibes only."

    monkeypatch.setattr(agent, "search_listings", fake_search)
    monkeypatch.setattr(agent, "suggest_outfit", fake_suggest)
    monkeypatch.setattr(agent, "create_fit_card", fake_card)

    session = run_agent("graphic tee under $30", WARDROBE)

    assert session["error"] is None

    # search_listings ran with the parsed params, full array stored, top selected.
    assert calls["search"] == {"description": "graphic tee", "size": None, "max_price": 30.0}
    assert session["search_results"] == SAMPLE_RESULTS
    assert session["selected_item"] == SAMPLE_RESULTS[0]

    # selected_item passed into suggest_outfit; its text captured.
    assert calls["suggest"]["new_item"] == SAMPLE_RESULTS[0]
    assert calls["suggest"]["wardrobe"] == WARDROBE
    assert session["outfit_suggestion"] == "Pair it with your baggy jeans and combat boots."

    # suggestion + item passed into create_fit_card; caption saved.
    assert calls["card"]["outfit"] == session["outfit_suggestion"]
    assert calls["card"]["new_item"] == SAMPLE_RESULTS[0]
    assert session["fit_card"] == "Scored this Graphic Tee for $24 on depop — grunge vibes only."


# 2. Empty Search Branching (Early Return): search_listings returns [] -> a
#    helpful error is logged and the loop short-circuits, NEVER invoking the
#    downstream tools.
def test_empty_search_early_return(monkeypatch):
    called = {"suggest": False, "card": False}

    monkeypatch.setattr(
        agent, "_parse_query",
        lambda q: {"description": "designer gown", "size": "XXS", "max_price": 5.0},
    )
    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [])

    def fake_suggest(*args, **kwargs):
        called["suggest"] = True
        return "should never run"

    def fake_card(*args, **kwargs):
        called["card"] = True
        return "should never run"

    monkeypatch.setattr(agent, "suggest_outfit", fake_suggest)
    monkeypatch.setattr(agent, "create_fit_card", fake_card)

    session = run_agent("designer gown size XXS under $5", WARDROBE)

    assert session["search_results"] == []
    assert session["error"]                       # helpful feedback message set
    assert session["selected_item"] is None
    assert session["outfit_suggestion"] is None
    assert session["fit_card"] is None
    assert called["suggest"] is False             # downstream tools never invoked
    assert called["card"] is False


# 3a. LLM/API Failure Mode — invalid API environment: the LLM client raises
#     during query parsing. The agent catches it (parsed == {}), sets a helpful
#     error, and returns early without ever searching or crashing.
def test_parse_failure_invalid_api(monkeypatch):
    called = {"search": False}

    def boom():
        raise ConnectionError("invalid API environment")

    def fake_search(**kwargs):
        called["search"] = True
        return list(SAMPLE_RESULTS)

    monkeypatch.setattr(agent, "_get_groq_client", boom)
    monkeypatch.setattr(agent, "search_listings", fake_search)

    session = run_agent("vintage graphic tee under $30", WARDROBE)

    assert session["parsed"] == {}
    assert session["error"]
    assert session["search_results"] == []
    assert session["selected_item"] is None
    assert session["fit_card"] is None
    assert called["search"] is False              # never reached search step


# 3b. LLM/API Failure Mode — network exception mid-pipeline: suggest_outfit
#     returns a tool error string. The agent detects it, halts before
#     create_fit_card, and sets a helpful error instead of crashing.
def test_suggest_outfit_failure_halts(monkeypatch):
    called = {"card": False}

    monkeypatch.setattr(
        agent, "_parse_query",
        lambda q: {"description": "graphic tee", "size": None, "max_price": None},
    )
    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: list(SAMPLE_RESULTS))
    monkeypatch.setattr(
        agent, "suggest_outfit",
        lambda new_item, wardrobe: (
            "Sorry, I ran into a problem generating outfit suggestions "
            "(ConnectionError). Please check your connection or API key and try again."
        ),
    )

    def fake_card(*args, **kwargs):
        called["card"] = True
        return "should never run"

    monkeypatch.setattr(agent, "create_fit_card", fake_card)

    session = run_agent("graphic tee", WARDROBE)

    assert session["selected_item"] == SAMPLE_RESULTS[0]   # search succeeded
    assert session["outfit_suggestion"] is None            # error not stored as output
    assert session["error"]
    assert session["fit_card"] is None
    assert called["card"] is False                         # halted before fit card
