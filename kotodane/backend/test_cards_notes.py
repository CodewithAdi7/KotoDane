from pathlib import Path
from uuid import uuid4

import db


def test_card_examples_are_persistent_and_deduplicated(monkeypatch):
    test_db = Path.cwd() / f"cards-{uuid4().hex}.tmp.db"
    monkeypatch.setattr(db, "DB_PATH", test_db)
    try:
        db.init_db()
        db.create_or_tap_card(
            lemma="食べる",
            reading="たべる",
            meaning="to eat",
            sentence="私は食べる。",
        )

        first = db.add_card_note(lemma="食べる", note="りんごを食べる。")
        duplicate = db.add_card_note(lemma="食べる", note="りんごを食べる。")

        assert first["notes"] == "りんごを食べる。"
        assert duplicate["notes"] == "りんごを食べる。"
        assert db.get_cards()[0]["notes"] == "りんごを食べる。"
    finally:
        test_db.unlink(missing_ok=True)
