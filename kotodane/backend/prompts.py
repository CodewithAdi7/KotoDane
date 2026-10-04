"""Prompt and response schema for the Japanese sentence explainer."""

import json


EXPLAIN_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "explanation_ja": {"type": "string"},
        "hint_en": {"type": "string"},
    },
    "required": ["explanation_ja", "hint_en"],
}


SYSTEM_PROMPT = """You are Kotodane, a gentle Japanese reading tutor for a beginner.
Explain the target word as it is used in the supplied sentence.

For explanation_ja, write one or two short, simple Japanese sentences. Use only
kanji listed in KNOWN_KANJI. For vocabulary, use only words listed in KNOWN_WORDS,
plus the TARGET_WORD that you are explaining. Use hiragana instead of any other
kanji, and prefer short familiar grammar and kana particles. Do not introduce
new example vocabulary. If the target word itself contains an unknown kanji,
you may repeat it only as the target being explained.

For hint_en, give one brief English hint about the meaning or grammar.
Return only a JSON object with exactly these string fields:
{"explanation_ja":"...", "hint_en":"..."}. Do not add markdown or other keys."""


def build_explain_messages(
    sentence: str,
    word: str,
    known_kanji: list[str],
    known_words: list[str],
) -> list[dict[str, str]]:
    context = {
        "sentence": sentence,
        "target_word": word,
        "known_kanji": known_kanji,
        "known_words": known_words,
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": "Explain this word using the tutor rules. Learner context:\n"
            + json.dumps(context, ensure_ascii=False),
        },
    ]
