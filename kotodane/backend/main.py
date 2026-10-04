from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi import Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from dictionary import get_jamdict, lookup_word
from tokenizer import mask_text


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_jamdict()
    yield


app = FastAPI(lifespan=lifespan)


class RenderRequest(BaseModel):
    text: str
    known_kanji: list[str]

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
