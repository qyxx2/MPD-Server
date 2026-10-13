"""Small, safe console diagnostics. No configuration or request bodies enter logs."""

from __future__ import annotations

import hashlib
import json
import logging
import sys
import traceback
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from threading import Lock
from typing import TextIO

_operation_id: ContextVar[str | None] = ContextVar('log_operation_id', default=None)
_generation: ContextVar[int | None] = ContextVar('log_generation', default=None)
_LEGACY_MESSAGES = frozenset({
    'State snapshot unavailable', 'State observation failed',
    'State observation cache refresh failed', 'Playback recovery failed',
    'Commit visibility registration failed for database %s',
    'Commit visibility failure handler failed for database %s',
    'Post-commit notification failed for database %s',
    'Realtime initial snapshot unavailable connection=%s',
    'Realtime delivery failed connection=%s', 'Realtime close failed connection=%s',
    'MPD URI mapping rejected direction=local_to_mpd command=%s',
    'MPD URI mapping rejected direction=mpd_to_local command=%s',
    'Skipping unavailable completion candidate %s',
})
_lock = Lock()
_logger = logging.getLogger('server.app')


@contextmanager
def log_context(*, operation_id: str | None = None, generation: int | None = None):
    operation_token = _operation_id.set(operation_id)
    generation_token = _generation.set(generation)
    try:
        yield
    finally:
        _operation_id.reset(operation_token)
        _generation.reset(generation_token)


def request_operation_id(key: str) -> str:
    # A stable short correlation digest; never emit the client's opaque key.
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def log_event(event: str, *, level: int = logging.INFO, **fields) -> None:
    """Call sites supply fixed event names/codes and safe scalar facts only.

    Logging is observational: even a broken user-installed handler cannot change
    the business result. Cancellation and other BaseExceptions still propagate.
    """
    try:
        _logger.log(level, event, extra={'diagnostic': {
            'event': event, 'operation_id': _operation_id.get(),
            'generation': _generation.get(), **fields,
        }})
    except Exception:  # noqa: BLE001, S110 - diagnostics must not change business results
        pass


class _SafeFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        row = {
            'time': datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            'level': record.levelname, 'source': record.name,
        }
        diagnostic = getattr(record, 'diagnostic', None)
        if diagnostic is not None:
            row.update(diagnostic)
        else:
            # Keep legacy error location/type without interpolated arguments,
            # exception messages, source lines or locals (all may contain secrets).
            row['description'] = (record.msg.replace('%s', '[redacted]')
                                  if isinstance(record.msg, str) and record.msg in _LEGACY_MESSAGES
                                  else 'Application diagnostic')
            row.update(event='legacy_record', function=record.funcName, line=record.lineno,
                       operation_id=_operation_id.get(), generation=_generation.get())
        if record.exc_info:
            row['error_type'] = record.exc_info[0].__name__
            row['frames'] = [
                {'file': frame.filename, 'function': frame.name, 'line': frame.lineno}
                for frame in traceback.extract_tb(record.exc_info[2])
            ]
        return json.dumps(row, ensure_ascii=False)


class _SafeStreamHandler(logging.StreamHandler):
    def emit(self, record):
        # StreamHandler normally prints the entire raw record on write failure.
        try:
            self.stream.write(self.format(record) + self.terminator)
            self.flush()
        except Exception:  # noqa: BLE001, S110 - do not print raw records on stream failure
            pass


def configure_logging(*, stream: TextIO | None = None) -> logging.Handler:
    """Install one application handler, without replacing host/Uvicorn handlers."""
    with _lock:
        # Parent console formatters could expose the raw legacy exception again.
        _logger.propagate = False
        for handler in _logger.handlers:
            if isinstance(handler, _SafeStreamHandler):
                return handler
        handler = _SafeStreamHandler(stream if stream is not None else sys.stderr)
        handler.setFormatter(_SafeFormatter())
        _logger.addHandler(handler)
        _logger.setLevel(logging.INFO)
        return handler
