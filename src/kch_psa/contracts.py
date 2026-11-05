"""Versioned, vendor-neutral contracts for engines, authority and receipts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import re
from typing import Any, Mapping
from uuid import UUID

from .canonical import canonical_json, digest, utc_now


_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")

DEPLOYMENT_AXES = (
    "specification",
    "code",
    "tests",
    "package",
    "install",
    "host_activation",
    "continuous_operation",
    "causal_validation",
    "external_authority",
)


class AxisState(str, Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    NOT_ESTIMABLE = "NOT_ESTIMABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EngineState(str, Enum):
    AVAILABLE = "AVAILABLE"
    CONNECTED = "CONNECTED"
    UNAVAILABLE = "UNAVAILABLE"
    BROKEN = "BROKEN"


class SessionState(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    CANCELED = "CANCELED"
    CLOSED = "CLOSED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class OperationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ABSTAIN = "ABSTAIN"
    NOT_ESTIMABLE = "NOT_ESTIMABLE"


class SideEffectState(str, Enum):
    NONE = "NONE"
    CONFIRMED = "CONFIRMED"
    UNCERTAIN = "UNCERTAIN"


def _identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{name}_INVALID")
    return value


def _sha256(value: str, name: str) -> str:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise ValueError(f"{name}_INVALID")
    return value


def _timestamp(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name}_INVALID")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{name}_INVALID") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name}_MUST_BE_OFFSET_AWARE")
    return value


def _axis_map(value: Mapping[str, AxisState | str]) -> dict[str, AxisState]:
    if set(value) != set(DEPLOYMENT_AXES):
        missing = sorted(set(DEPLOYMENT_AXES) - set(value))
        extra = sorted(set(value) - set(DEPLOYMENT_AXES))
        raise ValueError(f"DEPLOYMENT_AXES_MISMATCH:missing={missing}:extra={extra}")
    return {axis: state if isinstance(state, AxisState) else AxisState(state) for axis, state in value.items()}


@dataclass(frozen=True, slots=True)
class EngineProbe:
    engine_id: str
    adapter_version: str
    observed_at: str
    state: EngineState
    versions: Mapping[str, str]
    capabilities: Mapping[str, bool]
    deployment_axes: Mapping[str, AxisState | str]
    limits: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    schema: str = "kch-psa.engine-probe.v0.1.0"

    def __post_init__(self) -> None:
        _identifier(self.engine_id, "ENGINE_ID")
        _identifier(self.adapter_version, "ADAPTER_VERSION")
        _timestamp(self.observed_at, "OBSERVED_AT")
        object.__setattr__(self, "state", EngineState(self.state))
        object.__setattr__(self, "deployment_axes", _axis_map(self.deployment_axes))
        if not all(isinstance(key, str) and isinstance(value, str) for key, value in self.versions.items()):
            raise ValueError("VERSIONS_INVALID")
        if not all(isinstance(key, str) and isinstance(value, bool) for key, value in self.capabilities.items()):
            raise ValueError("CAPABILITIES_INVALID")
        if not all(isinstance(item, str) and item for item in (*self.limits, *self.evidence)):
            raise ValueError("PROBE_TEXT_ITEMS_INVALID")

    @property
    def sha256(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class SessionRef:
    mission_id: str
    engine_id: str
    engine_session_id: str
    state: SessionState
    created_at: str
    parent_session_id: str | None = None
    schema: str = "kch-psa.engine-session.v0.1.0"

    def __post_init__(self) -> None:
        _identifier(self.mission_id, "MISSION_ID")
        _identifier(self.engine_id, "ENGINE_ID")
        _identifier(self.engine_session_id, "ENGINE_SESSION_ID")
        if self.parent_session_id is not None:
            _identifier(self.parent_session_id, "PARENT_SESSION_ID")
        _timestamp(self.created_at, "CREATED_AT")
        object.__setattr__(self, "state", SessionState(self.state))


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    approval_id: str
    mission_id: str
    engine_session_id: str
    tool_name: str
    effect_class: str
    resource: str
    requested_at: str
    expires_at: str
    input_sha256: str
    default_decision: str = "DENY"
    schema: str = "kch-psa.approval-request.v0.1.0"

    def __post_init__(self) -> None:
        _identifier(self.approval_id, "APPROVAL_ID")
        _identifier(self.mission_id, "MISSION_ID")
        _identifier(self.engine_session_id, "ENGINE_SESSION_ID")
        _identifier(self.tool_name, "TOOL_NAME")
        _identifier(self.effect_class, "EFFECT_CLASS")
        if not isinstance(self.resource, str) or not self.resource:
            raise ValueError("RESOURCE_REQUIRED")
        _timestamp(self.requested_at, "REQUESTED_AT")
        _timestamp(self.expires_at, "EXPIRES_AT")
        if datetime.fromisoformat(self.expires_at.replace("Z", "+00:00")) <= datetime.fromisoformat(self.requested_at.replace("Z", "+00:00")):
            raise ValueError("APPROVAL_EXPIRY_NOT_AFTER_REQUEST")
        _sha256(self.input_sha256, "INPUT_SHA256")
        if self.default_decision != "DENY":
            raise ValueError("APPROVAL_DEFAULT_MUST_DENY")


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    approval_id: str
    decided_at: str
    accepted: bool
    actor: str
    reason: str
    request_sha256: str
    schema: str = "kch-psa.approval-decision.v0.1.0"

    def __post_init__(self) -> None:
        _identifier(self.approval_id, "APPROVAL_ID")
        _timestamp(self.decided_at, "DECIDED_AT")
        if not isinstance(self.accepted, bool):
            raise ValueError("APPROVAL_ACCEPTED_MUST_BE_BOOLEAN")
        _identifier(self.actor, "ACTOR")
        if not self.reason:
            raise ValueError("APPROVAL_REASON_REQUIRED")
        _sha256(self.request_sha256, "REQUEST_SHA256")


@dataclass(frozen=True, slots=True)
class ExecutionReceipt:
    receipt_id: str
    mission_id: str
    engine_id: str
    operation: str
    status: OperationStatus
    started_at: str
    ended_at: str
    request_sha256: str
    result_sha256: str | None
    side_effect: SideEffectState
    event_chain_head: str | None
    evidence_boundaries: tuple[str, ...] = ()
    error: str | None = None
    schema: str = "kch-psa.execution-receipt.v0.1.0"

    def __post_init__(self) -> None:
        try:
            UUID(self.receipt_id)
        except (ValueError, AttributeError) as error:
            raise ValueError("RECEIPT_ID_NOT_UUID") from error
        _identifier(self.mission_id, "MISSION_ID")
        _identifier(self.engine_id, "ENGINE_ID")
        _identifier(self.operation, "OPERATION")
        _timestamp(self.started_at, "STARTED_AT")
        _timestamp(self.ended_at, "ENDED_AT")
        if datetime.fromisoformat(self.ended_at.replace("Z", "+00:00")) < datetime.fromisoformat(self.started_at.replace("Z", "+00:00")):
            raise ValueError("RECEIPT_END_BEFORE_START")
        _sha256(self.request_sha256, "REQUEST_SHA256")
        if self.result_sha256 is not None:
            _sha256(self.result_sha256, "RESULT_SHA256")
        if self.event_chain_head is not None:
            _sha256(self.event_chain_head, "EVENT_CHAIN_HEAD")
        object.__setattr__(self, "status", OperationStatus(self.status))
        object.__setattr__(self, "side_effect", SideEffectState(self.side_effect))
        if self.status is OperationStatus.FAIL and not self.error:
            raise ValueError("FAILED_RECEIPT_REQUIRES_ERROR")
        if self.status is OperationStatus.PASS and self.error:
            raise ValueError("PASS_RECEIPT_CANNOT_HAVE_ERROR")

    @property
    def sha256(self) -> str:
        return digest(self)

    def to_json(self) -> str:
        return canonical_json(self)


def empty_deployment_axes(default: AxisState = AxisState.NOT_ESTIMABLE) -> dict[str, AxisState]:
    return {axis: default for axis in DEPLOYMENT_AXES}


def now() -> str:
    return utc_now()
