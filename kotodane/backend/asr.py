"""Lazy Japanese speech recognition using faster-whisper."""

from __future__ import annotations

import os
from threading import Lock
from typing import Any


class AsrModelLoadError(RuntimeError):
    """The model could not be imported or downloaded."""


class AsrTranscriptionError(RuntimeError):
    """The model could not decode the supplied audio."""


_model: Any | None = None
_model_size: str | None = None
_model_lock = Lock()


def _get_model() -> Any:
    global _model, _model_size
    model_size = os.environ.get("WHISPER_MODEL_SIZE", "small").strip() or "small"
    if _model is not None and _model_size == model_size:
        return _model

    with _model_lock:
        if _model is not None and _model_size == model_size:
            return _model
        try:
            from faster_whisper import WhisperModel

            # CPU int8 works without separately installed CUDA/cuDNN libraries.
            _model = WhisperModel(model_size, device="cpu", compute_type="int8")
            _model_size = model_size
        except Exception as exc:
            raise AsrModelLoadError(
                f"Could not load Whisper model '{model_size}'. Check the faster-whisper "
                "installation and internet access for its first model download."
            ) from exc
    return _model


def transcribe(audio_path: str) -> list[dict[str, float | str]]:
    """Transcribe an audio file in Japanese and return timestamped segments."""
    model = _get_model()
    try:
        segments, _info = model.transcribe(
            audio_path,
            language="ja",
            vad_filter=True,
            beam_size=5,
        )
        return [
            {"start": float(segment.start), "end": float(segment.end), "text": segment.text.strip()}
            for segment in segments
            if segment.text.strip()
        ]
    except Exception as exc:
        raise AsrTranscriptionError("Whisper could not transcribe this audio file.") from exc
