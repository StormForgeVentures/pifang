"""Structured errors and exit codes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SUCCESS = 0
VALIDATION = 1
MISSING_DEPENDENCY = 2
PROCESSING = 3
PARTIAL_BATCH = 4


@dataclass
class PifangError(Exception):
    """Base error with machine-readable fields."""

    message: str
    error_code: str
    exit_code: int = VALIDATION
    recovery: dict[str, Any] | None = field(default=None)

    def __str__(self) -> str:
        return self.message

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": False,
            "error_code": self.error_code,
            "message": self.message,
            "exit_code": self.exit_code,
        }
        if self.recovery:
            payload["recovery"] = self.recovery
        return payload


class ValidationError(PifangError):
    def __init__(self, message: str, error_code: str = "VALIDATION_ERROR", recovery: dict | None = None):
        super().__init__(message, error_code, VALIDATION, recovery)


class MissingDependencyError(PifangError):
    def __init__(self, message: str, recovery: dict | None = None):
        super().__init__(message, "MISSING_DEPENDENCY", MISSING_DEPENDENCY, recovery)


class ProcessingError(PifangError):
    def __init__(self, message: str, error_code: str = "PROCESSING_ERROR", recovery: dict | None = None):
        super().__init__(message, error_code, PROCESSING, recovery)


class PartialBatchError(PifangError):
    def __init__(self, message: str, recovery: dict | None = None):
        super().__init__(message, "PARTIAL_BATCH", PARTIAL_BATCH, recovery)
