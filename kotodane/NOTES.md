# Kotodane Notes

## Summary

Local-first Japanese reading tutor for a beginner learner. Phase 0 established the project structure; Phase 1 added Japanese tokenization and kanji-aware rendering; Phase 2 added local dictionary lookup; Phase 3 adds persistent known-kanji and vocabulary-card endpoints.

## Stack

- Python 3.13.7, FastAPI, SQLite
- fugashi with unidic-lite for Japanese tokenization
- jamdict and jamdict-data for dictionary lookup
- React and Vite (JavaScript) frontend
- Planned local AI: manga-ocr for reading, Ollama with a local open-weight LLM for teaching, and Whisper for listening

## Structure

```text
kotodane/
├── backend/
│   ├── check_setup.py
│   ├── db.py  (SQLite schema and persistence)
│   ├── dictionary.py
│   ├── llm.py
│   ├── main.py
│   ├── requirements.txt
│   ├── test_dictionary.py
│   ├── test_tokenizer.py
│   └── tokenizer.py
├── frontend/  (empty in Phase 0)
├── .gitignore
├── LICENSE
└── NOTES.md
```

## How to run

From a PowerShell terminal, enter `kotodane\backend`, create and activate a virtual environment, and install the listed requirements:

```powershell
cd kotodane\backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Start the API from `backend`:

```powershell
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000/docs` for Swagger UI and `http://127.0.0.1:8000/health` for the health response. In another terminal with the same virtual environment active, run:

```powershell
python check_setup.py
```

Phase 1 adds `POST /render`, which accepts `{"text": "...", "known_kanji": ["私"]}` and returns tokenizer results. Run tokenizer tests from `backend` with `python -m pytest test_tokenizer.py` (install `pytest` in the virtual environment if needed).

Phase 2 adds `GET /lookup?word=食べる` for exact local dictionary lookup. Run `python test_dictionary.py` from `backend` to check word and kanji results.

Phase 3 creates `kotodane.db` in the project folder on first API startup. Use `GET /known-kanji`, `PUT /known-kanji`, `POST /known-kanji/seed`, `GET /cards`, and `POST /cards` to manage the local study data. The seed route inserts about 80 common beginner kanji and is safe to call more than once.

## Decisions

- Phase 0 contains the health endpoint and dependency setup check.
- Phase 1 adds tokenization and rendering; the database and LLM modules remain placeholders for later phases.
- Phase 2 loads one cached Jamdict instance at API startup and returns up to five common-first word entries plus KANJIDIC2 details for kanji in the query.
- Phase 3 uses SQLite with foreign keys and creates one card per unique lemma; posting a known lemma again increments its tap count.
- CORS permits the Vite development origin `http://localhost:5173`.

## Phases-completed checklist

- [x] Phase 0: project setup
- [x] Phase 1: tokenizer and `/render`
- [x] Phase 2: dictionary and `/lookup`
- [x] Phase 3: SQLite, known kanji, and cards
- [ ] Later phases: application features
