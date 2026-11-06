from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import platform
import sys
import time
from uuid import uuid4

from kch_psa.canonical import canonical_json
from kch_psa.ledger import HashChainLedger
from kch_psa.lifecycle import DurableResidentLifecycle, ResidentPhase
from kch_psa.process_supervisor import ManagedProcess, ManagedProcessSupervisor


SCHEMA = "kch-psa.process-supervisor-witness.v0.1.0"


def now() -> datetime:
    return datetime.now(timezone.utc)


def stamp(value: datetime) -> str:
    return value.isoformat()


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def write_receipt(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(canonical_json(payload), encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    output = Path(arguments.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    receipt_path = output / "WITNESS_RECEIPT.json"
    ledger_path = output / "lifecycle.sqlite"
    started_at = now()
    ledger = HashChainLedger(ledger_path)
    lifecycle = DurableResidentLifecycle(ledger, "kch-psa-windows-witness")
    supervisor = ManagedProcessSupervisor(lifecycle, output / "runtime")
    managed: ManagedProcess | None = None
    try:
        authorization_id = "witness-start-authorization"
        lifecycle.authorize_start(
            actor="local-user:mission-authority",
            authority_ref="mission:implement-bounded-host-real-supervisor",
            reason="One bounded harmless process witness",
            requested_at=stamp(started_at),
            expires_at=stamp(started_at + timedelta(seconds=30)),
            operation_id=authorization_id,
        )
        managed = supervisor.start(
            authorization_event_id=authorization_id,
            executable=sys.executable,
            arguments=("-c", "import time; time.sleep(60)"),
            run_expires_at=stamp(now() + timedelta(seconds=2)),
            cwd=output,
        )
        while now() < datetime.fromisoformat(managed.record.run_expires_at):
            time.sleep(0.05)
        terminal = supervisor.enforce_run_lease(managed)
        if terminal.phase is not ResidentPhase.STOPPED:
            raise RuntimeError("WITNESS_NOT_TERMINAL_STOPPED")
        verification = ledger.verify()
        if not verification.valid:
            raise RuntimeError(f"LEDGER_INVALID:{verification.reason}")
        final_record = supervisor.load_record(managed.record.state_path)
        if final_record.state != "STOPPED" or managed.process.poll() is None:
            raise RuntimeError("PROCESS_TERMINALITY_NOT_CONFIRMED")
        ledger.close()
        payload: dict[str, object] = {
            "schema": SCHEMA,
            "witness_id": str(uuid4()),
            "status": "PASS",
            "started_at": stamp(started_at),
            "ended_at": stamp(now()),
            "platform": platform.platform(),
            "python": sys.version,
            "process_identity": asdict(managed.record.identity),
            "run_expires_at": managed.record.run_expires_at,
            "exit_code": managed.process.returncode,
            "lifecycle_phase": terminal.phase.value,
            "ledger_event_count": verification.event_count,
            "ledger_head": verification.head,
            "artifacts": {
                "ledger": {
                    "path": str(ledger_path),
                    "sha256": file_sha256(ledger_path),
                    "bytes": ledger_path.stat().st_size,
                },
                "process_record": {
                    "path": managed.record.state_path,
                    "sha256": file_sha256(Path(managed.record.state_path)),
                    "bytes": Path(managed.record.state_path).stat().st_size,
                },
                "stdout": {
                    "path": managed.record.stdout_path,
                    "sha256": file_sha256(Path(managed.record.stdout_path)),
                    "bytes": Path(managed.record.stdout_path).stat().st_size,
                },
                "stderr": {
                    "path": managed.record.stderr_path,
                    "sha256": file_sha256(Path(managed.record.stderr_path)),
                    "bytes": Path(managed.record.stderr_path).stat().st_size,
                },
            },
            "evidence_boundaries": [
                "one harmless local child process",
                "no network, tools, credentials, Telegram, PHL or persistent service",
                "does not establish continuous operation or production readiness",
            ],
        }
        write_receipt(receipt_path, payload)
        print(canonical_json(payload))
        return 0
    except Exception as error:
        if managed is not None and managed.process.poll() is None:
            managed.process.kill()
            managed.process.wait(timeout=10)
        ledger.close()
        payload = {
            "schema": SCHEMA,
            "witness_id": str(uuid4()),
            "status": "FAIL",
            "started_at": stamp(started_at),
            "ended_at": stamp(now()),
            "error_type": type(error).__name__,
            "error": str(error),
        }
        write_receipt(receipt_path, payload)
        print(canonical_json(payload))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
