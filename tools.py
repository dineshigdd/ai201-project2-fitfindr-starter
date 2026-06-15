"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def _size_matches(query: str | None, item_size: str) -> bool:
    """
    Case-insensitive size match between a requested size and a listing's size.

    Both strings are split into tokens on spaces, slashes, and parentheses, and
    every token in the query must be present in the listing. This honors the
    spec examples (e.g. "M" matches "S/M" or "M/L", and multi-token queries like
    "US 8.5" or "XL (oversized)" match their listings) while avoiding the
    false positives a plain substring check would cause (e.g. "S" must NOT match
    "US 7" or "One Size").
    """
    if query is None:
        return True

    def _tokens(s: str) -> set[str]:
        return {t for t in re.split(r"[\s/()]+", s.lower()) if t}

    query_tokens = _tokens(query)
    if not query_tokens:        # whitespace-only query → treat as no size filter
        return True
    return query_tokens <= _tokens(item_size)


def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings() in data_loader.py.
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    
    item_list = load_listings()

    # Filter by optional price ceiling and optional size.
    item_list = [item for item in item_list if max_price is None or item["price"] <= max_price]
    item_list = [item for item in item_list if _size_matches(size, item["size"])]

    # Score by keyword overlap with the description, drop non-matches (score 0),
    # and sort by score (highest first). Scores are kept in a side list so the
    # returned listing dicts stay clean — no extra "score" key is added.
    if description:
        keywords = description.lower().split()
        scored = []
        for item in item_list:
            haystack = (item["title"] + " " + item["description"]).lower()
            score = sum(1 for kw in keywords if kw in haystack)
            if score > 0:
                scored.append((score, item))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        item_list = [item for _, item in scored]

    return item_list


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    # Describe the new item once; reused in both prompt branches.
    item_desc = (
        f"- Title: {new_item.get('title', 'unknown item')}\n"
        f"- Category: {new_item.get('category', 'n/a')}\n"
        f"- Style tags: {', '.join(new_item.get('style_tags', [])) or 'n/a'}\n"
        f"- Colors: {', '.join(new_item.get('colors', [])) or 'n/a'}\n"
        f"- Description: {new_item.get('description', 'n/a')}"
    )

    items = wardrobe.get("items") or []

    if not items:
        # Empty wardrobe → general styling advice (no specific pieces to name).
        prompt = (
            "You are a friendly personal stylist helping someone who just found a "
            "secondhand item but hasn't told you anything about their existing wardrobe.\n\n"
            f"The item they're considering:\n{item_desc}\n\n"
            "Give general styling advice for this piece: what kinds of items pair well "
            "with it, what vibe or occasions it suits, and how to build a versatile look "
            "around it. Keep it warm and concise (2-3 short paragraphs). Do not invent "
            "specific items the person owns."
        )
    else:
        # Populated wardrobe → suggest concrete outfits using named pieces.
        wardrobe_lines = []
        for w in items:
            tags = ", ".join(w.get("style_tags", [])) or "n/a"
            colors = ", ".join(w.get("colors", [])) or "n/a"
            notes = w.get("notes")
            line = (
                f"- {w.get('name', 'unnamed piece')} "
                f"({w.get('category', 'n/a')}; colors: {colors}; style: {tags})"
            )
            if notes:
                line += f" — {notes}"
            wardrobe_lines.append(line)
        wardrobe_text = "\n".join(wardrobe_lines)

        prompt = (
            "You are a friendly personal stylist. Suggest 1-2 complete outfits that pair "
            "a newly found secondhand item with pieces the person already owns.\n\n"
            f"New item:\n{item_desc}\n\n"
            f"The person's wardrobe:\n{wardrobe_text}\n\n"
            "Suggest 1-2 complete outfits. Each outfit must combine the new item with "
            "SPECIFIC pieces named from the wardrobe above (refer to them by name). "
            "Briefly explain why each combination works. Keep it warm and concise."
        )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        suggestion = response.choices[0].message.content.strip()
        if not suggestion:
            return (
                "Sorry, I couldn't come up with an outfit suggestion right now. "
                "Please try again."
            )
        return suggestion
    except Exception as e:
        return (
            "Sorry, I ran into a problem generating outfit suggestions "
            f"({type(e).__name__}). Please check your connection or API key and try again."
        )



# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit: The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A short (≤ 2 sentence, ~30 word) string usable as an Instagram/TikTok
        caption. If outfit is empty or missing, return a descriptive error
        message string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    if not outfit or outfit.strip() == "":
        return "Sorry, I couldn't create a fit card for that outfit."

    title = new_item.get("title", "thrifted find")
    price = new_item.get("price", "unknown price")
    platform = new_item.get("platform", "a thrift app")

    prompt = (
        "You're writing a short, shareable caption for an Instagram/TikTok OOTD post "
        "about a secondhand find. Write the caption based on these details:\n\n"
        f"Item: {title}\n"
        f"Price: ${price}\n"
        f"Bought on: {platform}\n"
        f"Outfit: {outfit}\n\n"
        "Guidelines for the caption:\n"
        "- Keep it SHORT: 2 sentences max, about 30 words total. This is a quick "
        "social caption, not a paragraph.\n"
        "- Casual and authentic, like a real OOTD post — NOT a product description.\n"
        f"- Mention the item name ({title}), the price (${price}), and the platform "
        f"({platform}) naturally, each exactly once.\n"
        "- If the outfit lists more than one look, pick just ONE and capture its "
        "vibe in a few specific words — do not describe multiple outfits.\n"
        "Return only the caption text — no hashtags-only filler, no preamble, no quotes."
    )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_completion_tokens=90,
        )
        caption = response.choices[0].message.content.strip()
        if not caption:
            return "Sorry, I couldn't create a fit card for that outfit."
        return caption  
    except Exception as e:
        return (
            "Sorry, I ran into a problem creating the fit card "
            f"({type(e).__name__}). Please check your connection or API key and try again."
        )
     
