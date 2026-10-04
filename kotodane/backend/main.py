from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from tokenizer import mask_text

app = FastAPI()


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
