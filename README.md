# Kotodane (言種)

**Read what you love. Watch the kanji grow.**

Kotodane ("word seed") is a local-first Japanese reading tutor for beginner learners. Paste Japanese text or crop a bubble from a manga page, read it with kanji masking, look up words, and get level-checked explanations and practice sentences. Study data stays in a local SQLite database, and everything runs on your own machine: no cloud APIs, no accounts, no API keys.

<!-- Add the demo recording once it exists, then uncomment the next line:
![Kotodane demo](docs/demo.gif)
-->

## Why I built it

I built Kotodane for a friend who is learning Japanese so he can read his favorite manga and, one day, watch anime without subtitles. He knows hiragana, katakana and a few dozen kanji, and a real manga page is a wall of symbols he can't read yet.

Tools like Google Lens can translate a page, but they forget you as soon as they're done. They don't know what you know, and a translation doesn't teach you to read. Kotodane keeps a personal model of what you've learned and adapts everything you see to it.

## What's included

- **Reader:** paste Japanese text and read it with kanji masking. Kanji you know stay as kanji, everything else shows as hiragana, and the same text grows as you learn more.
- **Panel:** upload a manga page, crop a speech bubble, and read it with OCR.
- **Tap-to-lookup:** tap any word for its reading and meaning.
- **AI tutor:** level-checked explanations, practice sentences, and casual-speech explanations from a local LLM.
- **Cards and review:** saved words become flashcards, scheduled with FSRS.
- **Dashboard:** known-word percentages and kanji suggestions.
- **Listen:** optional transcription of short Japanese audio and video clips.

## How the AI stays at your level

Most AI tutors talk at whatever level the model feels like. Kotodane checks the model's output against what you actually know:

```
tap a word -> local LLM explains -> tokenizer checks against your known words and kanji
           -> too many unknown words? retry with "avoid: ..." feedback
           -> passes (or best attempt) -> shown with your personal kanji display
```

The LLM does the language work, and plain application logic enforces the learner's level.

## What uses AI?

| Feature | Tool or model | What it does |
|---|---|---|
| Manga text recognition | manga-ocr, weights `kha-white/manga-ocr-base` | Reads text in a selected speech bubble. |
| Tutor and example generation | Qwen3 4B, run locally by Ollama | Explains words, generates practice sentences, and explains casual speech. |
| Listening transcription | Whisper small, CTranslate2 format, run by faster-whisper | Transcribes Japanese audio and video clips. |

The app also uses classic, non-generative tools: fugashi/UniDic tokenization, Jamdict's JMdict and KANJIDIC2 lookup database, SQLite persistence, and FSRS scheduling. Kanji masking, known-word percentages, suggestions, and level checks are deterministic application logic. Generated explanations remain best-effort; the guardrail checks Japanese output against the learner's supplied known lists and reports whether the output passed.

## Models and licenses

| Model | Use | License | First download |
|---|---|---|---|
| `kha-white/manga-ocr-base` | Japanese manga OCR | Apache-2.0 | About 444 MB |
| `qwen3:4b` (Q4_K_M) | Local tutor | Apache-2.0 | About 2.5 GB |
| `Systran/faster-whisper-small` | Japanese speech recognition | MIT | About 486 MB |

The model weights have their own licenses, separate from this repository's MIT license. The faster-whisper inference implementation is also MIT licensed. Whisper transcription is optional; the app defaults to CPU int8, so a CUDA setup is not required.

## Requirements

- Windows 10 or later (the steps below are for Windows PowerShell; on macOS or Linux, use the equivalent venv activation and paths)
- Python 3.13 (the project was developed with Python 3.13.7)
- Node.js and npm
- Internet access on first installation and first use of each model
- Ollama and the Qwen model for AI tutor features
- FFmpeg on PATH for the optional audio/video transcription feature

## Install and run on Windows

Clone the repository, open PowerShell in the project directory, and create the Python environment:

```powershell
git clone https://github.com/CodewithAdi7/KotoDane.git
cd KotoDane
py -3.13 -m venv backend\.venv
.\backend\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip wheel
python -m pip install -r backend\requirements.txt
```

If PowerShell blocks environment activation, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then activate again. Alternatively, run the venv's Python directly as `backend\.venv\Scripts\python.exe`.

### Dictionary install on Windows

Jamdict's database package unpacks a compressed dictionary during installation. The wheel upgrade above addresses the install issue documented by Jamdict. If `jamdict-data` still fails while Windows is accessing its temporary database file, close other Kotodane/Python install processes and retry:

```powershell
python -m pip uninstall -y jamdict-data
python -m pip install --upgrade pip wheel
python -m pip install --no-cache-dir jamdict-data
python -m pip install -r backend\requirements.txt
```

### Start the backend

In one terminal:

```powershell
cd backend
uvicorn main:app --reload
```

