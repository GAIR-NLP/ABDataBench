"""Structured tracing for pipeline, agent, and tool execution."""

from __future__ import annotations

import json
import threading
import time
from itertools import count
from typing import Any, Optional


class TraceRecorder:
    """Thread-safe in-memory event recorder for async batch runs."""

    def __init__(self):
        self.started_at = time.time()
        self.started_perf = time.perf_counter()
        self._events: list[dict[str, Any]] = []
        self._counter = count(1)
        self._lock = threading.Lock()

    def start_span(self, span_type: str, name: str, **fields) -> int:
        span_id = next(self._counter)
        self._append(
            {
                "event": "span_start",
                "span_id": span_id,
                "span_type": span_type,
                "name": name,
                **fields,
            }
        )
        return span_id

    def end_span(self, span_id: Optional[int], status: str = "success", **fields):
        if span_id is None:
            return
        self._append(
            {
                "event": "span_end",
                "span_id": span_id,
                "status": status,
                **fields,
            }
        )

    def record_event(self, event: str, name: str, **fields):
        self._append(
            {
                "event": event,
                "name": name,
                **fields,
            }
        )

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            events = list(self._events)
        return {
            "started_at": self.started_at,
            "generated_at": time.time(),
            "events": events,
        }

    def write_json(self, path: str):
        payload = self.snapshot()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    def _append(self, event: dict[str, Any]):
        now = time.time()
        perf = time.perf_counter()
        record = {
            **event,
            "timestamp": now,
            "offset_ms": round((perf - self.started_perf) * 1000, 3),
        }
        with self._lock:
            self._events.append(record)
