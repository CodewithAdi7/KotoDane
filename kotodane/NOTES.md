# Kotodane Notes

## Summary

Local-first Japanese reading tutor for a beginner learner. Phase 0 establishes the project structure and verifies the initial Python dependencies.

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
│   ├── db.py
│   ├── dictionary.py
│   ├── llm.py
│   ├── main.py
│   ├── requirements.txt
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

## Decisions

- Phase 0 contains only the health endpoint and dependency setup check; application logic is deferred.
- The backend modules other than `main.py` are placeholders for later phases.
- CORS permits the Vite development origin `http://localhost:5173`.

## Phases-completed checklist

- [x] Phase 0: project setup
- [ ] Later phases: application features
