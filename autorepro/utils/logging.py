"""
Logging utilities for AutoRepro.

Provides consistent configuration, optional structured (JSON) logging, and logger
adapters for contextual logging.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from collections.abc import MutableMapping
from typing import Any

AUTOREPRO_LOGGER_NAME = "autorepro"


def _coerce_level(level: int | str | None) -> int:
    if isinstance(level, int):
        return level
    if isinstance(level, str):
        lookup = {
            "CRITICAL": logging.CRITICAL,
            "ERROR": logging.ERROR,
            "WARNING": logging.WARNING,
            "INFO": logging.INFO,
            "DEBUG": logging.DEBUG,
            "NOTSET": logging.NOTSET,
        }
        return lookup.get(level.upper(), logging.INFO)
    return logging.INFO


class JsonFormatter(logging.Formatter):
    """Render log records as JSON with useful context fields."""

    default_time_format = "%Y-%m-%dT%H:%M:%S"
    default_msec_format = "%s.%03dZ"

    def format(self, record: logging.LogRecord) -> str:
        # Base fields
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, self.default_time_format),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
            "msg": record.getMessage(),
        }

        # Include extras (fields not in LogRecord defaults)
        reserved = set(vars(logging.makeLogRecord({})).keys())
        for key, value in record.__dict__.items():
            if key not in reserved and key not in payload:
                payload[key] = value

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, separators=(",", ":"))

    def formatTime(
        self, record: logging.LogRecord, datefmt: str | None = None
    ) -> str:  # noqa: N802
        ct = self.converter(record.created)
        if datefmt:
            s = time.strftime(datefmt, ct)
        else:
            s = time.strftime(self.default_time_format, ct)
        return self.default_msec_format % (s, record.msecs)

    def converter(self, timestamp: float | None):
        # Use UTC timestamps for easier aggregation in logs
        return time.gmtime(timestamp or time.time())


class KeyValueFormatter(logging.Formatter):
    """Key=value text formatter suitable for local debugging."""

    def format(self, record: logging.LogRecord) -> str:
        base = (
            f"ts={self.formatTime(record)} level={record.levelname} "
            f"logger={record.name} where={record.module}:{record.lineno}:{record.funcName} "
            f'msg="{record.getMessage()}"'
        )

        reserved = set(vars(logging.makeLogRecord({})).keys())
        extras: list[str] = []
        for key, value in record.__dict__.items():
            if key not in reserved and key not in {"message", "asctime"}:
                try:
                    extras.append(f"{key}={json.dumps(value, separators=(',',':'))}")
                except Exception:
                    extras.append(f'{key}="{value}"')
        if record.exc_info:
            try:
                extras.append(
                    f"exc={json.dumps(self.formatException(record.exc_info))}"
                )
            except Exception:
                pass
        return base + (" " + " ".join(extras) if extras else "")

    def formatTime(
        self, record: logging.LogRecord, datefmt: str | None = None
    ) -> str:  # noqa: N802
        # ISO8601-ish UTC time
        ct = time.gmtime(record.created)
        return time.strftime("%Y-%m-%dT%H:%M:%S", ct) + f".{int(record.msecs):03d}Z"


class ContextAdapter(logging.LoggerAdapter):
    """LoggerAdapter that merges provided context into each log record."""

    def process(
        self, msg: str, kwargs: MutableMapping[str, Any]
    ) -> tuple[str, MutableMapping[str, Any]]:
        extra: dict[str, Any] = dict(getattr(self, "extra", {}) or {})
        kw_extra = kwargs.get("extra")
        if isinstance(kw_extra, dict):
            extra.update(kw_extra)
        kwargs = dict(kwargs)  # create a local mutable copy
        if extra:
            kwargs["extra"] = extra
        return msg, kwargs


def get_logger(
    name: str | None = None, **context: Any
) -> logging.Logger | ContextAdapter:
    """
    Return a logger (or adapter) under the AutoRepro namespace.

    If context is provided, a ContextAdapter is returned so that the context appears
    with each log message (and in JSON payloads).
    """
    full_name = AUTOREPRO_LOGGER_NAME if not name else name
    logger = logging.getLogger(full_name)
    return ContextAdapter(logger, context) if context else logger


def configure_logging(
    level: int | str | None = None,
    fmt: str | None = None,
    stream=sys.stderr,
) -> None:
    """
    Configure global logging with consistent formatting.

    - level: numeric or string level; defaults to INFO
    - fmt: 'json' or 'text' (key=value). Defaults from AUTOREPRO_LOG_FORMAT env.
    """
    resolved_level = _coerce_level(level)
    env_fmt = os.environ.get("AUTOREPRO_LOG_FORMAT", "").strip().lower()
    resolved_fmt = (fmt or env_fmt or "text").lower()
    if resolved_fmt not in {"json", "text"}:
        resolved_fmt = "text"

    # Use a stable, non-capturing stream to avoid pytest closing issues across tests
    real_stream = sys.__stderr__ if stream is sys.stderr else stream
    root = logging.getLogger()
    root.setLevel(resolved_level)

    # Try to reuse an existing stream handler to the same stream to avoid duplicates
    desired_formatter: logging.Formatter = (
        JsonFormatter() if resolved_fmt == "json" else KeyValueFormatter()
    )
    reused = False
    for h in root.handlers:
        if (
            isinstance(h, logging.StreamHandler)
            and getattr(h, "stream", None) is real_stream
        ):
            h.setFormatter(desired_formatter)
            h.setLevel(resolved_level)
            reused = True
            break

    if not reused:
        handler = logging.StreamHandler(real_stream)
        handler.setFormatter(desired_formatter)
        handler.setLevel(resolved_level)
        root.addHandler(handler)
    # Ensure our package logger propagates (so root handler applies)
    pkg_logger = logging.getLogger(AUTOREPRO_LOGGER_NAME)
    # Keep package logger level unset so root controls effective level
    pkg_logger.setLevel(logging.NOTSET)
    pkg_logger.propagate = True
