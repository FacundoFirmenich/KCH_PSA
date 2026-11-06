"""Host-real supervision with exact process identity and durable lifecycle receipts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime
import ctypes
from ctypes import wintypes
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Sequence
from uuid import uuid4

from .canonical import canonical_json, utc_now
from .lifecycle import (
    DesiredState,
    DurableResidentLifecycle,
    LifecycleError,
    LifecycleSnapshot,
    ResidentPhase,
)


PROCESS_RECORD_SCHEMA = "kch-psa.managed-process-record.v0.1.0"
PROCESS_FAILURE_EVENT = "resident.process.failure.v0.1"
PROCESS_IDENTITY_MISMATCH_EVENT = "resident.process.identity-mismatch.v0.1"


class ProcessSupervisorError(RuntimeError):
    """Base error for fail-closed host supervision."""


class ProcessNotFound(ProcessSupervisorError):
    pass


class ProcessIdentityMismatch(ProcessSupervisorError):
    pass


def _parse_time(value: str, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field}_INVALID")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field}_INVALID") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field}_MUST_BE_OFFSET_AWARE")
    return parsed


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class ProcessIdentity:
    pid: int
    executable_path: str
    executable_sha256: str
    start_token: str
    schema: str = "kch-psa.process-identity.v0.1.0"

    def __post_init__(self) -> None:
        if not isinstance(self.pid, int) or self.pid <= 0:
            raise ValueError("PID_INVALID")
        path = Path(self.executable_path)
        if not path.is_absolute():
            raise ValueError("EXECUTABLE_PATH_NOT_ABSOLUTE")
        if len(self.executable_sha256) != 64 or any(
            character not in "0123456789abcdef"
            for character in self.executable_sha256
        ):
            raise ValueError("EXECUTABLE_SHA256_INVALID")
        if not self.start_token:
            raise ValueError("START_TOKEN_REQUIRED")

    def matches(self, other: "ProcessIdentity") -> bool:
        return self == other

    def to_ref(self) -> str:
        return canonical_json(self)

    @classmethod
    def from_ref(cls, value: str) -> "ProcessIdentity":
        try:
            payload = json.loads(value)
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError("PROCESS_REF_INVALID_JSON") from error
        if not isinstance(payload, dict) or payload.get("schema") != cls.__dataclass_fields__["schema"].default:
            raise ValueError("PROCESS_REF_SCHEMA_MISMATCH")
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class ManagedProcessRecord:
    resident_id: str
    start_operation_id: str
    authorization_event_id: str
    identity: ProcessIdentity
    argv_sha256: str
    started_at: str
    run_expires_at: str
    stdout_path: str
    stderr_path: str
    state_path: str
    state: str = "RUNNING"
    stop_request_event_id: str | None = None
    stopped_at: str | None = None
    exit_code: int | None = None
    schema: str = PROCESS_RECORD_SCHEMA

    def __post_init__(self) -> None:
        _parse_time(self.started_at, "STARTED_AT")
        if _parse_time(self.run_expires_at, "RUN_EXPIRES_AT") <= _parse_time(
            self.started_at, "STARTED_AT"
        ):
            raise ValueError("RUN_LEASE_INVALID")
        if self.state not in {"RUNNING", "STOPPED"}:
            raise ValueError("PROCESS_RECORD_STATE_INVALID")
        if len(self.argv_sha256) != 64:
            raise ValueError("ARGV_SHA256_INVALID")
        for field, value in (
            ("STDOUT_PATH", self.stdout_path),
            ("STDERR_PATH", self.stderr_path),
            ("STATE_PATH", self.state_path),
        ):
            if not Path(value).is_absolute():
                raise ValueError(f"{field}_NOT_ABSOLUTE")
        if self.state == "RUNNING" and any(
            value is not None
            for value in (self.stop_request_event_id, self.stopped_at, self.exit_code)
        ):
            raise ValueError("RUNNING_RECORD_HAS_TERMINAL_FIELDS")
        if self.state == "STOPPED" and (
            self.stop_request_event_id is None or self.stopped_at is None
        ):
            raise ValueError("STOPPED_RECORD_MISSING_TERMINAL_FIELDS")

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["identity"] = asdict(self.identity)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "ManagedProcessRecord":
        data = dict(payload)
        if data.get("schema") != PROCESS_RECORD_SCHEMA:
            raise ValueError("PROCESS_RECORD_SCHEMA_MISMATCH")
        identity = data.get("identity")
        if not isinstance(identity, dict):
            raise ValueError("PROCESS_RECORD_IDENTITY_INVALID")
        data["identity"] = ProcessIdentity(**identity)
        return cls(**data)


@dataclass(frozen=True, slots=True)
class ManagedProcess:
    process: subprocess.Popen[bytes]
    record: ManagedProcessRecord


class ProcessInspector:
    """Capture process identity without third-party dependencies."""

    def capture(self, pid: int) -> ProcessIdentity:
        if os.name == "nt":
            return self._capture_windows(pid)
        return self._capture_procfs(pid)

    @staticmethod
    def _capture_procfs(pid: int) -> ProcessIdentity:
        root = Path("/proc") / str(pid)
        try:
            executable = Path(os.readlink(root / "exe")).resolve()
            stat = (root / "stat").read_text(encoding="utf-8")
        except (FileNotFoundError, ProcessLookupError) as error:
            raise ProcessNotFound(f"PROCESS_NOT_FOUND:{pid}") from error
        closing = stat.rfind(")")
        fields = stat[closing + 2 :].split()
        if closing < 0 or len(fields) <= 19:
            raise ProcessSupervisorError(f"PROC_STAT_INVALID:{pid}")
        return ProcessIdentity(
            pid=pid,
            executable_path=str(executable),
            executable_sha256=_hash_file(executable),
            start_token=f"procfs:{fields[19]}",
        )

    @staticmethod
    def _capture_windows(pid: int) -> ProcessIdentity:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        open_process = kernel32.OpenProcess
        open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        open_process.restype = wintypes.HANDLE
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL
        query_path = kernel32.QueryFullProcessImageNameW
        query_path.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        query_path.restype = wintypes.BOOL
        get_times = kernel32.GetProcessTimes
        get_times.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
        ]
        get_times.restype = wintypes.BOOL
        get_exit = kernel32.GetExitCodeProcess
        get_exit.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        get_exit.restype = wintypes.BOOL

        handle = open_process(0x1000, False, pid)
        if not handle:
            error = ctypes.get_last_error()
            if error in {87, 1168}:
                raise ProcessNotFound(f"PROCESS_NOT_FOUND:{pid}")
            raise ProcessSupervisorError(f"OPEN_PROCESS_FAILED:{pid}:{error}")
        try:
            exit_code = wintypes.DWORD()
            if not get_exit(handle, ctypes.byref(exit_code)):
                raise ProcessSupervisorError(
                    f"GET_EXIT_CODE_FAILED:{pid}:{ctypes.get_last_error()}"
                )
            if exit_code.value != 259:
                raise ProcessNotFound(f"PROCESS_NOT_RUNNING:{pid}:{exit_code.value}")
            capacity = wintypes.DWORD(32768)
            buffer = ctypes.create_unicode_buffer(capacity.value)
            if not query_path(handle, 0, buffer, ctypes.byref(capacity)):
                raise ProcessSupervisorError(
                    f"QUERY_PROCESS_PATH_FAILED:{pid}:{ctypes.get_last_error()}"
                )
            creation = wintypes.FILETIME()
            exit_time = wintypes.FILETIME()
            kernel = wintypes.FILETIME()
            user = wintypes.FILETIME()
            if not get_times(
                handle,
                ctypes.byref(creation),
                ctypes.byref(exit_time),
                ctypes.byref(kernel),
                ctypes.byref(user),
            ):
                raise ProcessSupervisorError(
                    f"GET_PROCESS_TIMES_FAILED:{pid}:{ctypes.get_last_error()}"
                )
            token = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
            executable = Path(buffer.value).resolve()
            return ProcessIdentity(
                pid=pid,
                executable_path=str(executable),
                executable_sha256=_hash_file(executable),
                start_token=f"filetime:{token}",
            )
        finally:
            close_handle(handle)


class ManagedProcessSupervisor:
    """Start and stop only processes bound to an exact durable identity."""

    def __init__(
        self,
        lifecycle: DurableResidentLifecycle,
        runtime_root: str | Path,
        *,
        inspector: ProcessInspector | None = None,
    ) -> None:
        self.lifecycle = lifecycle
        self.runtime_root = Path(runtime_root).resolve()
        self.inspector = inspector or ProcessInspector()

    @staticmethod
    def _write_record(record: ManagedProcessRecord) -> None:
        path = Path(record.state_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(canonical_json(record.to_dict()), encoding="utf-8")
        os.replace(temporary, path)

    @staticmethod
    def load_record(path: str | Path) -> ManagedProcessRecord:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("PROCESS_RECORD_NOT_OBJECT")
        return ManagedProcessRecord.from_dict(payload)

    def _record_failure(self, stage: str, error: BaseException) -> None:
        self.lifecycle.ledger.append(
            PROCESS_FAILURE_EVENT,
            {
                "resident_id": self.lifecycle.resident_id,
                "stage": stage,
                "error_type": type(error).__name__,
                "error": str(error),
                "observed_at": utc_now(),
            },
        )

    def _close_failed_start(
        self,
        *,
        operation_id: str,
        pid: int | None,
        process_absent: bool,
    ) -> None:
        snapshot = self.lifecycle.snapshot()
        if snapshot.phase is ResidentPhase.STOPPED:
            return
        if snapshot.desired_state is DesiredState.RUNNING:
            snapshot = self.lifecycle.request_stop(
                actor="kch-psa:runtime-supervisor",
                reason="Process start failed; authorization revoked",
                requested_at=utc_now(),
                operation_id=f"failed-start-stop-{operation_id}",
            )
        if not process_absent:
            return
        if snapshot.stop_request_event_id is None:
            raise ProcessSupervisorError("FAILED_START_STOP_REQUEST_MISSING")
        self.lifecycle.observe_stopped(
            stop_request_event_id=snapshot.stop_request_event_id,
            observation_ref=(
                "process:not-started"
                if pid is None
                else f"process:{pid}:terminated-after-start-failure"
            ),
            observed_at=utc_now(),
            operation_id=f"failed-start-stopped-{operation_id}",
        )

    def start(
        self,
        *,
        authorization_event_id: str,
        executable: str | Path,
        arguments: Sequence[str] = (),
        run_expires_at: str,
        cwd: str | Path | None = None,
    ) -> ManagedProcess:
        snapshot = self.lifecycle.snapshot()
        if snapshot.phase is not ResidentPhase.START_AUTHORIZED:
            raise LifecycleError("START_NOT_AUTHORIZED")
        if snapshot.desired_state is not DesiredState.RUNNING:
            raise LifecycleError("START_REVOKED")
        if snapshot.authorization_event_id != authorization_event_id:
            raise LifecycleError("AUTHORIZATION_REFERENCE_MISMATCH")
        observed_at = utc_now()
        if snapshot.authorization_expires_at is None or _parse_time(
            observed_at, "OBSERVED_AT"
        ) >= _parse_time(snapshot.authorization_expires_at, "AUTHORIZATION_EXPIRES_AT"):
            raise LifecycleError("START_AUTHORIZATION_EXPIRED")
        if _parse_time(run_expires_at, "RUN_EXPIRES_AT") <= _parse_time(
            observed_at, "OBSERVED_AT"
        ):
            raise ValueError("RUN_LEASE_NOT_FUTURE")

        executable_path = Path(executable).resolve()
        if not executable_path.is_absolute() or not executable_path.is_file():
            raise ValueError("EXECUTABLE_NOT_REGULAR_FILE")
        if any(not isinstance(argument, str) or "\x00" in argument for argument in arguments):
            raise ValueError("ARGUMENT_INVALID")
        cwd_path = Path(cwd).resolve() if cwd is not None else executable_path.parent
        if not cwd_path.is_dir():
            raise ValueError("CWD_NOT_DIRECTORY")

        operation_id = str(uuid4())
        resident_key = sha256(self.lifecycle.resident_id.encode("utf-8")).hexdigest()[:16]
        run_dir = self.runtime_root / resident_key / operation_id
        run_dir.mkdir(parents=True, exist_ok=False)
        stdout_path = run_dir / "stdout.log"
        stderr_path = run_dir / "stderr.log"
        state_path = run_dir / "process.json"
        command = [str(executable_path), *arguments]
        argv_sha256 = sha256(canonical_json(command).encode("utf-8")).hexdigest()
        process: subprocess.Popen[bytes] | None = None
        try:
            with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
                process = subprocess.Popen(
                    command,
                    cwd=cwd_path,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout,
                    stderr=stderr,
                    shell=False,
                    creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
                )
            identity = self.inspector.capture(process.pid)
            expected_sha256 = _hash_file(executable_path)
            if identity.executable_sha256 != expected_sha256:
                raise ProcessIdentityMismatch("STARTED_EXECUTABLE_HASH_MISMATCH")
            running = self.lifecycle.observe_running(
                authorization_event_id=authorization_event_id,
                process_ref=identity.to_ref(),
                observed_at=utc_now(),
                operation_id=f"running-{operation_id}",
            )
            record = ManagedProcessRecord(
                resident_id=self.lifecycle.resident_id,
                start_operation_id=operation_id,
                authorization_event_id=authorization_event_id,
                identity=identity,
                argv_sha256=argv_sha256,
                started_at=running.last_transition_at or observed_at,
                run_expires_at=run_expires_at,
                stdout_path=str(stdout_path),
                stderr_path=str(stderr_path),
                state_path=str(state_path),
            )
            self._write_record(record)
            return ManagedProcess(process=process, record=record)
        except Exception as error:
            process_absent = process is None
            if process is not None and process.poll() is None:
                try:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
                except Exception as cleanup_error:
                    try:
                        self._record_failure("start_process_cleanup", cleanup_error)
                    except Exception:
                        pass
                process_absent = process.poll() is not None
            try:
                self._record_failure("start", error)
            except Exception:
                pass
            try:
                self._close_failed_start(
                    operation_id=operation_id,
                    pid=None if process is None else process.pid,
                    process_absent=process_absent,
                )
            except Exception as lifecycle_cleanup_error:
                try:
                    self._record_failure(
                        "start_lifecycle_cleanup", lifecycle_cleanup_error
                    )
                except Exception:
                    pass
            raise

    def stop(
        self,
        managed: ManagedProcess,
        *,
        actor: str,
        reason: str,
        timeout_seconds: float = 10.0,
    ) -> LifecycleSnapshot:
        snapshot = self.lifecycle.snapshot()
        now = utc_now()
        if snapshot.phase is ResidentPhase.STOPPED:
            return snapshot
        if snapshot.desired_state is DesiredState.RUNNING:
            snapshot = self.lifecycle.request_stop(
                actor=actor,
                reason=reason,
                requested_at=now,
                operation_id=f"stop-{managed.record.start_operation_id}",
            )
        stop_request_id = snapshot.stop_request_event_id
        if stop_request_id is None:
            raise ProcessSupervisorError("STOP_REQUEST_MISSING")

        try:
            current = self.inspector.capture(managed.record.identity.pid)
        except ProcessNotFound:
            current = None
        if current is not None and not current.matches(managed.record.identity):
            self.lifecycle.ledger.append(
                PROCESS_IDENTITY_MISMATCH_EVENT,
                {
                    "resident_id": self.lifecycle.resident_id,
                    "expected": asdict(managed.record.identity),
                    "observed": asdict(current),
                    "observed_at": utc_now(),
                },
            )
            raise ProcessIdentityMismatch("PROCESS_IDENTITY_MISMATCH_STOP_REFUSED")

        if current is not None and managed.process.poll() is None:
            managed.process.terminate()
            try:
                managed.process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired as error:
                self._record_failure("stop_timeout", error)
                managed.process.kill()
                try:
                    managed.process.wait(timeout=timeout_seconds)
                except subprocess.TimeoutExpired as kill_error:
                    self._record_failure("kill_timeout", kill_error)
                    raise ProcessSupervisorError("PROCESS_KILL_TIMEOUT") from kill_error

        try:
            after = self.inspector.capture(managed.record.identity.pid)
        except ProcessNotFound:
            after = None
        if after is not None and after.matches(managed.record.identity):
            error = ProcessSupervisorError("PROCESS_STILL_RUNNING_AFTER_STOP")
            self._record_failure("stop_verify", error)
            raise error

        stopped_at = utc_now()
        terminal = self.lifecycle.observe_stopped(
            stop_request_event_id=stop_request_id,
            observation_ref=(
                f"process:{managed.record.identity.pid}:not-present"
                if after is None
                else f"process:{managed.record.identity.pid}:pid-reused"
            ),
            observed_at=stopped_at,
            operation_id=f"stopped-{managed.record.start_operation_id}",
        )
        finished = replace(
            managed.record,
            state="STOPPED",
            stop_request_event_id=stop_request_id,
            stopped_at=stopped_at,
            exit_code=managed.process.poll(),
        )
        self._write_record(finished)
        return terminal
    def enforce_run_lease(
        self,
        managed: ManagedProcess,
        *,
        observed_at: str | None = None,
        actor: str = "kch-psa:lease-supervisor",
    ) -> LifecycleSnapshot:
        effective_time = observed_at or utc_now()
        if _parse_time(effective_time, "OBSERVED_AT") < _parse_time(
            managed.record.run_expires_at, "RUN_EXPIRES_AT"
        ):
            return self.lifecycle.snapshot()
        return self.stop(
            managed,
            actor=actor,
            reason="Finite process run lease expired",
        )

    def reconcile_missing_process(
        self,
        record: ManagedProcessRecord,
        *,
        actor: str = "kch-psa:runtime-supervisor",
    ) -> LifecycleSnapshot:
        snapshot = self.lifecycle.snapshot()
        try:
            current = self.inspector.capture(record.identity.pid)
        except ProcessNotFound:
            current = None
        if current is not None:
            if not current.matches(record.identity):
                raise ProcessIdentityMismatch("PROCESS_IDENTITY_MISMATCH_RECONCILE")
            return snapshot
        if snapshot.phase is ResidentPhase.STOPPED:
            return snapshot
        if snapshot.desired_state is DesiredState.RUNNING:
            snapshot = self.lifecycle.request_stop(
                actor=actor,
                reason="Previously observed process is no longer present",
                requested_at=utc_now(),
                operation_id=f"reconcile-stop-{record.start_operation_id}",
            )
        if snapshot.stop_request_event_id is None:
            raise ProcessSupervisorError("RECONCILE_STOP_REQUEST_MISSING")
        stopped_at = utc_now()
        terminal = self.lifecycle.observe_stopped(
            stop_request_event_id=snapshot.stop_request_event_id,
            observation_ref=f"process:{record.identity.pid}:not-present-on-reconcile",
            observed_at=stopped_at,
            operation_id=f"reconcile-stopped-{record.start_operation_id}",
        )
        finished = replace(
            record,
            state="STOPPED",
            stop_request_event_id=snapshot.stop_request_event_id,
            stopped_at=stopped_at,
        )
        self._write_record(finished)
        return terminal
