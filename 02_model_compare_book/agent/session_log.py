"""세션 로그 — ../output/agent.log 에 기록."""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, TypeVar

from .config import LOG_PATH

F = TypeVar("F", bound=Callable[..., Any])

LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"
SEPARATOR = "=" * 80
SUBSEPARATOR = "-" * 80

_logger: logging.Logger | None = None
_session_start_time: datetime | None = None


def _timestamp() -> str:
    return datetime.now().strftime(LOG_DATEFMT)


def _format_elapsed(delta: timedelta) -> str:
    total = int(delta.total_seconds())
    minutes, seconds = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def _emit(message: str, level: int = logging.INFO) -> None:
    _get_logger().log(level, message)
    level_name = logging.getLevelName(level)
    print(f"{_timestamp()} | {level_name} | {message}", file=sys.stderr)


def _get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("model_compare_book")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
        handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT))
        logger.addHandler(handler)

    _logger = logger
    return logger


def log_event(message: str, level: int = logging.INFO) -> None:
    _emit(message, level)


def log_session_start(**meta: Any) -> None:
    global _session_start_time
    _session_start_time = datetime.now()
    logger = _get_logger()
    logger.info("")
    logger.info(SEPARATOR)
    parts = ["SESSION START", _timestamp()]
    for key, value in meta.items():
        parts.append(f"{key}={value}")
    header = " | ".join(parts)
    logger.info(header)
    logger.info(SEPARATOR)
    print(f"\n{SEPARATOR}\n{_timestamp()} | INFO | {header}\n{SEPARATOR}", file=sys.stderr)


def log_session_end(**meta: Any) -> None:
    logger = _get_logger()
    if _session_start_time is not None:
        meta.setdefault("elapsed", _format_elapsed(datetime.now() - _session_start_time))
    logger.info(SUBSEPARATOR)
    parts = ["SESSION END", _timestamp()]
    for key, value in meta.items():
        parts.append(f"{key}={value}")
    footer = " | ".join(parts)
    logger.info(footer)
    logger.info(SEPARATOR)
    logger.info("")
    print(f"\n{SUBSEPARATOR}\n{_timestamp()} | INFO | {footer}\n{SEPARATOR}\n", file=sys.stderr)


def log_tool(name: str) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            args_repr = ", ".join(repr(a) for a in args)
            kwargs_repr = ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
            params = ", ".join(filter(None, [args_repr, kwargs_repr]))
            log_event(f"TOOL START | {name}({params})")
            try:
                result = func(*args, **kwargs)
                log_event(f"TOOL OK   | {name} -> {_summarize(result)}")
                return result
            except Exception as exc:
                log_event(f"TOOL FAIL | {name} -> {exc}", level=logging.ERROR)
                raise

        return wrapper  # type: ignore[return-value]

    return decorator


def _summarize(result: Any, max_len: int = 200) -> str:
    text = repr(result)
    if len(text) > max_len:
        return text[: max_len - 3] + "..."
    return text
