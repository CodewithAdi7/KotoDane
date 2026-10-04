"""Small synchronous client for the local Ollama chat API."""

import json
import os
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from prompts import EXPLAIN_JSON_SCHEMA, build_explain_messages


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


def _parse_explanation(content: str) -> dict[str, str]:
    """Parse and validate the model's JSON response, tolerating code fences."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("{"), content.rfind("}")
        if start < 0 or end <= start:
            raise OllamaResponseError("Ollama returned invalid JSON for the explanation.")
        try:
            data = json.loads(content[start : end + 1])
        except json.JSONDecodeError as exc:
            raise OllamaResponseError("Ollama returned invalid JSON for the explanation.") from exc

    if not isinstance(data, dict):
        raise OllamaResponseError("Ollama returned JSON in an unexpected format.")
    explanation_ja = data.get("explanation_ja")
    hint_en = data.get("hint_en")
    if not isinstance(explanation_ja, str) or not explanation_ja.strip():
        raise OllamaResponseError("Ollama response is missing a usable explanation_ja.")
    if not isinstance(hint_en, str) or not hint_en.strip():
        raise OllamaResponseError("Ollama response is missing a usable hint_en.")
    return {"explanation_ja": explanation_ja.strip(), "hint_en": hint_en.strip()}


def explain(
    sentence: str,
    word: str,
    known_kanji: list[str],
    known_words: list[str] | None = None,
) -> dict[str, str]:
    """Ask Ollama for a beginner-friendly explanation in the requested JSON shape."""
    model = os.getenv("OLLAMA_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    base_url = os.getenv("OLLAMA_HOST", DEFAULT_OLLAMA_URL).rstrip("/")
    try:
        timeout = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
    except ValueError:
        timeout = DEFAULT_TIMEOUT_SECONDS

    payload = {
        "model": model,
        "messages": build_explain_messages(sentence, word, known_kanji, known_words or []),
        "format": EXPLAIN_JSON_SCHEMA,
        "stream": False,
        # Qwen3 otherwise spends the short output budget on its hidden reasoning field.
        "think": False,
        "options": {"temperature": 0.2, "num_predict": 180, "num_ctx": 4096},
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
        raise OllamaResponseError("Ollama response did not include message content.") from exc
    if not isinstance(content, str):
        raise OllamaResponseError("Ollama returned message content in an unexpected format.")
    return _parse_explanation(content)
