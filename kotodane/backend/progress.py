"""Render history and study dashboard calculations."""

from __future__ import annotations

from datetime import datetime, timezone

from db import get_dashboard_counts, get_latest_render, get_saved_card_texts, record_render
from tokenizer import mask_text


def _is_kanji(char: str) -> bool:
    codepoint = ord(char)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0x20000 <= codepoint <= 0x3134F
    )


def render_and_log(text: str, known_kanji: list[str]) -> dict:
    tokens = mask_text(text, set(known_kanji))
    kanji_total = 0
    kanji_shown = 0
    for token in tokens:
        visible_kanji = [char for char in token["surface"] if _is_kanji(char)]
        kanji_total += len(visible_kanji)
        if not token["masked"]:
            kanji_shown += len(visible_kanji)
    percentage = round(100 * kanji_shown / kanji_total, 1) if kanji_total else 100.0
    record_render(
        kanji_total=kanji_total,
        kanji_shown=kanji_shown,
        kanji_shown_percent=percentage,
    )
    return {"tokens": tokens}


def suggest_kanji(known_kanji: list[str], limit: int = 10) -> dict:
    known = set(known_kanji)
    frequencies: dict[str, int] = {}
    examples: dict[str, set[str]] = {}
    for card in get_saved_card_texts():
        word = card["word"]
        sentence = card["sentence"] or ""
        for char in (*word, *sentence):
            if _is_kanji(char) and char not in known:
                frequencies[char] = frequencies.get(char, 0) + 1
                examples.setdefault(char, set()).add(word)

    ranked = sorted(frequencies, key=lambda char: (-frequencies[char], char))[:limit]
    return {
        "suggestions": [
            {
                "kanji": char,
                "frequency": frequencies[char],
                "example_words": sorted(examples[char])[:3],
            }
            for char in ranked
        ]
    }


def get_dashboard_stats() -> dict:
    now = datetime.now(timezone.utc).isoformat()
    latest = get_latest_render()
    return {
        **get_dashboard_counts(now),
        "latest_kanji_shown_percent": (
            latest["kanji_shown_percent"] if latest is not None else None
        ),
    }
