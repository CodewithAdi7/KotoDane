# Kotodane (言種)

**Read what you love. Watch the kanji grow.**

Kotodane ("word seed") is a private, local-first Japanese reading tutor built on open-source AI. It helps beginners read manga by showing only the kanji they already know, explaining words at their level, and remembering what they've learned. Everything runs on your own machine: no cloud APIs, no accounts, no API keys.

> **Status:** early development. See [Project status](#project-status) for what works today.

---

## Why Kotodane?

I built this for a friend who is learning Japanese so he can read his favorite manga and, one day, watch anime without subtitles. He knows hiragana, katakana and a few dozen kanji, and real manga is a wall of symbols he can't read yet.

Tools like Google Lens can translate a page, but they forget you as soon as they're done. They don't know what you know, and a translation doesn't teach you to read. Kotodane keeps a personal model of what you've learned and uses it to adapt everything you see.

## How it works

1. **Crop a speech bubble** from a manga page you own.
2. **OCR reads it.** [manga-ocr](https://github.com/kha-white/manga-ocr) is an open model built for manga fonts and vertical text.
3. **The text adapts to you.** Kanji you know stay as kanji, and everything else is shown in hiragana. Mark a new kanji as known and the same page grows.
4. **Tap any word** to see its reading and meaning.
5. **A local LLM explains it at your level**, in simple Japanese using only words and kanji you already know, with a short English hint.
6. **A guardrail checks the AI.** Every explanation is tokenized and compared against your known words. If it uses too many words you haven't learned, the app retries with feedback.

```
tap a word -> local LLM explains -> tokenizer checks against what you know
           -> too many unknown words? retry with "avoid: ..." feedback
           -> passes (or best of 3 tries) -> shown in your personal kanji display
```

## Open-source AI used

| Role | Component | License |
|---|---|---|
| Reads speech bubbles | manga-ocr | Apache-2.0 *(verify)* |
| Explains words (local LLM) | `qwen3:4b` via [Ollama](https://ollama.com) | `MIT` |
| Splits Japanese into words | fugashi + unidic-lite | `[verify]` |
| Dictionary | JMdict / KANJIDIC2 via jamdict | EDRDG license *(verify)* |

Please double-check each license against the project's own page before relying on this table. "Open-weight" models sometimes come with usage conditions.

## Tech stack

- **Backend:** Python 3.13 + FastAPI
- **Database:** SQLite
- **Frontend:** React + Vite
- **NLP:** fugashi (MeCab wrapper), jamdict
- **OCR:** manga-ocr
- **LLM runtime:** Ollama

## Project structure

```
KotoDane/
├── backend/       # FastAPI app: tokenizer, dictionary, database, OCR, LLM
├── frontend/      # React + Vite app
├── NOTES.md       # Development notes and decisions
├── LICENSE
└── README.md
```

## Getting started

### Requirements
- Python 3.10 or newer (developed on 3.13)
- Node.js 18 or newer
- [Ollama](https://ollama.com) with a model pulled `[e.g. ollama pull MODEL_NAME]`
- Enough RAM for your chosen model

### Backend
```bash
cd backend
python -m venv venv

# Windows (PowerShell)
venv\Scripts\Activate.ps1
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
uvicorn main:app --reload
```
Open http://localhost:8000/docs to see the API.

### Frontend
```bash
cd frontend
npm install
```
Create `frontend/.env` with:
```
VITE_API_URL=http://localhost:8000
```
Then run:
```bash
npm run dev
```
Open http://localhost:5173.

### Configuration
Copy `.env.example` to `.env` in `backend/` and set:
- `OLLAMA_MODEL`: the local model to use for explanations

## Project status

- [x] Project setup
- [ ] Tokenizer and kanji-growing display (`/render`)
- [ ] Dictionary lookup (`/lookup`)
- [ ] Database: known kanji and saved words
- [ ] Reader UI with tap-to-lookup and kanji manager
- [ ] Manga bubble OCR (manga-ocr) with crop tool
- [ ] Local LLM explanations (`/explain`)
- [ ] Level-locked guardrail loop
- [ ] Practice sentences and casual-speech explanations
- [ ] Flashcard review (spaced repetition)
- [ ] Anime listening tools (subtitle import, Whisper transcription)

*Tick these off as you finish them, and remove anything you don't plan to build.*

## Known limitations

- OCR can misread stylized fonts, so recognized text is editable before processing.
- Kanji masking works on whole words for now, not on individual kanji.
- LLM explanations depend on the size and quality of the local model you choose.

## A note on manga and copyright

Kotodane doesn't include, host, or distribute any manga or anime. You supply your own legally obtained pages. The sample data in this repo `[describe: public-domain or self-made]` is only for demonstration.

## Roadmap

- Pitch accent and pronunciation practice using open-source speech models
- Per-kanji masking with proper okurigana handling
- Matching manga chapters to anime episodes, so words you read show up when you listen

## Contributing

Issues and pull requests are welcome. Please open an issue first for larger changes.

## License

Released under the [MIT License](LICENSE).

## Acknowledgments

- [manga-ocr](https://github.com/kha-white/manga-ocr) by kha-white
- [JMdict / KANJIDIC2](https://www.edrdg.org/) by the Electronic Dictionary Research and Development Group
- [fugashi](https://github.com/polm/fugashi) and [jamdict](https://github.com/neocl/jamdict)
- [Ollama](https://ollama.com) and the open-weight model `[MODEL NAME]`
- Built with the help of GitHub Copilot
