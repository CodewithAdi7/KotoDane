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

PRACTICE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "sentences": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "sentence": {"type": "string"},
                    "hint_en": {"type": "string"},
                },
                "required": ["sentence", "hint_en"],
            },
        }
    },
    "required": ["sentences"],
}

CASUAL_JSON_SCHEMA = EXPLAIN_JSON_SCHEMA


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
    feedback: str | None = None,
) -> list[dict[str, str]]:
    context = {
        "sentence": sentence,
        "target_word": word,
        "known_kanji": known_kanji,
        "known_words": known_words,
    }
    user_content = "Explain this word using the tutor rules. Learner context:\n" + json.dumps(
        context, ensure_ascii=False
    )
    if feedback:
        user_content += (
            "\nYour previous answer was too difficult. Follow this correction exactly: "
            + feedback
        )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


PRACTICE_SYSTEM_PROMPT = """You are Kotodane, a gentle Japanese reading tutor for a beginner.
Create the requested number of short, natural example sentences using the target
word. Build them mostly from KNOWN_WORDS and use only kanji from KNOWN_KANJI.
Kana-only words, particles, and punctuation are fine; write unfamiliar content
in kana rather than introducing new kanji. Keep each sentence simple and give
it one brief English meaning hint. Use the target word in every sentence.
Return only JSON matching this shape:
{"sentences":[{"sentence":"...","hint_en":"..."}]}"""


def build_practice_messages(
    word: str,
    known_kanji: list[str],
    known_words: list[str],
    count: int,
    feedback: str | None = None,
) -> list[dict[str, str]]:
    context = {
        "target_word": word,
        "known_kanji": known_kanji,
        "known_words": known_words,
        "sentence_count": count,
    }
    user_content = "Make the requested Japanese practice sentences. Context:\n" + json.dumps(
        context, ensure_ascii=False
    )
    if feedback:
        user_content += "\nRevise the previous response and follow this correction: " + feedback
    return [
        {"role": "system", "content": PRACTICE_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


CASUAL_SYSTEM_PROMPT = """You are Kotodane, a Japanese tutor for a beginner.
The explanation_ja value MUST be written only in Japanese. Never write English
or romaji in explanation_ja; English belongs only in hint_en.

Explain the casual or spoken forms that actually occur in the sentence. State
the usual standard form and briefly explain the tone or use. For contractions
such as 知らねえ or 食べてる, compare them with 知らない or 食べている. For
endings such as ぜ, わ, or じゃん, explain only the ending present in the input.
Use simple Japanese and one or two short sentences. Use only kanji in
KNOWN_KANJI and vocabulary in KNOWN_WORDS or the supplied sentence. For every
other word, write it in hiragana instead of using unfamiliar vocabulary or
kanji. Prefer simple patterns such as 「X」は「Y」とおなじいみです and
「X」は「Y」をもっとカジュアルにしたことばです. A word in the supplied
sentence is the subject being explained and may be quoted. Tone can depend on
context; do not make universal claims about who uses an ending.

Return one JSON object with exactly two string fields. explanation_ja must be
Japanese only. hint_en must be one short English hint.
{"explanation_ja":"『知らねえ』は『知らない』のくだけた言い方です。","hint_en":"Casual form of 'I don't know'."}"""


def build_casual_messages(
    sentence: str,
    known_kanji: list[str],
    known_words: list[str],
    feedback: str | None = None,
) -> list[dict[str, str]]:
    context = {
        "sentence": sentence,
        "known_kanji": known_kanji,
        "known_words": known_words,
    }
    user_content = "次の文にあるくだけた話し方を、学習者向けに日本語で説明してください。入力情報:\n" + json.dumps(
        context, ensure_ascii=False
    )
    if feedback:
        user_content += "\nRevise the previous response and follow this correction: " + feedback
    return [
        {"role": "system", "content": CASUAL_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
