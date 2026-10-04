from contextlib import asynccontextmanager
from io import BytesIO
import math
from pathlib import Path
import subprocess
import tempfile
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from PIL import Image, UnidentifiedImageError
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from asr import AsrModelLoadError, AsrTranscriptionError, transcribe

from db import (
    add_card_note,
    create_or_tap_card,
    get_cards,
    get_known_kanji,
    init_db,
    seed_known_kanji,
    update_known_kanji,
)
from dictionary import get_jamdict, lookup_word
from guardrail import generate_within_level
from llm import (
    OllamaResponseError,
    OllamaTimeoutError,
    OllamaUnavailableError,
    explain_casual as explain_casual_with_llm,
    explain as explain_with_llm,
    generate_practice as generate_practice_with_llm,
)
from ocr import OcrModelLoadError, recognize
from progress import get_dashboard_stats, render_and_log, suggest_kanji
from review import answer_card as answer_review_card, list_due_cards
from tokenizer import mask_text


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    get_jamdict()
    yield


app = FastAPI(lifespan=lifespan)

MAX_OCR_UPLOAD_BYTES = 5 * 1024 * 1024
SUPPORTED_IMAGE_TYPES = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}
IMAGE_EXTENSIONS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
UPLOADS_DIR = Path(__file__).resolve().parent / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")


class RenderRequest(BaseModel):
    text: str
    known_kanji: list[str]


class KnownKanjiUpdate(BaseModel):
    add: list[str] = Field(default_factory=list)
    remove: list[str] = Field(default_factory=list)


class CardCreate(BaseModel):
    lemma: str = Field(min_length=1)
    reading: str = Field(min_length=1)
    meaning: str
    sentence: str = Field(min_length=1)
    image_path: str | None = None


class CardNoteCreate(BaseModel):
    note: str = Field(min_length=1)


class ReviewAnswer(BaseModel):
    card_id: int = Field(gt=0)
    rating: int = Field(ge=1, le=4)


class ExplainRequest(BaseModel):
    sentence: str = Field(min_length=1)
    word: str = Field(min_length=1)
    known_kanji: list[str]
    known_words: list[str]


class PracticeRequest(BaseModel):
    word: str = Field(min_length=1)
    known_kanji: list[str]
    known_words: list[str]
    count: int = Field(default=3, ge=1, le=10)


class CasualExplainRequest(BaseModel):
    sentence: str = Field(min_length=1)
    known_kanji: list[str]
    known_words: list[str]


MAX_TRANSCRIBE_UPLOAD_BYTES = 50 * 1024 * 1024
TRANSCRIBE_EXTENSIONS = {
    ".wav", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".flac",
    ".mp4", ".mov", ".mkv", ".webm", ".avi", ".mpeg", ".mpg",
}
NON_CONTENT_POS = {"空白", "補助記号", "記号", "助詞", "助動詞"}


def _contains_kanji(text: str) -> bool:
    return any(
        0x3400 <= ord(char) <= 0x4DBF
        or 0x4E00 <= ord(char) <= 0x9FFF
        or 0xF900 <= ord(char) <= 0xFAFF
        or 0x20000 <= ord(char) <= 0x3134F
        for char in text
    )


def _known_word_percent(tokens: list[dict], known_words: set[str]) -> float:
    content = [token for token in tokens if token.get("pos") not in NON_CONTENT_POS]
    if not content:
        return 100.0
    known_count = sum(
        1 for token in content
        if token.get("lemma") in known_words
        or token.get("surface") in known_words
        or not _contains_kanji(token.get("surface", ""))
    )
    return round(100 * known_count / len(content), 1)


async def _store_transcription_upload(file: UploadFile, destination: Path) -> None:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in TRANSCRIBE_EXTENSIONS:
        await file.close()
        raise HTTPException(
            status_code=415,
            detail="Upload an audio or video file (WAV, MP3, M4A, OGG, FLAC, MP4, MOV, MKV, or WebM).",
        )
    total = 0
    try:
        with destination.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_TRANSCRIBE_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Audio and video uploads are limited to 50 MB.")
                output.write(chunk)
    finally:
        await file.close()
    if total == 0:
        raise HTTPException(status_code=400, detail="The uploaded media file is empty.")


