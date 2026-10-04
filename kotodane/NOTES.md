# Kotodane Notes

## Summary

Local-first Japanese reading tutor for a beginner learner. Phase 0 established the project structure; Phase 1 added Japanese tokenization and kanji-aware rendering; Phase 2 added local dictionary lookup; Phase 3 added persistent known-kanji and vocabulary-card endpoints; Phase 4 added the reader UI; Phase 5 added word lookup and known-kanji management; Phase 6 connects word lookup to saved vocabulary cards; Phase 7 adds local manga OCR.

## Stack

- Python 3.13.7, FastAPI, SQLite
- fugashi with unidic-lite for Japanese tokenization
- jamdict and jamdict-data for dictionary lookup
- manga-ocr for Japanese text recognition from images
- python-multipart for FastAPI multipart uploads
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
│   ├── ocr.py  (lazy manga-ocr model)
│   ├── requirements.txt
│   ├── test_dictionary.py
│   ├── test_ocr.py
│   ├── test_tokenizer.py
│   └── tokenizer.py
├── frontend/
│   ├── .env
│   ├── index.html
│   ├── package.json
│   ├── package-lock.json
│   ├── public/
│   │   └── favicon.svg
│   ├── src/
│   │   ├── App.css
│   │   ├── App.jsx
│   │   ├── index.css
│   │   └── main.jsx
│   └── vite.config.js
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

Install manga-ocr in the backend virtual environment with `python -m pip install manga-ocr` (or install all requirements with `python -m pip install -r requirements.txt`). The OCR model is loaded only on the first valid `POST /ocr` request, which downloads its model weights from Hugging Face if they are not cached. The endpoint accepts JPEG, PNG, and WebP images up to 5 MB. Use `/docs` to upload a cropped speech bubble.

Run the OCR sample check from `backend` after choosing a local sample image: `python test_ocr.py "C:\\path\\to\\speech-bubble.png" --expected "ここに予想される日本語"`. Omit `--expected` to print the recognition result without comparing it.

Phase 7 model details for the README: model ID `kha-white/manga-ocr-base`; project/model license Apache-2.0; first-run model download is approximately 444 MB (upstream describes it as about 400 MB). The upstream project notes that the newest Python release can lag behind PyTorch, but the current PyTorch Windows support range includes Python 3.13. `manga-ocr` and PyTorch installed successfully in this project's Python 3.13.7 environment. If `manga-ocr` itself cannot install in the Python 3.13 environment, use either of these alternatives:

1. Torchless ONNX port: replace `manga-ocr` with `manga-ocr-torchless` in `requirements.txt`, then run `python -m pip install -r requirements.txt`. It keeps the `from manga_ocr import MangaOcr` API and downloads about 400 MB of ONNX model files on first use.
2. Python 3.12 environment: from `backend`, run `uv python install 3.12`, `uv venv --python 3.12 .venv312`, `.\\.venv312\\Scripts\\Activate.ps1`, then `python -m pip install -r requirements.txt`.

Run the reader UI in a second PowerShell terminal with `cd frontend`, `npm install`, and `npm run dev`. The Vite app reads its backend base URL from `frontend/.env` (`VITE_API_URL=http://localhost:8000`). Paste Japanese text and press **Render text**; the UI loads the saved known kanji and sends the text to `POST /render`. Tap a word in the reading view to open its local dictionary entry and save a vocabulary card with the word's reading, first dictionary meaning, and source sentence. Use the **Kanji** tab to seed the starter list, add a character, or toggle a character's known status; the displayed passage re-renders when the list changes. Open **Cards** to review saved words and tap counts. Cards persist in `kotodane.db` across server restarts. Check the frontend compiles with `npm run build`.

## Decisions

- Phase 0 contains the health endpoint and dependency setup check.
- Phase 1 adds tokenization and rendering; the database and LLM modules remain placeholders for later phases.
- Phase 2 loads one cached Jamdict instance at API startup and returns up to five common-first word entries plus KANJIDIC2 details for kanji in the query.
- Phase 3 uses SQLite with foreign keys and creates one card per unique lemma; posting a known lemma again increments its tap count.
- Phase 4 introduced the React reader page and Phase 5 adds simple Reader/Kanji tabs, tap-to-lookup details, and known-kanji controls using the existing API.
- Phase 6 saves looked-up words through the existing `/cards` endpoint and adds a Cards view; repeat lookups reuse the lemma's card and increment its tap count.
- Phase 7 loads the manga-ocr model lazily on first image request and accepts validated JPEG/PNG/WebP uploads up to 5 MB at `POST /ocr`.
- CORS permits the Vite development origin `http://localhost:5173`.

## Phases-completed checklist

- [x] Phase 0: project setup
- [x] Phase 1: tokenizer and `/render`
- [x] Phase 2: dictionary and `/lookup`
- [x] Phase 3: SQLite, known kanji, and cards
- [x] Phase 4: React reader UI
- [x] Phase 5: tap-to-lookup and kanji manager
- [x] Phase 6: saved vocabulary cards
- [ ] Phase 7: manga OCR endpoint (sample-image recognition check pending)
- [ ] Later phases: application features
