"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import json
import re

from tools import (
    search_listings,
    suggest_outfit,
    create_fit_card,
    _get_groq_client,
)


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── helpers ───────────────────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """
    Extract search parameters (description, size, max_price) from the raw query.

    Step 2 of the planning loop uses the LLM to parse the free-form request into
    structured fields — this keeps the `description` clean (just item keywords,
    no filler words) so search_listings scores relevance accurately.

    Returns a dict with keys: description (str), size (str | None),
    max_price (float | None). Returns an empty dict {} if parsing fails or no
    usable description could be extracted, which the planning loop treats as a
    failure to extract parameters.
    """
    prompt = (
        "Extract structured search parameters from a user's secondhand-clothing "
        "request. Return ONLY a JSON object with exactly these keys:\n"
        '  "description": a short string of item keywords (type, style, color). '
        "Never include size or price words here.\n"
        '  "size": the requested size as a string (e.g. "M", "US 8"), or null if '
        "none is mentioned.\n"
        '  "max_price": the maximum price as a number, or null if none is '
        "mentioned.\n\n"
        f"User request: {query}\n\n"
        "JSON:"
    )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"},  # force valid JSON output
        )
        raw = response.choices[0].message.content.strip()
        # Strip ```json ... ``` fences the model may add.
        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Fallback: pull the first {...} block out of any surrounding prose.
            match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
            if not match:
                return {}
            data = json.loads(match.group())
    except Exception:
        return {}

    description = (data.get("description") or "").strip()
    if not description:
        return {}

    size = data.get("size")
    if isinstance(size, str):
        size = size.strip() or None
    elif size is not None:
        size = str(size)

    max_price = data.get("max_price")
    if isinstance(max_price, str):
        match = re.search(r"\d+(?:\.\d+)?", max_price)
        max_price = float(match.group()) if match else None
    elif isinstance(max_price, (int, float)):
        max_price = float(max_price)
    else:
        max_price = None

    return {"description": description, "size": size, "max_price": max_price}


def _is_tool_error(text: str) -> bool:
    """
    True if a tool returned a descriptive error string instead of real output.

    suggest_outfit and create_fit_card never raise — on failure they return a
    string starting with "Sorry, I ran into a problem" / "Sorry, I couldn't".
    Empty or whitespace-only output is treated as a failure too. (The empty
    wardrobe path of suggest_outfit returns normal advice, so it is NOT flagged.)
    """
    if not text or not text.strip():
        return True
    lowered = text.strip().lower()
    return lowered.startswith("sorry, i ran into a problem") or lowered.startswith(
        "sorry, i couldn't"
    )


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    # Step 1: fresh session — the single source of truth for this interaction.
    session = _new_session(query, wardrobe)

    # Step 2: parse the query into description / size / max_price.
    session["parsed"] = _parse_query(query)
    if not session["parsed"]:
        session["error"] = (
            "Sorry, I couldn't understand your request. Try describing the item "
            "you're after, e.g. \"vintage graphic tee under $30, size M\"."
        )
        return session

    parsed = session["parsed"]

    # Step 3: search the listings with the parsed parameters.
    try:
        session["search_results"] = search_listings(
            description=parsed["description"],
            size=parsed["size"],
            max_price=parsed["max_price"],
        )
    except Exception as e:
        session["error"] = (
            f"Something went wrong while searching listings ({type(e).__name__}). "
            "Please try again."
        )
        return session

    # No matches → halt early, do NOT call downstream tools on empty input.
    if not session["search_results"]:
        session["error"] = (
            "No listings matched your search. Try different keywords, a different "
            "size, or a higher price ceiling."
        )
        return session

    # Step 4: select the top (most relevant) result.
    session["selected_item"] = session["search_results"][0]

    # Step 5: suggest an outfit. An empty wardrobe is a success path (general
    # advice); only a tool error string halts the workflow here.
    outfit = suggest_outfit(session["selected_item"], wardrobe)
    if _is_tool_error(outfit):
        session["error"] = (
            "I found an item but couldn't generate outfit ideas right now. "
            "Please try again in a moment."
        )
        return session
    session["outfit_suggestion"] = outfit

    # Step 6: create the shareable fit card from the outfit + selected item.
    card = create_fit_card(session["outfit_suggestion"], session["selected_item"])
    if _is_tool_error(card):
        session["error"] = (
            "I styled an outfit but couldn't create a shareable fit card. "
            "Please try again in a moment."
        )
        return session
    session["fit_card"] = card

    # Step 7: success — return the completed session.
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Found: {session2['selected_item']}") # should be None
    print(f"\nOutfit: {session2['outfit_suggestion']}") # should be None
    print(f"\nFit card: {session2['fit_card']}") # should be None
    print(f"Error message: {session2['error']}")
