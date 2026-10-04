"""SQLite persistence for known kanji and vocabulary cards."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
from typing import Any, Iterator


DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "kotodane.db"
DB_PATH = Path(os.environ.get("KOTODANE_DB_PATH", DEFAULT_DB_PATH))

N5_KANJI = tuple(
    "日一国人年大十二本中長出三時行見月後前生五間上東四今金九入学"
    "高円子外八六下来気小七山話女北午百書先名川千水半男西電校語"
    "土木聞食車何南万毎白天母火右読友左休父雨魚"
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _connection() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db() -> None:
    """Create the local database and tables if they do not exist yet."""
    with _connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS known_kanji (
                kanji TEXT PRIMARY KEY,
                added_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lemma TEXT NOT NULL UNIQUE,
                reading TEXT NOT NULL,
                seen_count INTEGER NOT NULL DEFAULT 0,
                tap_count INTEGER NOT NULL DEFAULT 0,
                first_seen TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word_id INTEGER NOT NULL UNIQUE,
                sentence TEXT NOT NULL,
                meaning TEXT NOT NULL,
                image_path TEXT NULL,
                notes TEXT NOT NULL DEFAULT '',
                fsrs_state TEXT NULL,
                due_at TEXT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE
            );
            """
        )
        card_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(cards)").fetchall()
        }
        if "notes" not in card_columns:
            connection.execute("ALTER TABLE cards ADD COLUMN notes TEXT NOT NULL DEFAULT ''")


def get_known_kanji() -> list[str]:
    with _connection() as connection:
        rows = connection.execute(
            "SELECT kanji FROM known_kanji ORDER BY added_at, kanji"
        ).fetchall()
    return [row["kanji"] for row in rows]


def update_known_kanji(add: list[str], remove: list[str]) -> list[str]:
    now = _utc_now()
    with _connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.executemany(
            "DELETE FROM known_kanji WHERE kanji = ?",
            ((kanji,) for kanji in set(remove)),
        )
        connection.executemany(
            "INSERT OR IGNORE INTO known_kanji (kanji, added_at) VALUES (?, ?)",
            ((kanji, now) for kanji in dict.fromkeys(add)),
        )
        rows = connection.execute(
            "SELECT kanji FROM known_kanji ORDER BY added_at, kanji"
        ).fetchall()
    return [row["kanji"] for row in rows]


def seed_known_kanji() -> dict[str, int]:
    now = _utc_now()
    with _connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        before = connection.execute(
            "SELECT COUNT(*) FROM known_kanji"
        ).fetchone()[0]
        connection.executemany(
            "INSERT OR IGNORE INTO known_kanji (kanji, added_at) VALUES (?, ?)",
            ((kanji, now) for kanji in N5_KANJI),
        )
        total = connection.execute(
            "SELECT COUNT(*) FROM known_kanji"
        ).fetchone()[0]
    return {"added": total - before, "total": total}


def _card_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


_CARD_SELECT = """
    SELECT cards.id, cards.word_id, words.lemma, words.reading,
           words.seen_count, words.tap_count, words.first_seen,
           cards.sentence, cards.meaning, cards.image_path,
           cards.notes, cards.fsrs_state, cards.due_at, cards.created_at
    FROM cards JOIN words ON words.id = cards.word_id
"""


def get_cards() -> list[dict[str, Any]]:
    with _connection() as connection:
        rows = connection.execute(
            _CARD_SELECT + " ORDER BY cards.created_at DESC, cards.id DESC"
        ).fetchall()
    return [_card_from_row(row) for row in rows]


def get_due_cards(limit: int, now: str) -> list[dict[str, Any]]:
    """Return scheduled cards due by ``now``; unscheduled new cards are due now."""
    with _connection() as connection:
        rows = connection.execute(
            """SELECT cards.id AS card_id, words.lemma AS word, words.reading,
                      cards.meaning, cards.sentence, cards.image_path, cards.due_at
               FROM cards JOIN words ON words.id = cards.word_id
               WHERE cards.due_at IS NULL OR cards.due_at <= ?
               ORDER BY (cards.due_at IS NOT NULL), cards.due_at, cards.created_at
               LIMIT ?""",
            (now, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_card_for_review(card_id: int) -> dict[str, Any] | None:
    with _connection() as connection:
        row = connection.execute(
            _CARD_SELECT + " WHERE cards.id = ?", (card_id,)
        ).fetchone()
    return _card_from_row(row) if row is not None else None


def save_review_state(*, card_id: int, fsrs_state: str, due_at: str) -> bool:
    with _connection() as connection:
        cursor = connection.execute(
            "UPDATE cards SET fsrs_state = ?, due_at = ? WHERE id = ?",
            (fsrs_state, due_at, card_id),
        )
    return cursor.rowcount == 1


def create_or_tap_card(
    *, lemma: str, reading: str, meaning: str, sentence: str,
    image_path: str | None = None,
) -> dict[str, Any]:
    """Create one card per lemma, or count a repeat post as a tap."""
    now = _utc_now()
    with _connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        word = connection.execute(
            "SELECT id FROM words WHERE lemma = ?", (lemma,)
        ).fetchone()

        if word is None:
            cursor = connection.execute(
                """INSERT INTO words (lemma, reading, first_seen, tap_count)
                   VALUES (?, ?, ?, 1)""",
                (lemma, reading, now),
            )
            word_id = cursor.lastrowid
        else:
            word_id = word["id"]
            connection.execute(
                "UPDATE words SET tap_count = tap_count + 1 WHERE id = ?",
                (word_id,),
            )

        card = connection.execute(
            _CARD_SELECT + " WHERE cards.word_id = ?", (word_id,)
        ).fetchone()
        created = card is None
        if created:
            connection.execute(
                """INSERT INTO cards
                   (word_id, sentence, meaning, image_path, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (word_id, sentence, meaning, image_path, now),
            )
            card = connection.execute(
                _CARD_SELECT + " WHERE cards.word_id = ?", (word_id,)
            ).fetchone()
        elif image_path is not None:
            connection.execute(
                "UPDATE cards SET image_path = ? WHERE word_id = ?",
                (image_path, word_id),
            )
            card = connection.execute(
                _CARD_SELECT + " WHERE cards.word_id = ?", (word_id,)
            ).fetchone()

    return {"card": _card_from_row(card), "created": created}


def add_card_note(*, lemma: str, note: str) -> dict[str, Any] | None:
    """Append a unique example note to an existing vocabulary card."""
    cleaned_note = note.strip()
    if not cleaned_note:
        raise ValueError("A card note cannot be empty.")
    with _connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        card_row = connection.execute(
            _CARD_SELECT + " WHERE words.lemma = ?", (lemma,)
        ).fetchone()
        if card_row is None:
            return None
        existing = card_row["notes"] or ""
        notes = existing.splitlines()
        if cleaned_note not in notes:
            notes.append(cleaned_note)
            connection.execute(
                "UPDATE cards SET notes = ? WHERE id = ?",
                ("\n".join(notes), card_row["id"]),
            )
        updated = connection.execute(
            _CARD_SELECT + " WHERE cards.id = ?", (card_row["id"],)
        ).fetchone()
    return _card_from_row(updated)
