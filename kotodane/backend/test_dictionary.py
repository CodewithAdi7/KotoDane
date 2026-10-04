"""Small manual smoke test for the Jamdict integration."""

import json
import sys

from dictionary import lookup_word


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> None:
    eating = lookup_word("食べる")
    assert eating["found"]
    assert any("たべる" in entry["kana_forms"] for entry in eating["entries"])
    assert any(
        "to eat" in gloss
        for entry in eating["entries"]
        for sense in entry["senses"]
        for gloss in sense["glosses"]
    )

    language = lookup_word("語")
    assert language["found"]
    assert any(item["char"] == "語" for item in language["kanji"])

    missing = lookup_word("zz_not_a_word_zz")
    assert missing == {
        "query": "zz_not_a_word_zz",
        "found": False,
        "entries": [],
        "kanji": [],
    }

    print(json.dumps({"食べる": eating, "語": language, "missing": missing},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
