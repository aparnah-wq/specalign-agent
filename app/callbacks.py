"""ADK pre-model guardrails (PII redaction & prompt-injection defense) and async Memory Bank hooks."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger("specalign.callbacks")

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CREDIT_CARD_RE = re.compile(
    r"(?<!\d)(?:(?:\d{4}[-\s]?){3}\d{4}|3[47]\d{2}[-\s]?\d{6}[-\s]?\d{5})(?!\d)"
)
_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s])\d{3}[-.\s]\d{4}(?!\d)"
)
_SECRET_RE = re.compile(
    r"(?:Bearer\s+[A-Za-z0-9\-._~+/]+=*|AIza[0-9A-Za-z\-_]{20,}|sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,})"
)

_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\bignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bdisregard\s+(?:all\s+)?(?:previous|prior|system)\s+(?:instructions|prompts?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\boverride\s+your\s+(?:system\s+)?(?:instructions|rules|prompt)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\breveal\s+(?:your\s+)?(?:hidden\s+)?system\s+prompt\b", re.IGNORECASE
    ),
)


def redact_pii(text: str) -> str:
    """Deterministically mask emails, SSNs, credit cards, phone numbers, and API/Bearer secrets."""
    if not text:
        return text
    cleaned = _SECRET_RE.sub("[REDACTED_SECRET]", text)
    cleaned = _EMAIL_RE.sub("[REDACTED_EMAIL]", cleaned)
    cleaned = _SSN_RE.sub("[REDACTED_SSN]", cleaned)
    cleaned = _CREDIT_CARD_RE.sub("[REDACTED_CREDIT_CARD]", cleaned)
    cleaned = _PHONE_RE.sub("[REDACTED_PHONE]", cleaned)
    return cleaned


def detect_prompt_injection(text: str) -> bool:
    """Return True if untrusted input contains a known prompt-injection override phrase."""
    if not text:
        return False
    return any(pattern.search(text) for pattern in _INJECTION_PATTERNS)


def _build_blocked_response(reason_code: str, message: str) -> Any:
    """Build an ADK LlmResponse (or structured dict offline) to short-circuit unsafe calls."""
    envelope = json.dumps(
        {
            "status": "blocked_or_needs_input",
            "error_code": reason_code,
            "message": message,
            "recovery_guidance": (
                "Remove instruction-override phrases from the submitted document or prompt "
                "and re-submit for alignment analysis."
            ),
        }
    )
    try:
        from google.adk.models.llm_response import LlmResponse  # type: ignore[import-not-found]
        from google.genai import types  # type: ignore[import-not-found]

        return LlmResponse(
            content=types.ModelContent(parts=[types.Part.from_text(text=envelope)])
        )
    except ImportError:
        return {"blocked": True, "text": envelope}


def before_model_guardrail_callback(
    callback_context: Any,
    llm_request: Any,
) -> Any | None:
    """ADK before_model_callback that redacts PII in-place and blocks prompt-injection attempts.

    Returns `None` when the request is safe so execution proceeds normally, or
    returns a blocking `LlmResponse` to skip the model call cleanly.
    """
    contents = getattr(llm_request, "contents", None) or []
    for content in contents:
        parts = getattr(content, "parts", None) or []
        for part in parts:
            text = getattr(part, "text", None)
            if not isinstance(text, str) or not text:
                continue
            if detect_prompt_injection(text):
                agent_name = getattr(callback_context, "agent_name", "unknown")
                logger.warning(
                    "Blocked prompt-injection attempt before model call on agent '%s'.",
                    agent_name,
                )
                return _build_blocked_response(
                    "PROMPT_INJECTION_DETECTED",
                    "Detected an instruction-override pattern inside the input payload.",
                )
            sanitized = redact_pii(text)
            if sanitized != text:
                part.text = sanitized
    return None


async def add_session_to_memory_callback(callback_context: Any) -> None:
    """ADK after_agent_callback persisting completed turns to Agent Memory Bank asynchronously.

    Handles `ValueError` gracefully when running locally in `agents-cli playground`
    without a configured Vertex AI Memory Bank service.
    """
    try:
        await callback_context.add_session_to_memory()
    except ValueError as exc:
        logger.warning(
            "Skipping async memory extraction (no memory service configured): %s", exc
        )
