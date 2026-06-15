"""
Unit tests for Tool 3: create_fit_card (see planning.md, lines 262-264).

The Groq LLM client is mocked in every test so the suite is deterministic,
fast, and runs offline (no API key or network required). We patch
`tools._get_groq_client` — the internal dependency create_fit_card calls — so the
real function under test still executes its own guard, prompt-building, and
error-handling logic.
"""

from types import SimpleNamespace

import tools
from tools import create_fit_card


def _fake_client(reply="Here is a great caption.", capture=None):
    """
    Build a stand-in for the Groq client.

    Mirrors the shape create_fit_card relies on:
        client.chat.completions.create(...).choices[0].message.content

    If `capture` (a dict) is provided, the kwargs passed to create() are recorded
    so a test can assert what the tool actually sent to the LLM.
    """
    def create(*args, **kwargs):
        if capture is not None:
            capture.update(kwargs)
        message = SimpleNamespace(content=reply)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])

    completions = SimpleNamespace(create=create)
    chat = SimpleNamespace(completions=completions)
    return SimpleNamespace(chat=chat)


NEW_ITEM = {
    "id": "lst_001",
    "title": "Vintage Denim Jacket",
    "description": "A classic denim jacket with a worn-in look.",
    "category": "outerwear",
    "style_tags": ["vintage", "denim"],
    "colors": ["blue"],
    "size": "M",
    "price": 40,
    "platform": "ThriftApp",
}

OUTFIT = "Pair the jacket with your white tank and boots for a cool, casual vibe."
EMPTY_MESSAGE = "Sorry, I couldn't create a fit card for that outfit."


# 1. Successful Generation: valid outfit + populated item -> the tool calls the
#    LLM (correct model, elevated temperature, item details in the prompt) and
#    returns the caption string.
def test_create_fit_card_success(monkeypatch):
    capture = {}
    caption_reply = (
        "Obsessed with this Vintage Denim Jacket I scored on ThriftApp for $40! "
        "Styled it with a white tank and boots for an easy, cool vibe."
    )
    monkeypatch.setattr(
        tools, "_get_groq_client",
        lambda: _fake_client(caption_reply, capture),
    )

    caption = create_fit_card(OUTFIT, NEW_ITEM)

    assert isinstance(caption, str)
    assert caption.strip()                                  # non-empty caption
    assert caption == caption_reply                         # returns the LLM output
    assert capture["model"] == "llama-3.3-70b-versatile"    # really called the LLM
    assert capture["temperature"] >= 0.7                    # elevated for variety
    prompt_text = capture["messages"][0]["content"]
    assert "Vintage Denim Jacket" in prompt_text            # item details in prompt
    assert "ThriftApp" in prompt_text
    assert OUTFIT in prompt_text                            # outfit passed through


# 2. Empty/White-space Outfit Fallback: empty and whitespace-only outfits bypass
#    the LLM entirely, do not crash, and return the descriptive error string.
def test_create_fit_card_empty_outfit(monkeypatch):
    # If the LLM were ever reached, this would blow up — proving the guard runs
    # BEFORE any client call.
    def explode():
        raise AssertionError("LLM should not be called for an empty outfit")

    monkeypatch.setattr(tools, "_get_groq_client", explode)

    assert create_fit_card("", NEW_ITEM) == EMPTY_MESSAGE
    assert create_fit_card("   ", NEW_ITEM) == EMPTY_MESSAGE


# 3. LLM/API Failure Mode: the client raises a network exception -> the tool
#    catches it and returns a helpful error string instead of crashing.
def test_create_fit_card_llm_failure(monkeypatch):
    def raise_exception(*args, **kwargs):
        raise ConnectionError("Failed to connect to LLM API")

    failing_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=raise_exception)
        )
    )
    monkeypatch.setattr(tools, "_get_groq_client", lambda: failing_client)

    caption = create_fit_card(OUTFIT, NEW_ITEM)

    assert isinstance(caption, str)
    assert caption.startswith("Sorry, I ran into a problem creating the fit card")
    assert "ConnectionError" in caption
    assert "Please check your connection or API key and try again." in caption
