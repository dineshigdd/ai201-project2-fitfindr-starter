"""
Unit tests for Tool 2: suggest_outfit (see planning.md, lines 252-254).

The Groq LLM client is mocked in every test so the suite is deterministic,
fast, and runs offline (no API key or network required). We patch
`tools._get_groq_client` — the internal dependency suggest_outfit calls — so the
real function under test still executes its own prompt-building and error
handling logic.
"""

from types import SimpleNamespace

import tools
from tools import suggest_outfit


def _fake_client(reply="Here is a great outfit suggestion.", capture=None):
    """
    Build a stand-in for the Groq client.

    Mirrors the shape suggest_outfit relies on:
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
}

# Wardrobe items follow the real schema: keyed by `name`, not `title`.
POPULATED_WARDROBE = {
    "items": [
        {"id": "w_003", "name": "White ribbed tank top", "category": "tops",
         "colors": ["white"], "style_tags": ["basics", "minimal"]},
        {"id": "w_008", "name": "Black combat boots", "category": "shoes",
         "colors": ["black"], "style_tags": ["boots", "grunge"]},
    ]
}


# 1. Successful Generation: valid item + populated wardrobe -> the tool calls the
#    LLM (correct model + named wardrobe pieces) and returns a non-empty string.
def test_suggest_outfit_success(monkeypatch):
    capture = {}
    monkeypatch.setattr(
        tools, "_get_groq_client",
        lambda: _fake_client("Pair the jacket with your white tank and boots.", capture),
    )

    result = suggest_outfit(NEW_ITEM, POPULATED_WARDROBE)

    assert isinstance(result, str)
    assert result.strip()                                   # non-empty
    assert capture["model"] == "llama-3.3-70b-versatile"    # really called the LLM
    prompt_text = capture["messages"][0]["content"]
    assert "Vintage Denim Jacket" in prompt_text            # new item in prompt
    assert "White ribbed tank top" in prompt_text           # wardrobe named by piece
    assert "Black combat boots" in prompt_text


# 2. Empty Wardrobe Fallback: empty wardrobe -> does not crash, still returns a
#    non-empty string, and routes through the general-advice prompt branch.
def test_suggest_outfit_empty_wardrobe(monkeypatch):
    capture = {}
    monkeypatch.setattr(
        tools, "_get_groq_client",
        lambda: _fake_client("This piece suits a casual vibe and pairs well with denim.", capture),
    )

    result = suggest_outfit(NEW_ITEM, {"items": []})

    assert isinstance(result, str)
    assert result.strip()                                   # non-empty fallback
    prompt_text = capture["messages"][0]["content"].lower()
    assert "general styling advice" in prompt_text          # used the empty branch
    assert "Vintage Denim Jacket".lower() in prompt_text    # still describes the item


# 3. LLM/API Failure Mode: the client raises -> the tool catches it and returns a
#    helpful error string instead of propagating the exception.
def test_suggest_outfit_llm_failure(monkeypatch):
    def boom():
        raise Exception("LLM API failure")

    monkeypatch.setattr(tools, "_get_groq_client", boom)

    # Must not raise — the tool is responsible for handling the failure.
    result = suggest_outfit(NEW_ITEM, POPULATED_WARDROBE)

    assert isinstance(result, str)
    assert result.strip()
    assert "sorry" in result.lower() or "problem" in result.lower()