Open http://127.0.0.1:8000/docs for the API, or http://127.0.0.1:8000/health to confirm it is running. The local database is created at first startup.

### Start the frontend

In a second PowerShell terminal:

```powershell
cd frontend
if (!(Test-Path .env)) { Copy-Item .env.example .env }
npm ci
npm run dev
```

Open the local URL Vite prints (normally http://localhost:5173). `.env.example` shows the default backend URL for a fresh checkout.

## Enable OCR and the local tutor

Install Ollama from [ollama.com/download/windows](https://ollama.com/download/windows), open a new terminal, and pull the model:

```powershell
ollama --version
ollama pull qwen3:4b
```

Ollama serves its local API at http://localhost:11434. In the terminal where you start FastAPI, set optional backend settings before starting the server:

```powershell
$env:OLLAMA_MODEL = "qwen3:4b"
$env:OLLAMA_TIMEOUT_SECONDS = "180"
$env:WHISPER_MODEL_SIZE = "small"
uvicorn main:app --reload
```

No separate OCR command is required. Open **Panel**, upload `sample-data/demo-page.png`, drag a crop around the speech bubble, and choose **Read bubble**. The first OCR request downloads about 444 MB of model files. Edit the recognized text if needed and choose **Process text**. In **Reader**, tap a word and choose **AI explain** or **Practice sentences**. The first tutor request requires Ollama to be running with `qwen3:4b` available.

The UI shows loading indicators during OCR, tutor generation, transcription, and review. When Ollama is unavailable, the tutor panel explains how to start it and provides **Retry**. OCR model load/download failures are shown in the panel as a readable error; retry after confirming manga-ocr is installed and internet access is available for the initial model download.

## Optional: audio/video transcription

Install FFmpeg from [ffmpeg.org/download.html](https://ffmpeg.org/download.html) using one of its linked Windows builds. Extract it and add the folder containing `ffmpeg.exe` and `ffprobe.exe` to PATH; open a new terminal and verify `ffmpeg -version` and `ffprobe -version`. Use the **Listen** tab to upload a clip up to 60 seconds. The Whisper model downloads on first use.

## Sample asset

`sample-data/demo-page.png` is an original page illustration made for this project, not a scan or excerpt from a published manga. It is included for the crop/OCR demo and is available under this repository's MIT license.

## A note on manga and copyright

Kotodane doesn't include, host, or distribute any manga or anime. Use pages you own or have the right to use. The only page in this repository is the self-made sample above.

<details>
<summary><strong>90-second demo script</strong></summary>

| Time | Demo |
|---|---|
| 0–10 s | Open Kotodane and introduce the local reading workflow. |
| 10–28 s | Open Panel, upload `sample-data/demo-page.png`, and drag a crop around the balloon. |
| 28–38 s | Choose Read bubble; briefly show the OCR loading state and editable Japanese result. |
| 38–48 s | Choose Process text to open the masked reading view; point out the unknown-kanji reading. |
| 48–68 s | Tap a word and choose AI explain; show the Japanese explanation, English hint, and level-check result. |
| 68–82 s | Choose Practice sentences and show the generated examples and their level-check status. |
| 82–90 s | Save or revisit a word in Cards, then show the progress/suggestions in Dashboard. |

</details>

## Tests and build

From `backend`, with the venv active:

```powershell
python -m pip install pytest
python -m pytest -q test_tokenizer.py test_dictionary.py test_progress.py test_review.py test_guardrail.py test_l3.py test_cards_notes.py
```

OCR recognition requires a chosen image/model download; transcription requires FFmpeg and a clip. Those are manual checks. From `frontend`, build the production bundle with:

```powershell
npm run build
```

## Known limitations

- OCR can misread stylized fonts, so recognized text is editable before processing.
- Kanji masking works on whole words for now, not on individual kanji.
- Tutor explanations depend on the size and quality of the local model, and remain best-effort even with the level check.

## Contributing

Issues and pull requests are welcome. Please open an issue first for larger changes.

## License

Kotodane source code and the original demo image are under the [MIT License](LICENSE). Third-party models, packages, and dictionary data retain their respective licenses listed above or by their upstream projects.

## Acknowledgments

- [manga-ocr](https://github.com/kha-white/manga-ocr) by kha-white
- [Qwen3](https://ollama.com/library/qwen3) and [Ollama](https://ollama.com)
- [Whisper](https://github.com/openai/whisper) by OpenAI, and [faster-whisper](https://github.com/SYSTRAN/faster-whisper) by SYSTRAN
- [fugashi](https://github.com/polm/fugashi), UniDic, and [jamdict](https://github.com/neocl/jamdict)
- JMdict and KANJIDIC2 by the [Electronic Dictionary Research and Development Group](https://www.edrdg.org/), used under the [EDRDG licence](https://www.edrdg.org/edrdg/licence.html)
- Built with the help of GitHub Copilot
