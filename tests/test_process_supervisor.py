from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time
import unittest

from kch_psa.ledger import HashChainLedger
from kch_psa.lifecycle import DurableResidentLifecycle, LifecycleError, ResidentPhase
from kch_psa.process_supervisor import (
    ManagedProcess,
    ManagedProcessSupervisor,
    ProcessIdentity,
    ProcessIdentityMismatch,
    ProcessInspector,
    ProcessNotFound,
)


def stamp(offset_seconds: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)).isoformat()


class ProcessSupervisorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.ledger = HashChainLedger(Path(self.tmp.name) / "ledger.sqlite")
        self.lifecycle = DurableResidentLifecycle(self.ledger, "test-resident")
        self.supervisor = ManagedProcessSupervisor(
            self.lifecycle, Path(self.tmp.name) / "runtime"
        )
        self.managed: list[ManagedProcess] = []

    def tearDown(self) -> None:
        for managed in self.managed:
            if managed.process.poll() is None:
                managed.process.kill()
                managed.process.wait(timeout=10)
        self.ledger.close()
        self.tmp.cleanup()

    def authorize(self) -> str:
        operation_id = "host-auth"
        self.lifecycle.authorize_start(
            actor="local-user",
            authority_ref="test:explicit-authorization",
            reason="Bounded host-real supervisor test",
            requested_at=stamp(-1),
            expires_at=stamp(120),
            operation_id=operation_id,
        )
        return operation_id

    def start_child(self) -> ManagedProcess:
        managed = self.supervisor.start(
            authorization_event_id=self.authorize(),
            executable=sys.executable,
            arguments=("-c", "import time; time.sleep(60)"),
            run_expires_at=stamp(300),
            cwd=self.tmp.name,
        )
        self.managed.append(managed)
        return managed

    def test_start_requires_exact_authorization_before_effect(self) -> None:
        with self.assertRaisesRegex(LifecycleError, "START_NOT_AUTHORIZED"):
            self.supervisor.start(
                authorization_event_id="missing",
                executable=sys.executable,
                arguments=("-c", "import time; time.sleep(60)"),
                run_expires_at=stamp(300),
            )
        self.assertEqual(self.lifecycle.snapshot().event_count, 0)

    def test_real_process_start_identity_logs_and_stop(self) -> None:
        managed = self.start_child()
        self.assertIsNone(managed.process.poll())
        self.assertTrue(Path(managed.record.stdout_path).is_file())
        self.assertTrue(Path(managed.record.stderr_path).is_file())
        loaded = self.supervisor.load_record(managed.record.state_path)
        self.assertEqual(loaded.identity, managed.record.identity)
        self.assertEqual(self.lifecycle.snapshot().phase, ResidentPhase.RUNNING)

        stopped = self.supervisor.stop(
            managed,
            actor="local-user",
            reason="End bounded test",
        )
        self.assertEqual(stopped.phase, ResidentPhase.STOPPED)
        self.assertIsNotNone(managed.process.poll())
        final_record = self.supervisor.load_record(managed.record.state_path)
        self.assertEqual(final_record.state, "STOPPED")
        self.assertTrue(self.ledger.verify().valid)

    def test_identity_mismatch_refuses_to_kill_then_exact_identity_finishes(self) -> None:
        managed = self.start_child()
        wrong_identity = replace(
            managed.record.identity,
            executable_sha256="0" * 64,
        )
        wrong_record = replace(managed.record, identity=wrong_identity)
        wrong = ManagedProcess(process=managed.process, record=wrong_record)
        with self.assertRaisesRegex(
            ProcessIdentityMismatch, "PROCESS_IDENTITY_MISMATCH_STOP_REFUSED"
        ):
            self.supervisor.stop(
                wrong,
                actor="local-user",
                reason="Attempt with stale identity",
            )
        self.assertIsNone(managed.process.poll())

        stopped = self.supervisor.stop(
            managed,
            actor="local-user",
            reason="Retry with exact identity",
        )
        self.assertEqual(stopped.phase, ResidentPhase.STOPPED)

    def test_reconcile_unexpected_exit_closes_durable_state(self) -> None:
        managed = self.start_child()
        managed.process.terminate()
        managed.process.wait(timeout=10)
        reconciled = self.supervisor.reconcile_missing_process(managed.record)
        self.assertEqual(reconciled.phase, ResidentPhase.STOPPED)
        loaded = self.supervisor.load_record(managed.record.state_path)
        self.assertEqual(loaded.state, "STOPPED")
        self.assertTrue(self.ledger.verify().valid)

    def test_finite_run_lease_stops_real_process(self) -> None:
        authorization = self.authorize()
        managed = self.supervisor.start(
            authorization_event_id=authorization,
            executable=sys.executable,
            arguments=("-c", "import time; time.sleep(60)"),
            run_expires_at=stamp(1),
            cwd=self.tmp.name,
        )
        self.managed.append(managed)
        before = self.supervisor.enforce_run_lease(managed)
        self.assertEqual(before.phase, ResidentPhase.RUNNING)
        self.assertIsNone(managed.process.poll())
        time.sleep(1.1)
        after = self.supervisor.enforce_run_lease(managed)
        self.assertEqual(after.phase, ResidentPhase.STOPPED)
        self.assertIsNotNone(managed.process.poll())

    def test_failed_identity_gate_revokes_authorization_and_closes_process(self) -> None:
        class MismatchingInspector(ProcessInspector):
            captured: ProcessIdentity | None = None

            def capture(self, pid: int) -> ProcessIdentity:
                exact = super().capture(pid)
                self.captured = exact
                return replace(exact, executable_sha256="0" * 64)

        inspector = MismatchingInspector()
        supervisor = ManagedProcessSupervisor(
            self.lifecycle,
            Path(self.tmp.name) / "failed-start-runtime",
            inspector=inspector,
        )
        with self.assertRaisesRegex(
            ProcessIdentityMismatch, "STARTED_EXECUTABLE_HASH_MISMATCH"
        ):
            supervisor.start(
                authorization_event_id=self.authorize(),
                executable=sys.executable,
                arguments=("-c", "import time; time.sleep(60)"),
                run_expires_at=stamp(300),
                cwd=self.tmp.name,
            )

        self.assertIsNotNone(inspector.captured)
        self.assertEqual(self.lifecycle.snapshot().phase, ResidentPhase.STOPPED)
        with self.assertRaises(ProcessNotFound):
            ProcessInspector().capture(inspector.captured.pid)  # type: ignore[union-attr]
        self.assertTrue(self.ledger.verify().valid)


if __name__ == "__main__":
    unittest.main()