def _probe_duration(media_path: Path) -> float:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
             "default=noprint_wrappers=1:nokey=1", str(media_path)],
            check=True, capture_output=True, text=True, timeout=20,
        )
        duration = float(result.stdout.strip())
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("invalid media duration")
        return duration
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="ffprobe was not found. Install FFmpeg and add its bin folder to PATH, then restart the backend.") from exc
    except (subprocess.SubprocessError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Could not read this media file. Check that it is a valid audio or video clip.") from exc


def _extract_audio(media_path: Path, audio_path: Path) -> None:
    try:
        subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(media_path),
             "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", str(audio_path)],
            check=True, capture_output=True, text=True, timeout=90,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="ffmpeg was not found. Install FFmpeg and add its bin folder to PATH, then restart the backend.") from exc
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=400, detail="Audio extraction took too long. Try a shorter clip.") from exc
    except subprocess.CalledProcessError as exc:
        raise HTTPException(status_code=400, detail="FFmpeg could not extract audio from this file.") from exc


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/render")
def render(request: RenderRequest):
    return render_and_log(request.text, request.known_kanji)


@app.get("/suggestions/kanji")
def kanji_suggestions():
    return suggest_kanji(get_known_kanji())


@app.get("/stats")
def stats():
    return get_dashboard_stats()


@app.post("/explain")
def post_explain(request: ExplainRequest):
    try:
        def task_fn(feedback: str):
            return explain_with_llm(
                sentence=request.sentence,
                word=request.word,
                known_kanji=request.known_kanji,
                known_words=request.known_words,
                feedback=feedback or None,
            )

        return generate_within_level(
            task_fn=task_fn,
            known_kanji=request.known_kanji,
            # The selected target is what the learner is asking to understand.
            known_words=[*request.known_words, request.word],
        )
    except OllamaUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OllamaTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except OllamaResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/practice")
def post_practice(request: PracticeRequest):
    try:
        def task_fn(feedback: str):
            return generate_practice_with_llm(
                word=request.word,
                known_kanji=request.known_kanji,
                known_words=request.known_words,
                count=request.count,
                feedback=feedback or None,
            )

        return generate_within_level(
            task_fn=task_fn,
            known_kanji=request.known_kanji,
            known_words=[*request.known_words, request.word],
        )
    except OllamaUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OllamaTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except OllamaResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/explain-casual")
def post_explain_casual(request: CasualExplainRequest):
    try:
        sentence_words = [
            form
            for token in mask_text(request.sentence, set(request.known_kanji))
            for form in (token["surface"], token["lemma"])
        ]

        def task_fn(feedback: str):
            return explain_casual_with_llm(
                sentence=request.sentence,
                known_kanji=request.known_kanji,
                known_words=request.known_words,
                feedback=feedback or None,
            )

        return generate_within_level(
            task_fn=task_fn,
            known_kanji=request.known_kanji,
            # The casual form in the sentence is the expression being taught.
            known_words=[*request.known_words, *sentence_words],
        )
    except OllamaUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OllamaTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except OllamaResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


async def read_valid_image(file: UploadFile) -> tuple[bytes, str]:
    content_type = (file.content_type or "").split(";", maxsplit=1)[0].lower()
    expected_format = SUPPORTED_IMAGE_TYPES.get(content_type)
    if expected_format is None:
        await file.close()
        raise HTTPException(
            status_code=415,
            detail="Upload a JPEG, PNG, or WebP image.",
        )

    try:
        image_bytes = await file.read(MAX_OCR_UPLOAD_BYTES + 1)
    finally:
        await file.close()
    if len(image_bytes) > MAX_OCR_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image uploads are limited to 5 MB.")
    if not image_bytes:
        raise HTTPException(status_code=400, detail="The uploaded image is empty.")

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image_format = image.format
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise HTTPException(
            status_code=400,
            detail="The upload is not a valid, readable image.",
        ) from exc

    if image_format != expected_format:
        raise HTTPException(
            status_code=415,
            detail="The image contents do not match the declared file type.",
        )

    return image_bytes, image_format


