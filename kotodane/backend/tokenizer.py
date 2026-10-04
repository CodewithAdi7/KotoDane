"""Japanese tokenization and beginner-friendly kanji masking."""

from __future__ import annotations

import re
from typing import Any

from fugashi import Tagger


_tagger = Tagger()
_whitespace = re.compile(r"(\s+)")
# UniDic splits 日本語 into 日本 + 語 and selects ニッポン for 日本. This
# common compound is conventionally read にほんご in beginner material.
_compound_readings = {"日本語": "にほんご"}


def to_hiragana(katakana_str: str) -> str:
    """Convert standard katakana characters to hiragana, preserving others."""
    converted: list[str] = []
    for char in katakana_str:
        codepoint = ord(char)
        if 0x30A1 <= codepoint <= 0x30F6:
            converted.append(chr(codepoint - 0x60))
        else:
            converted.append(char)
    return "".join(converted)


def _is_kanji(char: str) -> bool:
    codepoint = ord(char)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0x20000 <= codepoint <= 0x3134F
    )


def _make_token(surface: str, lemma: str, reading: str, pos: str,
                known_kanji: set[str]) -> dict[str, Any]:
    reading_hiragana = to_hiragana(reading)
    has_unknown_kanji = any(
        _is_kanji(char) and char not in known_kanji for char in surface
    )
    return {
        "surface": surface,
        "lemma": lemma,
        "reading_hiragana": reading_hiragana,
        "display": reading_hiragana if has_unknown_kanji and reading_hiragana else surface,
        "masked": has_unknown_kanji,
        "pos": pos,
    }


def _tokenize_segment(text: str, known_kanji: set[str]) -> list[dict[str, Any]]:
    parsed = list(_tagger(text))
    output: list[dict[str, Any]] = []
    index = 0

    while index < len(parsed):
        token = parsed[index]
        surface = token.surface
        feature = token.feature
        lemma = getattr(feature, "lemma", None) or surface
        reading = getattr(feature, "kana", None) or ""
        pos = getattr(feature, "pos1", None) or ""

        # UniDic may split a written compound into adjacent noun tokens (e.g.
        # 日本 + 語). Treat consecutive kanji nouns as one word for masking.
        if pos == "名詞" and any(_is_kanji(c) for c in surface):
            parts = [token]
            next_index = index + 1
            while next_index < len(parsed):
                following = parsed[next_index]
                following_pos = getattr(following.feature, "pos1", None)
                if (following_pos != "名詞"
                        or not any(_is_kanji(c) for c in following.surface)):
                    break
                parts.append(following)
                next_index += 1

            if len(parts) > 1:
                surface = "".join(part.surface for part in parts)
                lemma = "".join(
                    getattr(part.feature, "lemma", None) or part.surface
                    for part in parts
                )
                reading = "".join(
                    getattr(part.feature, "kana", None) or "" for part in parts
                )
                index = next_index
            else:
                index += 1
        else:
            index += 1

        token_reading = _compound_readings.get(surface, to_hiragana(reading))
        output.append(_make_token(surface, lemma, token_reading, pos, known_kanji))

    return output


def mask_text(text: str, known_kanji: set[str]) -> list[dict[str, Any]]:
    """Tokenize text and mask any whole word containing an unknown kanji.

    Whitespace runs are emitted verbatim as tokens so spaces and newlines are
    retained when callers join the returned ``display`` values.
    """
    if not text:
        return []

    tokens: list[dict[str, Any]] = []
    for segment in _whitespace.split(text):
        if not segment:
            continue
        if segment.isspace():
            tokens.append({
                "surface": segment,
                "lemma": segment,
                "reading_hiragana": segment,
                "display": segment,
                "masked": False,
                "pos": "空白",
            })
        else:
            tokens.extend(_tokenize_segment(segment, known_kanji))
    return tokens
