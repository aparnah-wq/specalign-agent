"""Minimal stdlib fallback shim for Pydantic v2 APIs in offline test environments.

Used only when the real `pydantic` package is not installed (for example, on a
minimal Linux host without pip/uv). In Cloud Shell, local uv environments, and
Agent Runtime containers, `app/schemas.py` imports real `pydantic>=2.7.0`.
"""

from __future__ import annotations

import typing
from collections.abc import Callable
from enum import Enum
from typing import Any, get_args, get_origin

_MISSING = object()


class SchemaValidationError(ValueError):
    """Raised when a payload fails field type, range, or enum validation."""


class _FieldSpec:
    """Stores Field constraints for stdlib fallback validation."""

    def __init__(
        self,
        default: Any = _MISSING,
        *,
        default_factory: Callable[[], Any] | None = None,
        description: str = "",
        ge: float | None = None,
        le: float | None = None,
        min_length: int | None = None,
        max_length: int | None = None,
    ) -> None:
        self.default = default
        self.default_factory = default_factory
        self.description = description
        self.ge = ge
        self.le = le
        self.min_length = min_length
        self.max_length = max_length


def Field(
    default: Any = _MISSING,
    *,
    default_factory: Callable[[], Any] | None = None,
    description: str = "",
    ge: float | None = None,
    le: float | None = None,
    min_length: int | None = None,
    max_length: int | None = None,
) -> Any:
    """Declare field defaults and validation bounds matching Pydantic v2 Field()."""
    if default is Ellipsis:
        default = _MISSING
    return _FieldSpec(
        default=default,
        default_factory=default_factory,
        description=description,
        ge=ge,
        le=le,
        min_length=min_length,
        max_length=max_length,
    )


def _coerce_value(name: str, raw: Any, annotation: Any) -> Any:
    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is typing.Union or str(origin) == "types.UnionType":
        if raw is None and type(None) in args:
            return None
        for option in args:
            if option is type(None):
                continue
            try:
                return _coerce_value(name, raw, option)
            except SchemaValidationError:
                continue
        raise SchemaValidationError(
            f"Field '{name}' value {raw!r} does not match {annotation}."
        )

    if origin is typing.Literal:
        if raw not in args:
            raise SchemaValidationError(
                f"Field '{name}' must be one of {args}, got {raw!r}."
            )
        return raw

    if origin is list:
        if not isinstance(raw, list):
            raise SchemaValidationError(f"Field '{name}' must be a list.")
        item_type = args[0] if args else Any
        return [
            _coerce_value(f"{name}[{idx}]", item, item_type)
            for idx, item in enumerate(raw)
        ]

    if isinstance(annotation, type) and issubclass(annotation, Enum):
        if isinstance(raw, annotation):
            return raw
        try:
            return annotation(raw)
        except ValueError as exc:
            raise SchemaValidationError(
                f"Field '{name}' invalid enum value {raw!r} for {annotation.__name__}."
            ) from exc

    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        if isinstance(raw, annotation):
            return raw
        if isinstance(raw, dict):
            return annotation.model_validate(raw)
        raise SchemaValidationError(
            f"Field '{name}' expected object for {annotation.__name__}."
        )

    if annotation is int:
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise SchemaValidationError(
                f"Field '{name}' must be an integer, got {raw!r}."
            )
        return raw

    if annotation is float:
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise SchemaValidationError(f"Field '{name}' must be numeric, got {raw!r}.")
        return float(raw)

    if annotation is bool:
        if not isinstance(raw, bool):
            raise SchemaValidationError(
                f"Field '{name}' must be a boolean, got {raw!r}."
            )
        return raw

    if annotation is str:
        if not isinstance(raw, str):
            raise SchemaValidationError(
                f"Field '{name}' must be a string, got {raw!r}."
            )
        return raw

    return raw


def _serialize(value: Any, json_mode: bool) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json" if json_mode else "python")
    if isinstance(value, Enum):
        return value.value if json_mode else value
    if isinstance(value, list):
        return [_serialize(v, json_mode) for v in value]
    if isinstance(value, dict):
        return {k: _serialize(v, json_mode) for k, v in value.items()}
    return value


class BaseModel:
    """Lightweight BaseModel compatible with Pydantic v2 validation & serialization calls."""

    def __init__(self, **data: Any) -> None:
        hints = typing.get_type_hints(self.__class__)
        for field_name, field_type in hints.items():
            if field_name.startswith("_"):
                continue
            spec = getattr(self.__class__, field_name, _MISSING)
            if field_name in data:
                raw_val = data[field_name]
            elif isinstance(spec, _FieldSpec):
                if spec.default_factory is not None:
                    raw_val = spec.default_factory()
                elif spec.default is not _MISSING:
                    raw_val = spec.default
                else:
                    raise SchemaValidationError(
                        f"Missing required field '{field_name}'."
                    )
            elif spec is not _MISSING:
                raw_val = spec
            else:
                raise SchemaValidationError(f"Missing required field '{field_name}'.")

            coerced = _coerce_value(field_name, raw_val, field_type)
            if isinstance(spec, _FieldSpec):
                if spec.ge is not None and coerced < spec.ge:
                    raise SchemaValidationError(
                        f"Field '{field_name}' must be >= {spec.ge}, got {coerced}."
                    )
                if spec.le is not None and coerced > spec.le:
                    raise SchemaValidationError(
                        f"Field '{field_name}' must be <= {spec.le}, got {coerced}."
                    )
                if spec.min_length is not None and len(coerced) < spec.min_length:
                    raise SchemaValidationError(
                        f"Field '{field_name}' length must be >= {spec.min_length}."
                    )
                if spec.max_length is not None and len(coerced) > spec.max_length:
                    raise SchemaValidationError(
                        f"Field '{field_name}' length must be <= {spec.max_length}."
                    )
            setattr(self, field_name, coerced)

    @classmethod
    def model_validate(cls, obj: Any) -> Any:
        if isinstance(obj, cls):
            return obj
        if not isinstance(obj, dict):
            raise SchemaValidationError(f"Expected dict to validate {cls.__name__}.")
        return cls(**obj)

    def model_dump(self, mode: str = "python") -> dict[str, Any]:
        json_mode = mode == "json"
        hints = typing.get_type_hints(self.__class__)
        return {
            name: _serialize(getattr(self, name), json_mode)
            for name in hints
            if not name.startswith("_")
        }

    @classmethod
    def model_json_schema(cls) -> dict[str, Any]:
        hints = typing.get_type_hints(cls)
        properties: dict[str, dict[str, Any]] = {}
        required: list[str] = []
        for name, field_type in hints.items():
            if name.startswith("_"):
                continue
            spec = getattr(cls, name, _MISSING)
            desc = spec.description if isinstance(spec, _FieldSpec) else ""
            properties[name] = {
                "title": name,
                "type": str(field_type),
                "description": desc,
            }
            if (
                not isinstance(spec, _FieldSpec)
                or (spec.default is _MISSING and spec.default_factory is None)
            ) and (spec is _MISSING or isinstance(spec, _FieldSpec)):
                required.append(name)
        return {
            "title": cls.__name__,
            "type": "object",
            "properties": properties,
            "required": required,
        }
