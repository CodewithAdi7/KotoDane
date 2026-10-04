from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from db import (
    create_or_tap_card,
    get_cards,
    get_known_kanji,
    init_db,
    seed_known_kanji,
    update_known_kanji,
)
from dictionary import get_jamdict, lookup_word
from tokenizer import mask_text


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    get_jamdict()
    yield


app = FastAPI(lifespan=lifespan)


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
