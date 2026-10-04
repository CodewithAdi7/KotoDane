from tokenizer import mask_text, to_hiragana


def test_to_hiragana_converts_katakana_and_preserves_other_characters():
    assert to_hiragana("カタカナーABC") == "かたかなーABC"


def test_example_masks_unknown_kanji_as_whole_words():
    tokens = mask_text("私は日本語を勉強しています", {"私", "日", "本"})

    assert "".join(token["display"] for token in tokens) == "私はにほんごをべんきょうしています"
    by_surface = {token["surface"]: token for token in tokens}
    assert by_surface["私"]["masked"] is False
    assert by_surface["日本語"]["masked"] is True
    assert by_surface["日本語"]["reading_hiragana"] == "にほんご"
    assert by_surface["勉強"]["display"] == "べんきょう"


def test_kana_punctuation_spaces_and_newlines_are_preserved():
    source = "かな！\nカナ。"
    tokens = mask_text(source, set())

    assert "".join(token["display"] for token in tokens) == "かな！\nカナ。"
    assert all(not token["masked"] for token in tokens)
