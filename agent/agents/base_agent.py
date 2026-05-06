"""Base agent classes."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from enum import Enum
import logging


class AgentStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRY = "retry"


@dataclass
class AgentResult:
    status: AgentStatus
    data: Any = None
    artifacts: Dict[str, str] = field(default_factory=dict)
    errors: list = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    retry_suggestion: Optional[str] = None


class BaseAgent(ABC):
    def __init__(self, name: str, config):
        self.name = name
        self.config = config
        self.status = AgentStatus.IDLE
        self.logger = logging.getLogger(f"agent.{name}")

    @abstractmethod
    async def execute(self, context: dict) -> AgentResult:
        pass

    def _get_tracer(self, context: Optional[dict] = None):
        tracer = getattr(self.config, "trace_recorder", None)
        if tracer or context is None:
            return tracer
        return context.get("trace_recorder")

    def _start_span(self, context: Optional[dict], span_type: str, name: str, **fields):
        tracer = self._get_tracer(context)
        if not tracer:
            return None
        base = {}
        if context:
            base["paper_id"] = context.get("paper_id")
            base["phase"] = context.get("current_phase")
        if span_type == "agent":
            base["agent"] = self.name
        return tracer.start_span(span_type, name, **{**base, **fields})

    def _end_span(self, context: Optional[dict], span_id: Optional[int], status: str = "success", **fields):
        tracer = self._get_tracer(context)
        if tracer:
            tracer.end_span(span_id, status=status, **fields)

    def _record_event(self, context: Optional[dict], event: str, name: str, **fields):
        tracer = self._get_tracer(context)
        if not tracer:
            return
        base = {}
        if context:
            base["paper_id"] = context.get("paper_id")
            base["phase"] = context.get("current_phase")
        tracer.record_event(event, name, agent=self.name, **base, **fields)
