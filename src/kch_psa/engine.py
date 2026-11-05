"""Engine adapter protocol. Hosts execute; KCH_PSA adjudicates and records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Mapping, Protocol, runtime_checkable

from .contracts import EngineProbe, ExecutionReceipt, SessionRef


@dataclass(frozen=True, slots=True)
class SessionCreateRequest:
    mission_id: str
    mode: str = "CONFORMANCE_NO_MODEL_NO_TOOLS"
    metadata: Mapping[str, Any] | None = None


@runtime_checkable
class EngineAdapter(Protocol):
    """Smallest common lifecycle; optional capabilities are declared by probe."""

    async def probe(self) -> EngineProbe: ...

    async def create(self, request: SessionCreateRequest) -> tuple[SessionRef, ExecutionReceipt]: ...

    async def cancel(self, session: SessionRef, reason: str) -> ExecutionReceipt: ...

    async def close(self) -> ExecutionReceipt: ...

    async def events(self, session: SessionRef) -> AsyncIterator[Mapping[str, Any]]: ...
