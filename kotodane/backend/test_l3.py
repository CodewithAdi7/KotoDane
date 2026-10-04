import pytest

import llm
from guardrail import generate_within_level


def test_practice_generation_retries_for_unknown_kanji():
    attempts = iter([
        {
            "sentences": [
                {"sentence": "猫が食べる。", "hint_en": "The cat eats."},
                {"sentence": "猫は食べる。", "hint_en": "The cat eats."},
                {"sentence": "猫も食べる。", "hint_en": "The cat eats too."},
            ]
        },
        {
            "sentences": [
                {"sentence": "私は食べる。", "hint_en": "I eat."},
                {"sentence": "水を飲む。", "hint_en": "Drink water."},
                {"sentence": "りんごを食べる。", "hint_en": "Eat an apple."},
            ]
        },
    ])
    feedback = []

    def task_fn(avoid):
        feedback.append(avoid)
        return next(attempts)

    result = generate_within_level(
        task_fn,
        known_kanji=["私", "食", "水", "飲"],
        known_words=["私", "食べる", "水", "飲む", "りんご"],
    )

    assert result["tries"] == 2
    assert result["passed"] is True
    assert len(result["sentences"]) == 3
    assert "avoid: 猫" in feedback[1]


def test_practice_output_validation_reports_wrong_count(monkeypatch):
    monkeypatch.setattr(
        llm,
        "_chat_json",
        lambda *_args, **_kwargs: {"sentences": [{"sentence": "水を飲む。", "hint_en": "Drink."}]},
    )

    with pytest.raises(llm.OllamaResponseError, match="exactly 3 sentences"):
        llm.generate_practice("飲む", ["水"], ["水", "飲む"], count=3)


def test_casual_output_validation_reports_missing_hint(monkeypatch):
    monkeypatch.setattr(
        llm,
        "_chat_json",
        lambda *_args, **_kwargs: {"explanation_ja": "しらない の みじかい いいかた。"},
    )

    with pytest.raises(llm.OllamaResponseError, match="hint_en"):
        llm.explain_casual("知らねえよ", ["知"], [])
