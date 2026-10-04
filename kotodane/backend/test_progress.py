import db
from db import create_or_tap_card, init_db, update_known_kanji
from progress import get_dashboard_stats, render_and_log, suggest_kanji


def test_render_history_tracks_visible_kanji(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "progress.db")
    init_db()

    result = render_and_log("日 一", ["日"])

    assert result["tokens"][0]["display"] == "日"
    stats = get_dashboard_stats()
    assert stats["latest_kanji_shown_percent"] == 50.0


def test_suggestions_rank_unknown_kanji_from_saved_cards(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "suggestions.db")
    init_db()
    update_known_kanji(["猫"], [])
    create_or_tap_card(
        lemma="猫",
        reading="ねこ",
        meaning="cat",
        sentence="猫を見る。猫がいる。",
    )
    create_or_tap_card(
        lemma="見る",
        reading="みる",
        meaning="to see",
        sentence="犬が見る。",
    )

    result = suggest_kanji(["猫"])

    assert result["suggestions"][0] == {
        "kanji": "見",
        "frequency": 3,
        "example_words": ["猫", "見る"],
    }
    assert all(item["kanji"] != "猫" for item in result["suggestions"])


def test_dashboard_counts_known_words_cards_and_due(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "stats.db")
    init_db()
    update_known_kanji(["日", "本"], [])
    create_or_tap_card(
        lemma="猫",
        reading="ねこ",
        meaning="cat",
        sentence="猫がいる。",
    )
    create_or_tap_card(
        lemma="見る",
        reading="みる",
        meaning="to see",
        sentence="犬を見る。",
    )

    stats = get_dashboard_stats()

    assert stats["known_kanji_count"] == 2
    assert stats["words_met"] == 2
    assert stats["cards_total"] == 2
    assert stats["cards_due"] == 2
    assert stats["latest_kanji_shown_percent"] is None
