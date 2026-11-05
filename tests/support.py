from __future__ import annotations

from dataclasses import replace
from typing import AsyncIterator, Mapping, Any
from uuid import uuid4

from kch_psa.canonical import digest, utc_now
from kch_psa.contracts import (
    AxisState,
    EngineProbe,
    EngineState,
    ExecutionReceipt,
    OperationStatus,
    SessionRef,
    SessionState,
    SideEffectState,
    empty_deployment_axes,
)
from kch_psa.engine import SessionCreateRequest


class RecordingConformanceEngine:
    """Test double only: exercises the protocol without model, tools or effects."""

    def __init__(self, fail_at: str | None = None) -> None:
        self.fail_at = fail_at
        self.calls: list[str] = []
        self.session: SessionRef | None = None

    def _receipt(self, operation: str, request: object) -> ExecutionReceipt:
        now = utc_now()
        return ExecutionReceipt(
            receipt_id=str(uuid4()),
            mission_id=self.session.mission_id if self.session else "mission-test",
            engine_id="recording-engine",
            operation=operation,
            status=OperationStatus.PASS,
            started_at=now,
            ended_at=now,
            request_sha256=digest(request),
            result_sha256=digest({"operation": operation, "state": "PASS"}),
            side_effect=SideEffectState.NONE,
            event_chain_head=None,
            evidence_boundaries=("TEST_DOUBLE_NO_MODEL_NO_TOOLS",),
        )

    async def probe(self) -> EngineProbe:
        self.calls.append("probe")
        if self.fail_at == "probe":
            raise RuntimeError("probe failure")
        axes = empty_deployment_axes()
        axes.update(
            specification=AxisState.PRESENT,
            code=AxisState.PRESENT,
            tests=AxisState.PRESENT,
        )
        return EngineProbe(
            engine_id="recording-engine",
            adapter_version="0.1.0-test",
            observed_at=utc_now(),
            state=EngineState.AVAILABLE,
            versions={"fixture": "1"},
            capabilities={"create_without_model": True, "cancel": True, "close": True},
            deployment_axes=axes,
            limits=("TEST_DOUBLE_ONLY",),
            evidence=("tests.support.RecordingConformanceEngine",),
        )

    async def create(self, request: SessionCreateRequest):
        self.calls.append("create")
        if self.fail_at == "create":
            raise RuntimeError("create failure")
        self.session = SessionRef(
            mission_id=request.mission_id,
            engine_id="recording-engine",
            engine_session_id="session-test",
            state=SessionState.CREATED,
            created_at=utc_now(),
        )
        return self.session, self._receipt("session.create", request)

    async def cancel(self, session: SessionRef, reason: str):
        self.calls.append("cancel")
        if self.fail_at == "cancel":
            raise RuntimeError("cancel failure")
        self.session = replace(session, state=SessionState.CANCELED)
        return self._receipt("session.cancel", {"session": session.engine_session_id, "reason": reason})

    async def close(self):
        self.calls.append("close")
        if self.fail_at == "close":
            raise RuntimeError("close failure")
        return self._receipt("engine.close", {})

    async def events(self, session: SessionRef) -> AsyncIterator[Mapping[str, Any]]:
        if False:
            yield {"session": session.engine_session_id}
