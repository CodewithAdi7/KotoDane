from guardrail import check_level, generate_within_level


def test_known_level_japanese_passes():
    result = check_level("私はここにいます。", ["私"], ["私"])

    assert result == {
        "ok": True,
        "unknown_kanji": [],
        "unknown_words": [],
        "unknown_ratio": 0.0,
    }


def test_unknown_kanji_retries_then_passes():
    replies = iter([
        {"explanation_ja": "猫はいます。", "hint_en": "A cat is there."},
        {"explanation_ja": "私はいます。", "hint_en": "I am here."},
    ])
    feedbacks = []

    def task_fn(feedback):
        feedbacks.append(feedback)
        return next(replies)

    result = generate_within_level(task_fn, ["私"], ["私"])

    assert result["tries"] == 2
    assert result["passed"] is True
    assert result["unknown_ratio"] == 0.0
    assert "avoid: 猫" in feedbacks[1]


def test_always_failing_returns_best_attempt():
    replies = iter([
        {"explanation_ja": "猫です。", "hint_en": "A cat."},
        {"explanation_ja": "犬です。", "hint_en": "A dog."},
        {"explanation_ja": "鳥です。", "hint_en": "A bird."},
    ])

    result = generate_within_level(lambda _feedback: next(replies), [], [], max_tries=3)

    assert result["explanation_ja"] == "猫です。"
    assert result["tries"] == 3
    assert result["unknown_ratio"] == 1.0
    assert result["passed"] is False
