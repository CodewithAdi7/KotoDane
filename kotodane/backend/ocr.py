"""Lazy, process-wide manga-ocr model access."""

from __future__ import annotations

from io import BytesIO
from threading import Lock

from PIL import Image


_model = None
_model_lock = Lock()


class OcrModelLoadError(RuntimeError):
    """Raised when manga-ocr or its model cannot be initialized."""


def recognize(image_bytes: bytes) -> str:
    """Recognize Japanese text from encoded image bytes."""
    global _model

    with Image.open(BytesIO(image_bytes)) as image:
        image = image.convert("RGB")

    with _model_lock:
        if _model is None:
            try:
                from manga_ocr import MangaOcr

                _model = MangaOcr()
            except Exception as exc:
                raise OcrModelLoadError(
                    "Could not load manga-ocr or download its model."
                ) from exc

        return _model(image)
