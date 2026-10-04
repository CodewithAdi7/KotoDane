# Kotodane Notes

## Summary

Local-first Japanese reading tutor for a beginner learner. Phase 0 established the project structure; Phase 1 added Japanese tokenization and kanji-aware rendering; Phase 2 added local dictionary lookup; Phase 3 added persistent known-kanji and vocabulary-card endpoints; Phase 4 added the reader UI; Phase 5 added word lookup and known-kanji management; Phase 6 connects word lookup to saved vocabulary cards; Phase 7 adds local manga OCR; Phase 8 connects page cropping, OCR, reading, and card thumbnails; Phases L1-L3 add local Ollama explanations, level guardrails, practice examples, and casual-speech explanations.

## Stack

- Python 3.13.7, FastAPI, SQLite
- fugashi with unidic-lite for Japanese tokenization
- jamdict and jamdict-data for dictionary lookup
- manga-ocr for Japanese text recognition from images
- python-multipart for FastAPI multipart uploads
- React Image Crop for selecting manga speech-bubble crops
- React and Vite (JavaScript) frontend
- Ollama with Qwen3 4B for local Japanese explanations; planned Whisper for listening

## Structure

```text
kotodane/
├── backend/
│   ├── check_setup.py
│   ├── db.py  (SQLite schema and persistence)
│   ├── dictionary.py
│   ├── guardrail.py  (known-level checks and retry loop)
│   ├── llm.py
│   ├── main.py
│   ├── ocr.py  (lazy manga-ocr model)
│   ├── prompts.py  (LLM prompt templates and JSON schemas)
│   ├── requirements.txt
│   ├── test_dictionary.py
│   ├── test_guardrail.py
│   ├── test_l3.py
│   ├── test_ocr.py
│   ├── test_tokenizer.py
│   ├── tokenizer.py
│   └── uploads/  (saved bubble crops; created on first API import)
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

For local explanations, install Ollama on Windows from [ollama.com/download/windows](https://ollama.com/download/windows), or run this command in PowerShell:

```powershell
irm https://ollama.com/install.ps1 | iex
```

Open a new PowerShell window, then download and start the recommended model:

```powershell
ollama --version
ollama pull qwen3:4b
ollama run qwen3:4b
```

Exit the interactive model prompt after confirming Ollama responds. It continues serving its local API at `http://localhost:11434`. From the backend terminal, set the model and start FastAPI:

```powershell
$env:OLLAMA_MODEL = "qwen3:4b"
uvicorn main:app --reload
```

`POST /explain` accepts `sentence`, `word`, `known_kanji`, and `known_words`, and returns `explanation_ja` plus `hint_en`. The model uses Ollama's JSON response format. Set `$env:OLLAMA_TIMEOUT_SECONDS = "180"` before starting the backend if generation times out. No additional Python package is needed for this phase.

Phase L2 checks generated Japanese explanation text with fugashi. Kana-only words, particles, punctuation, and whitespace are allowed; unlisted kanji trigger a retry, and unknown vocabulary above the 10% default threshold also triggers a retry. `/explain` returns `tries`, `unknown_ratio`, and `passed` alongside the explanation. Retry feedback names the words or kanji to avoid. Run the mocked guardrail tests from `backend` with `python -m pytest -q test_guardrail.py`.

Phase L3 adds `POST /practice` for short target-word example sentences and `POST /explain-casual` for spoken Japanese forms and sentence endings. Both use structured Ollama JSON and the L2 guardrail loop; responses include `tries`, `unknown_ratio`, and `passed`. Practice accepts `count` from 1 to 10 (default 3). Test the mocked L3 validation and guardrail paths with `python -m pytest -q test_l3.py` from `backend`.

Phase L1 model recommendation: use `qwen3:4b` (Q4_K_M, approximately 2.5 GB; Apache License 2.0). The 4B size and quantization suit a 6 GB GPU, though available VRAM and context usage determine GPU offload. Alternatives: `gemma3:4b` (approximately 3.3 GB; Gemma Terms of Use) supports over 140 languages; `llama3.2:3b` (approximately 2.0 GB; Llama 3.2 Community License) is lightweight, but Japanese is not among Meta's officially listed supported languages. Ollama catalog sizes and licenses: [Qwen3 4B](https://ollama.com/library/qwen3%3A4b), [Gemma 3 4B](https://ollama.com/library/gemma3%3A4b), [Llama 3.2 3B](https://ollama.com/library/llama3.2%3A3b).

Run the OCR sample check from `backend` after choosing a local sample image: `python test_ocr.py "C:\\path\\to\\speech-bubble.png" --expected "ここに予想される日本語"`. Omit `--expected` to print the recognition result without comparing it.

In the frontend, open the **Panel** tab, upload a manga page, drag a crop around one speech bubble, and choose **Read bubble**. Correct the editable OCR text if needed, then select **Process text** to send it through the normal reader rendering and lookup flow. A crop is saved under `backend/uploads/`; vocabulary cards created from that reader text keep the crop path and show its thumbnail on the Cards tab. Uploaded crop files are local data and are excluded from Git.

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
- Phase 8 uses React Image Crop in the Panel tab, saves the selected crop through `POST /images`, renders corrected OCR text through the existing `/render` flow, and attaches the saved crop path to vocabulary cards.
- Phase L1 adds a local Ollama `/explain` endpoint with `qwen3:4b` as the default model, JSON-validated output, beginner-level Japanese constrained by the supplied known lists, and a short English hint. Qwen3 thinking is disabled for this short structured response so its output budget is used for the JSON result. Model license: Apache License 2.0.
- Phase L2 validates `explanation_ja` against known kanji and words, retries up to three times with `avoid:` feedback, and returns the best attempt with retry metadata. Unknown kanji always cause a retry; unknown vocabulary is tolerated only within the configured ratio.
- Phase L3 adds `/practice` and `/explain-casual`, using structured JSON prompts and the L2 guardrail. Practice checks all returned example sentences; casual-speech explanations allow quoted forms from the input sentence while still checking kanji against the learner's known list.
- Reopening an existing vocabulary card with a crop updates its image path instead of creating a duplicate card.
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
- [ ] Phase 8: panel crop, OCR, and image-backed cards (manual OCR round-trip pending)
- [x] Phase L1: local Ollama `/explain`
- [x] Phase L2: level-locked guardrail loop
- [x] Phase L3: practice sentences and casual-speech explanations
- [ ] Later phases: application features
