"""Structured JSON intent-vs-outcome logging and OpenTelemetry tracing for SpecAlign."""

from __future__ import annotations

import functools
import hashlib
import json
import logging
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.callbacks import redact_pii

_RAW_CONTENT_KEYS: frozenset[str] = frozenset({"raw_text", "content", "document_body"})


class JsonLogFormatter(logging.Formatter):
    """Formats Python LogRecords as single-line JSON with automatic PII scrubbing."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_pii(record.getMessage()),
        }
        for key in (
            "event_type",
            "trace_id",
            "tool_name",
            "arguments",
            "status",
            "latency_ms",
            "error_code",
            "finding_count",
        ):
            val = getattr(record, key, None)
            if val is not None:
                payload[key] = val
        return json.dumps(payload, default=str)


def get_structured_logger(name: str = "specalign.tools") -> logging.Logger:
    """Return a JSON-formatted logger without duplicating handlers."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonLogFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def sanitize_args_for_log(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Strip raw document bodies and scrub PII before writing structured tool intent logs."""
    sanitized: dict[str, Any] = {}
    for key, val in kwargs.items():
        if key == "tool_context":
            continue
        if key in _RAW_CONTENT_KEYS and isinstance(val, str):
            digest = hashlib.sha256(val.encode("utf-8")).hexdigest()[:12]
            sanitized[f"{key}_sha256"] = digest
            sanitized[f"{key}_chars"] = len(val)
        elif isinstance(val, str):
            sanitized[key] = redact_pii(val)
        elif isinstance(val, list):
            sanitized[key] = [
                redact_pii(item) if isinstance(item, str) else item for item in val
            ]
        else:
            sanitized[key] = val
    return sanitized


def _get_otel_tracer() -> Any | None:
    try:
        from opentelemetry import trace  # type: ignore[import-not-found]

        return trace.get_tracer("specalign.tools")
    except ImportError:
        return None


def trace_tool_call(
    logger_name: str = "specalign.tools",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator emitting correlated `tool_intent` and `tool_outcome` JSON logs and OTel spans."""

    def _decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        tool_name = getattr(func, "__name__", repr(func))

        @functools.wraps(func)
        def _wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = get_structured_logger(logger_name)
            trace_id = uuid.uuid4().hex[:16]
            safe_args = sanitize_args_for_log(kwargs)
            logger.info(
                "Tool intent: %s",
                tool_name,
                extra={
                    "event_type": "tool_intent",
                    "trace_id": trace_id,
                    "tool_name": tool_name,
                    "arguments": safe_args,
                },
            )

            tracer = _get_otel_tracer()
            start = time.perf_counter()
            try:
                if tracer is not None:
                    with tracer.start_as_current_span(f"tool.{tool_name}") as span:
                        span.set_attribute("specalign.tool_name", tool_name)
                        span.set_attribute("specalign.trace_id", trace_id)
                        result = func(*args, **kwargs)
                        span.set_attribute(
                            "specalign.status",
                            result.get("status", "unknown")
                            if isinstance(result, dict)
                            else "success",
                        )
                else:
                    result = func(*args, **kwargs)
            except Exception as exc:
                latency_ms = round((time.perf_counter() - start) * 1000.0, 2)
                logger.error(
                    "Tool outcome: %s (exception)",
                    tool_name,
                    extra={
                        "event_type": "tool_outcome",
                        "trace_id": trace_id,
                        "tool_name": tool_name,
                        "status": "exception",
                        "latency_ms": latency_ms,
                        "error_code": type(exc).__name__,
                    },
                )
                raise

            latency_ms = round((time.perf_counter() - start) * 1000.0, 2)
            status = (
                result.get("status", "unknown")
                if isinstance(result, dict)
                else "success"
            )
            error_code = result.get("error_code") if isinstance(result, dict) else None
            logger.info(
                "Tool outcome: %s (%s)",
                tool_name,
                status,
                extra={
                    "event_type": "tool_outcome",
                    "trace_id": trace_id,
                    "tool_name": tool_name,
                    "status": status,
                    "latency_ms": latency_ms,
                    "error_code": error_code,
                },
            )
            return result

        return _wrapper

    return _decorator
