"""Durable, explicit lifecycle control for resident KCH/Jarvis processes.

The ledger records governance and host observations separately:
authorization is not execution; a stop request is not proof that a process ended.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import sqlite3
from typing import Any
from uuid import uuid4

from .canonical import canonical_json
from .ledger import HashChainLedger, LedgerEvent


START_AUTHORIZED_EVENT = "resident.start.authorized.v0.1"
RUNNING_OBSERVED_EVENT = "resident.running.observed.v0.1"
STOP_REQUESTED_EVENT = "resident.stop.requested.v0.1"
STOPPED_OBSERVED_EVENT = "resident.stopped.observed.v0.1"
LIFECYCLE_EVENT_TYPES = frozenset(
    {
        START_AUTHORIZED_EVENT,
        RUNNING_OBSERVED_EVENT,
        STOP_REQUESTED_EVENT,
        STOPPED_OBSERVED_EVENT,
    }
)
LIFECYCLE_SCHEMA = "kch-psa.resident-lifecycle-event.v0.1.0"


class LifecycleError(RuntimeError):
    """Fail-closed lifecycle contract violation."""


class ResidentPhase(str, Enum):
    STOPPED = "STOPPED"
    START_AUTHORIZED = "START_AUTHORIZED"
    RUNNING = "RUNNING"


class DesiredState(str, Enum):
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"


@dataclass(frozen=True, slots=True)
class LifecycleSnapshot:
    resident_id: str
    phase: ResidentPhase
    desired_state: DesiredState
    authorization_event_id: str | None
    authorization_expires_at: str | None
    stop_request_event_id: str | None
    process_ref: str | None
    event_count: int
    ledger_head: str

    @property
    def pending_action(self) -> str:
        if self.phase is ResidentPhase.START_AUTHORIZED and self.desired_state is DesiredState.RUNNING:
            return "START"
        if self.phase is not ResidentPhase.STOPPED and self.desired_state is DesiredState.STOPPED:
            return "STOP"
        return "NONE"


def _time(value: str, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field}_INVALID")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field}_INVALID") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field}_MUST_BE_OFFSET_AWARE")
    return parsed


def _text(value: str, field: str, *, limit: int = 1000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{field}_INVALID")
    return value


class DurableResidentLifecycle:
    """Reconstructible resident lifecycle backed by a hash-chain ledger.

    A controller never starts or stops a process. Host adapters perform effects and
    then record exact observations through this contract.
    """

    def __init__(self, ledger: HashChainLedger, resident_id: str) -> None:
        self.ledger = ledger
        self.resident_id = _text(resident_id, "RESIDENT_ID", limit=200)

    def _resident_events(self) -> list[LedgerEvent]:
        events: list[LedgerEvent] = []
        for event in self.ledger.events():
            if event.event_type not in LIFECYCLE_EVENT_TYPES:
                continue
            payload = event.payload
            if not isinstance(payload, dict):
                raise LifecycleError(f"LIFECYCLE_PAYLOAD_NOT_OBJECT:{event.sequence}")
            if payload.get("resident_id") == self.resident_id:
                events.append(event)
        return events

    def _existing(self, event_id: str) -> LedgerEvent | None:
        for event in self.ledger.events():
            if event.event_id == event_id:
                return event
        return None

    @staticmethod
    def _assert_same(existing: LedgerEvent, event_type: str, payload: dict[str, Any]) -> None:
        if existing.event_type != event_type or canonical_json(existing.payload) != canonical_json(payload):
            raise LifecycleError("IDEMPOTENCY_CONFLICT")

    def _append_once(
        self, event_type: str, payload: dict[str, Any], event_id: str
    ) -> LedgerEvent:
        existing = self._existing(event_id)
        if existing is not None:
            self._assert_same(existing, event_type, payload)
            return existing
        try:
            return self.ledger.append(event_type, payload, event_id=event_id)
        except sqlite3.IntegrityError:
            existing = self._existing(event_id)
            if existing is None:
                raise
            self._assert_same(existing, event_type, payload)
            return existing

    def snapshot(self) -> LifecycleSnapshot:
        phase = ResidentPhase.STOPPED
        desired = DesiredState.STOPPED
        authorization_event_id: str | None = None
        authorization_expires_at: str | None = None
        stop_request_event_id: str | None = None
        process_ref: str | None = None
        events = self._resident_events()

        for event in events:
            payload = event.payload
            if payload.get("schema") != LIFECYCLE_SCHEMA:
                raise LifecycleError(f"LIFECYCLE_SCHEMA_MISMATCH:{event.sequence}")
            if payload.get("operation_id") != event.event_id:
                raise LifecycleError(f"LIFECYCLE_OPERATION_ID_MISMATCH:{event.sequence}")

            if event.event_type == START_AUTHORIZED_EVENT:
                if phase is not ResidentPhase.STOPPED or desired is not DesiredState.STOPPED:
                    raise LifecycleError(f"INVALID_START_AUTHORIZATION_TRANSITION:{event.sequence}")
                requested = _time(payload.get("requested_at"), "REQUESTED_AT")
                expires = _time(payload.get("expires_at"), "EXPIRES_AT")
                if expires <= requested:
                    raise LifecycleError(f"START_AUTHORIZATION_LEASE_INVALID:{event.sequence}")
                _text(payload.get("actor"), "ACTOR", limit=200)
                _text(payload.get("authority_ref"), "AUTHORITY_REF", limit=1000)
                _text(payload.get("reason"), "REASON", limit=2000)
                phase = ResidentPhase.START_AUTHORIZED
                desired = DesiredState.RUNNING
                authorization_event_id = event.event_id
                authorization_expires_at = payload["expires_at"]
                stop_request_event_id = None
                process_ref = None

            elif event.event_type == RUNNING_OBSERVED_EVENT:
                if phase is not ResidentPhase.START_AUTHORIZED or desired is not DesiredState.RUNNING:
                    raise LifecycleError(f"INVALID_RUNNING_TRANSITION:{event.sequence}")
                if payload.get("authorization_event_id") != authorization_event_id:
                    raise LifecycleError(f"AUTHORIZATION_REFERENCE_MISMATCH:{event.sequence}")
                observed = _time(payload.get("observed_at"), "OBSERVED_AT")
                if authorization_expires_at is None or observed >= _time(
                    authorization_expires_at, "AUTHORIZATION_EXPIRES_AT"
                ):
                    raise LifecycleError(f"START_AUTHORIZATION_EXPIRED:{event.sequence}")
                process_ref = _text(payload.get("process_ref"), "PROCESS_REF", limit=1000)
                phase = ResidentPhase.RUNNING

            elif event.event_type == STOP_REQUESTED_EVENT:
                if phase is ResidentPhase.STOPPED or desired is not DesiredState.RUNNING:
                    raise LifecycleError(f"INVALID_STOP_REQUEST_TRANSITION:{event.sequence}")
                _time(payload.get("requested_at"), "REQUESTED_AT")
                _text(payload.get("actor"), "ACTOR", limit=200)
                _text(payload.get("reason"), "REASON", limit=2000)
                desired = DesiredState.STOPPED
                stop_request_event_id = event.event_id

            elif event.event_type == STOPPED_OBSERVED_EVENT:
                if (
                    phase is ResidentPhase.STOPPED
                    or desired is not DesiredState.STOPPED
                    or payload.get("stop_request_event_id") != stop_request_event_id
                ):
                    raise LifecycleError(f"INVALID_STOPPED_TRANSITION:{event.sequence}")
                _time(payload.get("observed_at"), "OBSERVED_AT")
                _text(payload.get("observation_ref"), "OBSERVATION_REF", limit=1000)
                phase = ResidentPhase.STOPPED
                desired = DesiredState.STOPPED
                authorization_event_id = None
                authorization_expires_at = None
                stop_request_event_id = None
                process_ref = None

        return LifecycleSnapshot(
            resident_id=self.resident_id,
            phase=phase,
            desired_state=desired,
            authorization_event_id=authorization_event_id,
            authorization_expires_at=authorization_expires_at,
            stop_request_event_id=stop_request_event_id,
            process_ref=process_ref,
            event_count=len(events),
            ledger_head=self.ledger.head,
        )

    def authorize_start(
        self,
        *,
        actor: str,
        authority_ref: str,
        reason: str,
        requested_at: str,
        expires_at: str,
        operation_id: str | None = None,
    ) -> LifecycleSnapshot:
        operation_id = operation_id or str(uuid4())
        payload = {
            "schema": LIFECYCLE_SCHEMA,
            "operation_id": operation_id,
            "resident_id": self.resident_id,
            "actor": _text(actor, "ACTOR", limit=200),
            "authority_ref": _text(authority_ref, "AUTHORITY_REF", limit=1000),
            "reason": _text(reason, "REASON", limit=2000),
            "requested_at": requested_at,
            "expires_at": expires_at,
        }
        requested = _time(requested_at, "REQUESTED_AT")
        expires = _time(expires_at, "EXPIRES_AT")
        if expires <= requested:
            raise ValueError("START_AUTHORIZATION_LEASE_INVALID")
        existing = self._existing(operation_id)
        if existing is not None:
            self._assert_same(existing, START_AUTHORIZED_EVENT, payload)
            return self.snapshot()
        current = self.snapshot()
        if current.phase is not ResidentPhase.STOPPED:
            raise LifecycleError("RESIDENT_NOT_STOPPED")
        self._append_once(START_AUTHORIZED_EVENT, payload, operation_id)
        return self.snapshot()

    def observe_running(
        self,
        *,
        authorization_event_id: str,
        process_ref: str,
        observed_at: str,
        operation_id: str | None = None,
    ) -> LifecycleSnapshot:
        operation_id = operation_id or str(uuid4())
        payload = {
            "schema": LIFECYCLE_SCHEMA,
            "operation_id": operation_id,
            "resident_id": self.resident_id,
            "authorization_event_id": _text(
                authorization_event_id, "AUTHORIZATION_EVENT_ID", limit=200
            ),
            "process_ref": _text(process_ref, "PROCESS_REF", limit=1000),
            "observed_at": observed_at,
        }
        observed = _time(observed_at, "OBSERVED_AT")
        existing = self._existing(operation_id)
        if existing is not None:
            self._assert_same(existing, RUNNING_OBSERVED_EVENT, payload)
            return self.snapshot()
        current = self.snapshot()
        if current.phase is not ResidentPhase.START_AUTHORIZED:
            raise LifecycleError("START_NOT_AUTHORIZED")
        if current.desired_state is not DesiredState.RUNNING:
            raise LifecycleError("START_REVOKED")
        if authorization_event_id != current.authorization_event_id:
            raise LifecycleError("AUTHORIZATION_REFERENCE_MISMATCH")
        if current.authorization_expires_at is None or observed >= _time(
            current.authorization_expires_at, "AUTHORIZATION_EXPIRES_AT"
        ):
            raise LifecycleError("START_AUTHORIZATION_EXPIRED")
        self._append_once(RUNNING_OBSERVED_EVENT, payload, operation_id)
        return self.snapshot()

    def request_stop(
        self,
        *,
        actor: str,
        reason: str,
        requested_at: str,
        operation_id: str | None = None,
    ) -> LifecycleSnapshot:
        current = self.snapshot()
        if current.phase is ResidentPhase.STOPPED:
            return current
        operation_id = operation_id or str(uuid4())
        payload = {
            "schema": LIFECYCLE_SCHEMA,
            "operation_id": operation_id,
            "resident_id": self.resident_id,
            "actor": _text(actor, "ACTOR", limit=200),
            "reason": _text(reason, "REASON", limit=2000),
            "requested_at": requested_at,
        }
        _time(requested_at, "REQUESTED_AT")
        existing = self._existing(operation_id)
        if existing is not None:
            self._assert_same(existing, STOP_REQUESTED_EVENT, payload)
            return self.snapshot()
        if current.desired_state is DesiredState.STOPPED:
            raise LifecycleError("STOP_ALREADY_REQUESTED")
        self._append_once(STOP_REQUESTED_EVENT, payload, operation_id)
        return self.snapshot()

    def observe_stopped(
        self,
        *,
        stop_request_event_id: str,
        observation_ref: str,
        observed_at: str,
        operation_id: str | None = None,
    ) -> LifecycleSnapshot:
        operation_id = operation_id or str(uuid4())
        payload = {
            "schema": LIFECYCLE_SCHEMA,
            "operation_id": operation_id,
            "resident_id": self.resident_id,
            "stop_request_event_id": _text(
                stop_request_event_id, "STOP_REQUEST_EVENT_ID", limit=200
            ),
            "observation_ref": _text(observation_ref, "OBSERVATION_REF", limit=1000),
            "observed_at": observed_at,
        }
        _time(observed_at, "OBSERVED_AT")
        existing = self._existing(operation_id)
        if existing is not None:
            self._assert_same(existing, STOPPED_OBSERVED_EVENT, payload)
            return self.snapshot()
        current = self.snapshot()
        if current.phase is ResidentPhase.STOPPED:
            raise LifecycleError("RESIDENT_ALREADY_STOPPED")
        if current.desired_state is not DesiredState.STOPPED:
            raise LifecycleError("STOP_NOT_REQUESTED")
        if stop_request_event_id != current.stop_request_event_id:
            raise LifecycleError("STOP_REQUEST_REFERENCE_MISMATCH")
        self._append_once(STOPPED_OBSERVED_EVENT, payload, operation_id)
        return self.snapshot()