@app.post("/ocr")
async def ocr(file: UploadFile = File(...)):
    image_bytes, _ = await read_valid_image(file)

    try:
        text = await run_in_threadpool(recognize, image_bytes)
    except OcrModelLoadError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "The OCR model could not be loaded. Confirm manga-ocr is installed; "
                "its model downloads on the first OCR request."
            ),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="OCR could not process this image.",
        ) from exc

    return {"text": text}


@app.post("/transcribe")
async def post_transcribe(file: UploadFile = File(...)):
    """Transcribe up to 60 seconds of uploaded audio/video and return masked segments."""
    with tempfile.TemporaryDirectory(prefix="kotodane-asr-") as temp_dir:
        media_path = Path(temp_dir) / f"upload{Path(file.filename or '').suffix.lower()}"
        audio_path = Path(temp_dir) / "audio.wav"
        await _store_transcription_upload(file, media_path)
        duration = await run_in_threadpool(_probe_duration, media_path)
        if duration > 60:
            raise HTTPException(status_code=413, detail="Clips must be 60 seconds or shorter.")
        await run_in_threadpool(_extract_audio, media_path, audio_path)
        try:
            raw_segments = await run_in_threadpool(transcribe, str(audio_path))
        except AsrModelLoadError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except AsrTranscriptionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail="Speech recognition failed unexpectedly.") from exc

    known_kanji = set(get_known_kanji())
    known_words = {card["lemma"] for card in get_cards()}
    segments = []
    for segment in raw_segments:
        tokens = mask_text(segment["text"], known_kanji)
        segments.append({
            **segment,
            "tokens": tokens,
            "known_words_percent": _known_word_percent(tokens, known_words),
        })
    return {"segments": segments, "duration": round(duration, 2)}


@app.post("/images")
async def save_image(file: UploadFile = File(...)):
    image_bytes, image_format = await read_valid_image(file)
    filename = f"{uuid4().hex}{IMAGE_EXTENSIONS[image_format]}"
    image_path = UPLOADS_DIR / filename
    try:
        await run_in_threadpool(image_path.write_bytes, image_bytes)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not save the cropped image.") from exc
    return {"image_path": f"/uploads/{filename}"}


@app.get("/lookup")
def lookup(word: str = Query(..., min_length=1)):
    return lookup_word(word)


@app.get("/known-kanji")
def known_kanji():
    return {"known_kanji": get_known_kanji()}


@app.put("/known-kanji")
def put_known_kanji(request: KnownKanjiUpdate):
    return {"known_kanji": update_known_kanji(request.add, request.remove)}


@app.post("/known-kanji/seed")
def post_known_kanji_seed():
    return seed_known_kanji()


@app.post("/cards")
def post_card(request: CardCreate):
    return create_or_tap_card(
        lemma=request.lemma,
        reading=request.reading,
        meaning=request.meaning,
        sentence=request.sentence,
        image_path=request.image_path,
    )


@app.post("/cards/{lemma}/notes")
def post_card_note(lemma: str, request: CardNoteCreate):
    card = add_card_note(lemma=lemma, note=request.note)
    if card is None:
        raise HTTPException(status_code=404, detail="Save this word as a card before adding examples.")
    return {"card": card}


@app.get("/cards")
def cards():
    return {"cards": get_cards()}


@app.get("/reviews/due")
def reviews_due(limit: int = Query(default=20, ge=1, le=100)):
    return {"cards": list_due_cards(limit=limit)}


@app.post("/reviews/answer")
def review_answer(request: ReviewAnswer):
    try:
        result = answer_review_card(request.card_id, request.rating)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Vocabulary card not found.")
    return result
