"""Module provides universal interface for diffenet JSON implementations."""

from typing import Any

import orjson
from orjson import JSONDecodeError


__all__ = (
    "JSONDecodeError",
    "loads",
    "dumps",
)


def loads(raw_data: bytes | str) -> Any:
    return orjson.loads(raw_data)


def dumps(obj: Any) -> str:
    return orjson.dumps(obj).decode("utf-8")
