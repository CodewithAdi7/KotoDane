"""Small synchronous client for the local Ollama chat API."""

import json
import os
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from prompts import (
    CASUAL_JSON_SCHEMA,
    EXPLAIN_JSON_SCHEMA,
    PRACTICE_JSON_SCHEMA,
    build_casual_messages,
    build_explain_messages,
    build_practice_messages,
)


DEFAULT_MODEL = "qwen3:4b"
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_TIMEOUT_SECONDS = 120


class OllamaError(RuntimeError):
    """Base exception for local Ollama failures."""


class OllamaUnavailableError(OllamaError):
    pass


class OllamaTimeoutError(OllamaError):
    pass


class OllamaResponseError(OllamaError):
    pass


def _parse_json_object(content: str, feature: str) -> dict:
    """Parse a JSON object, tolerating surrounding Markdown code fences."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("{"), content.rfind("}")
        if start < 0 or end <= start:
            raise OllamaResponseError(f"Ollama returned invalid JSON for {feature}.")
        try:
            data = json.loads(content[start : end + 1])
        except json.JSONDecodeError as exc:
            raise OllamaResponseError(f"Ollama returned invalid JSON for {feature}.") from exc
    if not isinstance(data, dict):
        raise OllamaResponseError(f"Ollama returned JSON in an unexpected format for {feature}.")
    return data


def _chat_json(messages: list[dict[str, str]], schema: dict, feature: str,
               max_predict: int = 220) -> dict:
    model = os.getenv("OLLAMA_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    base_url = os.getenv("OLLAMA_HOST", DEFAULT_OLLAMA_URL).rstrip("/")
    try:
        timeout = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
    except ValueError:
        timeout = DEFAULT_TIMEOUT_SECONDS

    payload = {
        "model": model,
        "messages": messages,
        "format": schema,
        "stream": False,
        # Qwen3 otherwise spends a short output budget on hidden reasoning.
        "think": False,
        "options": {"temperature": 0.2, "num_predict": max_predict, "num_ctx": 4096},
    }
    request = Request(
        f"{base_url}/api/chat",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=max(1, timeout)) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if exc.code == 404 or "model" in detail.lower() and "not found" in detail.lower():
            raise OllamaUnavailableError(
                f"Ollama model '{model}' is not installed. Run: ollama pull {model}"
            ) from exc
        raise OllamaResponseError(f"Ollama returned HTTP {exc.code}: {detail[:300]}") from exc
    except (URLError, ConnectionError, OSError) as exc:
        if isinstance(exc, (TimeoutError, socket.timeout)) or isinstance(
            getattr(exc, "reason", None), (TimeoutError, socket.timeout)
        ):
            raise OllamaTimeoutError(
                f"Ollama did not respond within {timeout:g} seconds. Try again or increase "
                "OLLAMA_TIMEOUT_SECONDS."
            ) from exc
        raise OllamaUnavailableError(
            f"Cannot connect to Ollama at {base_url}. Start the Ollama app, then retry."
        ) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise OllamaTimeoutError(
            f"Ollama did not respond within {timeout:g} seconds. Try again or increase "
            "OLLAMA_TIMEOUT_SECONDS."
        ) from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise OllamaResponseError("Ollama returned an unreadable response.") from exc

    try:
        content = result["message"]["content"]
    except (KeyError, TypeError) as exc:
        raise OllamaResponseError(f"Ollama response did not include {feature} content.") from exc
    if not isinstance(content, str):
        raise OllamaResponseError(f"Ollama returned {feature} content in an unexpected format.")
    return _parse_json_object(content, feature)


def _required_string(data: dict, field: str, feature: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise OllamaResponseError(f"Ollama {feature} response is missing a usable {field}.")
    return value.strip()


def explain(
    sentence: str,
    word: str,
    known_kanji: list[str],
    known_words: list[str] | None = None,
    feedback: str | None = None,
) -> dict[str, str]:
    messages = build_explain_messages(
        sentence, word, known_kanji, known_words or [], feedback=feedback
    )
    data = _chat_json(messages, EXPLAIN_JSON_SCHEMA, "explanation")
    return {
        "explanation_ja": _required_string(data, "explanation_ja", "explanation"),
        "hint_en": _required_string(data, "hint_en", "explanation"),
    }


def generate_practice(
    word: str,
    known_kanji: list[str],
    known_words: list[str],
    count: int = 3,
    feedback: str | None = None,
) -> dict:
    messages = build_practice_messages(word, known_kanji, known_words, count, feedback)
    data = _chat_json(
        messages,
        PRACTICE_JSON_SCHEMA,
        "practice sentences",
        max_predict=max(300, count * 150),
    )
    sentences = data.get("sentences")
    if not isinstance(sentences, list) or len(sentences) != count:
        raise OllamaResponseError(
            f"Ollama practice response must contain exactly {count} sentences."
        )
    normalized = []
    for item in sentences:
        if not isinstance(item, dict):
            raise OllamaResponseError("Ollama returned a malformed practice sentence.")
        normalized.append({
            "sentence": _required_string(item, "sentence", "practice"),
            "hint_en": _required_string(item, "hint_en", "practice"),
        })
    return {"sentences": normalized}


def explain_casual(
    sentence: str,
    known_kanji: list[str],
    known_words: list[str],
    feedback: str | None = None,
) -> dict[str, str]:
    messages = build_casual_messages(sentence, known_kanji, known_words, feedback)
    data = _chat_json(messages, CASUAL_JSON_SCHEMA, "casual explanation")
    return {
        "explanation_ja": _required_string(data, "explanation_ja", "casual explanation"),
        "hint_en": _required_string(data, "hint_en", "casual explanation"),
    }
