# Kotodane

Kotodane is a local-first Japanese reading tutor for beginner learners. Paste Japanese text or crop a bubble from a manga page, read it with kanji masking, look up words, and get level-checked explanations and practice sentences. Study data stays in a local SQLite database.

> **Demo image:** [Self-made sample manga page](sample-data/demo-page.png). Add a short screen recording here when available: `![Kotodane demo](docs/demo.gif)`.

## What uses AI?

| Feature | Tool or model | What it does |
| --- | --- | --- |
| Manga text recognition | [manga-ocr](https://github.com/kha-white/manga-ocr), weights [`kha-white/manga-ocr-base`](https://huggingface.co/kha-white/manga-ocr-base) | Reads text in a selected speech bubble. |
| Tutor and example generation | [Qwen3 4B](https://ollama.com/library/qwen3%3A4b), run locally by Ollama | Explains words, generates practice sentences, and explains casual speech. |
| Listening transcription | [Whisper small, CTranslate2 format](https://huggingface.co/Systran/faster-whisper-small), run by [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Transcribes Japanese audio and video clips. |

The app also uses classic, non-generative tools: fugashi/UniDic tokenization, Jamdict's JMdict and KANJIDIC2 lookup database, SQLite persistence, and FSRS scheduling. Kanji masking, known-word percentages, suggestions, and level checks are deterministic application logic. Generated explanations remain best-effort; the guardrail checks Japanese output against the learner's supplied known lists and reports whether the output passed.

## Models and licenses

| Model | Use | License | First download |
| --- | --- | --- | --- |
| [`kha-white/manga-ocr-base`](https://huggingface.co/kha-white/manga-ocr-base) | Japanese manga OCR | Apache-2.0 | About 444 MB |
| [`qwen3:4b`](https://ollama.com/library/qwen3%3A4b) (Q4_K_M) | Local tutor | Apache-2.0 | About 2.5 GB |
| [`Systran/faster-whisper-small`](https://huggingface.co/Systran/faster-whisper-small) | Japanese speech recognition | MIT | About 486 MB |

The model weights have their own licenses, separate from this repository's MIT license. The faster-whisper inference implementation is also MIT licensed. Whisper transcription is optional; the app defaults to CPU `int8`, so a CUDA setup is not required.

## Requirements

- Windows 10 or later
- Python 3.13 (the project was developed with Python 3.13.7)
- Node.js and npm
- Internet access on first installation and first use of each model
- Ollama and the Qwen model for AI tutor features
- FFmpeg on `PATH` for the optional audio/video transcription feature

## Install and run on Windows

Clone the repository, open PowerShell in the project directory, and create the Python environment:

```powershell
git clone <repository-url> kotodane
cd kotodane
py -3.13 -m venv backend\.venv
.\backend\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip wheel
python -m pip install -r backend\requirements.txt
```

If PowerShell blocks environment activation, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then activate again. Alternatively, run the venv's Python directly as `backend\.venv\Scripts\python.exe`.

### Dictionary install on Windows

Jamdict's database package unpacks a compressed dictionary during installation. The `wheel` upgrade above addresses the install issue documented by Jamdict. If `jamdict-data` still fails while Windows is accessing its temporary database file, close other Kotodane/Python install processes and retry:

```powershell
python -m pip uninstall -y jamdict-data
python -m pip install --upgrade pip wheel
python -m pip install --no-cache-dir jamdict-data
python -m pip install -r backend\requirements.txt
```

Start the backend in one terminal:

```powershell
cd backend
uvicorn main:app --reload
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for the API, or [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) to confirm it is running. The local database is created at first startup.

In a second PowerShell terminal, start the frontend:

```powershell
cd frontend
if (!(Test-Path .env)) { Copy-Item .env.example .env }
npm ci
npm run dev
```

Open the local URL Vite prints (normally [http://localhost:5173](http://localhost:5173)). The repository already includes a `.env`; `.env.example` shows the default backend URL for a fresh checkout.

## Enable OCR and the local tutor

Install Ollama from [ollama.com/download/windows](https://ollama.com/download/windows), open a new terminal, and pull the model:

```powershell
ollama --version
ollama pull qwen3:4b
```

Ollama serves its local API at `http://localhost:11434`. In the terminal where you start FastAPI, set optional backend settings before starting the server:

```powershell
$env:OLLAMA_MODEL = "qwen3:4b"
$env:OLLAMA_TIMEOUT_SECONDS = "180"
$env:WHISPER_MODEL_SIZE = "small"
uvicorn main:app --reload
```

No separate OCR command is required. Open **Panel**, upload `sample-data/demo-page.png`, drag a crop around the speech bubble, and choose **Read bubble**. The first OCR request downloads about 444 MB of model files. Edit the recognized text if needed and choose **Process text**. In Reader, tap a word and choose **AI explain** or **Practice sentences**. The first tutor request requires Ollama to be running with `qwen3:4b` available.

The existing UI shows loading indicators during OCR, tutor generation, transcription, and review. When Ollama is unavailable, the tutor panel explains how to start it and provides Retry. OCR model load/download failures are shown in the panel as a readable error; retry after confirming `manga-ocr` is installed and internet access is available for the initial model download.

## Optional: audio/video transcription

Install FFmpeg from [ffmpeg.org/download.html](https://ffmpeg.org/download.html) using one of its linked Windows builds. Extract it and add the folder containing `ffmpeg.exe` and `ffprobe.exe` to `PATH`; open a new terminal and verify `ffmpeg -version` and `ffprobe -version`. Use the **Listen** tab to upload a clip up to 60 seconds. The Whisper model downloads on first use.

## Sample asset

`sample-data/demo-page.png` is an original page illustration made for this project, not a scan or excerpt from a published manga. It is included for the crop/OCR demo and is available under this repository's MIT license.

## 90-second demo script

| Time | Demo |
| --- | --- |
| 0–10 s | Open Kotodane and introduce the local reading workflow. |
| 10–28 s | Open **Panel**, upload `sample-data/demo-page.png`, and drag a crop around the balloon. |
| 28–38 s | Choose **Read bubble**; briefly show the OCR loading state and editable Japanese result. |
| 38–48 s | Choose **Process text** to open the masked reading view; point out the unknown-kanji reading. |
| 48–68 s | Tap a word and choose **AI explain**; show the Japanese explanation, English hint, and level-check result. |
| 68–82 s | Choose **Practice sentences** and show the generated examples and their level-check status. |
| 82–90 s | Save or revisit a word in **Cards**, then show the progress/suggestions in **Dashboard**. |

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

## License

Kotodane source code and the original demo image are under the [MIT License](LICENSE). Third-party models, packages, and dictionary data retain their respective licenses listed above or by their upstream projects.
