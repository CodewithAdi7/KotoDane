"""Local JMdict and KANJIDIC2 lookups backed by Jamdict."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from jamdict import Jamdict


_COMMON_PRIORITY_PREFIXES = ("ichi", "news", "spec", "gai")


@lru_cache(maxsize=1)
def get_jamdict() -> Jamdict:
    """Create and retain one Jamdict instance for this application process."""
    return Jamdict()


def _is_kanji(char: str) -> bool:
    codepoint = ord(char)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0x20000 <= codepoint <= 0x3134F
    )


def _entry_is_common(entry: Any) -> bool:
    forms = [*entry.kanji_forms, *entry.kana_forms]
    priorities = (priority for form in forms for priority in form.pri)
    return any(
        priority.startswith(_COMMON_PRIORITY_PREFIXES)
        or priority.startswith("nf")
        for priority in priorities
    )


def _serialize_entry(entry: Any) -> dict[str, Any]:
    return {
        "kanji_forms": [form.text for form in entry.kanji_forms],
        "kana_forms": [form.text for form in entry.kana_forms],
        "senses": [
            {
                "pos": list(sense.pos),
                "glosses": [gloss.text for gloss in sense.gloss],
            }
            for sense in entry.senses
        ],
        "common": _entry_is_common(entry),
    }


def _serialize_kanji(character: Any) -> dict[str, Any]:
    readings = [
        reading
        for group in character.rm_groups
        for reading in group.readings
    ]
    return {
        "char": character.literal,
        "meanings": character.meanings(english_only=True),
        "onyomi": list(dict.fromkeys(
            reading.value for reading in readings if reading.r_type == "ja_on"
        )),
        "kunyomi": list(dict.fromkeys(
            reading.value for reading in readings if reading.r_type == "ja_kun"
        )),
        "strokes": character.stroke_count,
    }


def lookup_word(word: str) -> dict[str, Any]:
    """Return exact JMdict matches and KANJIDIC2 data for kanji in ``word``."""
    if not word:
        return {"query": word, "found": False, "entries": [], "kanji": []}

    result = get_jamdict().lookup(word, strict_lookup=True)
    entries = [_serialize_entry(entry) for entry in result.entries]
    entries.sort(key=lambda entry: not entry["common"])
    entries = entries[:5]

    kanji_order = list(dict.fromkeys(char for char in word if _is_kanji(char)))
    found_chars = {character.literal: character for character in result.chars}
    jam = get_jamdict()
    kanji: list[dict[str, Any]] = []
    for char in kanji_order:
        character = found_chars.get(char)
        if character is None:
            char_result = jam.lookup(char, strict_lookup=True)
            character = next(
                (item for item in char_result.chars if item.literal == char), None
            )
        if character is not None:
            kanji.append(_serialize_kanji(character))

    return {
        "query": word,
        "found": bool(entries or kanji),
        "entries": entries,
        "kanji": kanji,
    }
