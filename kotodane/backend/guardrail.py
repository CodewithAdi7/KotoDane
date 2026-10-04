"""Level checks and retry loop for learner-facing Japanese output."""

from collections.abc import Callable
from typing import Any

from tokenizer import _is_kanji, mask_text


_KANA_RANGES = (
    (0x3040, 0x309F),  # hiragana
    (0x30A0, 0x30FF),  # katakana, including the long-vowel mark
    (0x31F0, 0x31FF),  # katakana phonetic extensions
    (0x1B000, 0x1B16F),  # kana supplement and extended kana
)


def _is_kana_only(text: str) -> bool:
    return bool(text) and all(
        any(start <= ord(char) <= end for start, end in _KANA_RANGES)
        for char in text
    )


def check_level(
    text: str,
    known_kanji: set[str] | list[str],
    known_words: set[str] | list[str],
) -> dict[str, Any]:
    """Return unknown kanji and vocabulary found in Japanese output text.

    Particles, punctuation/whitespace, and words written only in kana are
    treated as known. Vocabulary containing kanji is allowed when either its
    surface form or lemma occurs in ``known_words``.
    """
    kanji_set = set(known_kanji)
    word_set = {word.strip() for word in known_words if word.strip()}
    tokens = mask_text(text, kanji_set)

    unknown_kanji = sorted({
        char
        for token in tokens
        for char in token["surface"]
        if _is_kanji(char) and char not in kanji_set
    })

    candidates: list[dict[str, Any]] = []
    unknown_words: set[str] = set()
    violating_surfaces: set[str] = set()
    for token in tokens:
        surface = token["surface"]
        pos = token["pos"]
        if not surface.strip() or pos in {"助詞", "補助記号", "空白"}:
            continue
        if _is_kana_only(surface):
            continue

        candidates.append(token)
        token_has_unknown_kanji = any(
            _is_kanji(char) and char not in kanji_set for char in surface
        )
        is_known_word = surface in word_set or token["lemma"] in word_set
        if token_has_unknown_kanji or not is_known_word:
            violating_surfaces.add(surface)
            if not is_known_word:
                unknown_words.add(surface)

    unknown_ratio = len(violating_surfaces) / len(candidates) if candidates else 0.0
    return {
        "ok": not unknown_kanji and not unknown_words,
        "unknown_kanji": unknown_kanji,
        "unknown_words": sorted(unknown_words),
        "unknown_ratio": unknown_ratio,
    }


def generate_within_level(
    task_fn: Callable[[str], Any],
    known_kanji: set[str] | list[str],
    known_words: set[str] | list[str],
    max_tries: int = 3,
    max_unknown_ratio: float = 0.1,
) -> dict[str, Any]:
    """Generate, check, and retry with explicit feedback when output is too hard.

    ``task_fn`` receives an empty string on the first call, then an ``avoid:``
    hint containing vocabulary or kanji from failed attempts. It may return
    either a Japanese string or a mapping with an ``explanation_ja`` field.
    """
    attempts = max(1, max_tries)
    feedback = ""
    best_result: Any = None
    best_check: dict[str, Any] | None = None
    best_score: tuple[int, float, int] | None = None

    for attempt in range(1, attempts + 1):
        result = task_fn(feedback)
        text = result.get("explanation_ja", "") if isinstance(result, dict) else str(result)
        level = check_level(text, known_kanji, known_words)
        passed = (
            not level["unknown_kanji"]
            and level["unknown_ratio"] <= max_unknown_ratio
        )

        # Prefer a candidate without unknown kanji, then the lowest unknown ratio.
        score = (
            1 if level["unknown_kanji"] else 0,
            level["unknown_ratio"],
            len(level["unknown_words"]),
        )
        if best_score is None or score < best_score:
            best_result, best_check, best_score = result, level, score

        if passed:
            best_result, best_check = result, level
            return {
                **best_result,
                "tries": attempt,
                "unknown_ratio": level["unknown_ratio"],
                "passed": True,
            } if isinstance(best_result, dict) else {
                "text": best_result,
                "tries": attempt,
                "unknown_ratio": level["unknown_ratio"],
                "passed": True,
            }

        offending = sorted(set(level["unknown_kanji"] + level["unknown_words"]))
        avoid = "、".join(offending) if offending else "unknown vocabulary"
        feedback = f"avoid: {avoid}. Use kana or known vocabulary instead."

    assert best_check is not None
    response = dict(best_result) if isinstance(best_result, dict) else {"text": best_result}
    response.update({
        "tries": attempts,
        "unknown_ratio": best_check["unknown_ratio"],
        "passed": False,
    })
    return response
