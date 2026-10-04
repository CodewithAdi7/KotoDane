from datetime import datetime, timezone

import db
import pytest
from db import create_or_tap_card, get_card_for_review, init_db
from review import answer_card, list_due_cards


@pytest.fixture
def review_database(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "review-test.db")
    init_db()
    card_ids = []
    for lemma in ("食べる", "飲む"):
        result = create_or_tap_card(
            lemma=lemma,
            reading="たべる" if lemma == "食べる" else "のむ",
            meaning="test meaning",
            sentence="テストです。",
        )
        card_ids.append(result["card"]["id"])
    return card_ids


def test_new_cards_are_due_immediately(review_database):
    due = list_due_cards(limit=20)
    assert {card["card_id"] for card in due} == set(review_database)
    assert all(card["due_at"] is None for card in due)
    assert all({"word", "reading", "meaning", "sentence", "image_path"} <= card.keys() for card in due)


def test_again_schedules_sooner_than_easy(review_database):
    again_id, easy_id = review_database
    reviewed_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    again = answer_card(again_id, 1, now=reviewed_at)
    easy = answer_card(easy_id, 4, now=reviewed_at)

    assert again is not None and easy is not None
    assert datetime.fromisoformat(again["due_at"]) < datetime.fromisoformat(easy["due_at"])


def test_answer_persists_fsrs_json_and_due_date(review_database):
    card_id = review_database[0]
    reviewed = answer_card(card_id, 3)

    stored = get_card_for_review(card_id)
    assert reviewed is not None
    assert stored["fsrs_state"]
    assert stored["due_at"] == reviewed["due_at"]
    assert card_id not in {card["card_id"] for card in list_due_cards(limit=20)}
