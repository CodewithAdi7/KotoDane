"""FSRS scheduling helpers for saved vocabulary cards."""

from __future__ import annotations

from datetime import datetime, timezone
import json

from fsrs import Card as FsrsCard
from fsrs import Rating, Scheduler

from db import get_card_for_review, get_due_cards, save_review_state


_scheduler = Scheduler(enable_fuzzing=False)


def list_due_cards(limit: int = 20) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    return get_due_cards(limit=limit, now=now)


def answer_card(card_id: int, rating: int, *, now: datetime | None = None) -> dict | None:
    """Apply an FSRS rating and persist the card state and next due date."""
    row = get_card_for_review(card_id)
    if row is None:
        return None

    review_time = now or datetime.now(timezone.utc)
    if review_time.tzinfo is None or review_time.utcoffset() != timezone.utc.utcoffset(review_time):
        raise ValueError("Review timestamps must be timezone-aware UTC values.")

    try:
        fsrs_card = (
            FsrsCard(card_id=card_id)
            if not row["fsrs_state"]
            else FsrsCard.from_json(row["fsrs_state"])
        )
        if fsrs_card.card_id != card_id:
            raise ValueError("Stored FSRS card ID does not match its database card.")
        rating_value = Rating(rating)
        updated_card, _review_log = _scheduler.review_card(
            fsrs_card,
            rating_value,
            review_datetime=review_time,
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not schedule this card: {exc}") from exc

    due_at = updated_card.due.isoformat()
    if not save_review_state(
        card_id=card_id,
        fsrs_state=updated_card.to_json(),
        due_at=due_at,
    ):
        return None

    return {
        "card_id": card_id,
        "rating": int(rating_value),
        "due_at": due_at,
        "state": int(updated_card.state),
    }
