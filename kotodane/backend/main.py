from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from PIL import Image, UnidentifiedImageError
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from db import (
    create_or_tap_card,
    get_cards,
    get_known_kanji,
    init_db,
    seed_known_kanji,
    update_known_kanji,
)
from dictionary import get_jamdict, lookup_word
from llm import (
    OllamaResponseError,
    OllamaTimeoutError,
    OllamaUnavailableError,
    explain as explain_with_llm,
)
from ocr import OcrModelLoadError, recognize
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


class ExplainRequest(BaseModel):
    sentence: str = Field(min_length=1)
    word: str = Field(min_length=1)
    known_kanji: list[str]
    known_words: list[str]


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
    return {"tokens": mask_text(request.text, set(request.known_kanji))}


@app.post("/explain")
def post_explain(request: ExplainRequest):
    try:
        return explain_with_llm(
            sentence=request.sentence,
            word=request.word,
            known_kanji=request.known_kanji,
            known_words=request.known_words,
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


@app.get("/cards")
def cards():
    return {"cards": get_cards()}
