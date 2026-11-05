from __future__ import annotations

from tempfile import TemporaryDirectory
import unittest

from kch_psa.ledger import HashChainLedger
from kch_psa.lifecycle import (
    DesiredState,
    DurableResidentLifecycle,
    LifecycleError,
    ResidentPhase,
)


T0 = "2026-11-05T20:00:00+00:00"
T1 = "2026-11-05T20:01:00+00:00"
T2 = "2026-11-05T20:02:00+00:00"
T3 = "2026-11-05T20:03:00+00:00"
T4 = "2026-11-05T20:04:00+00:00"
T5 = "2026-11-05T20:05:00+00:00"


class ResidentLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.ledger = HashChainLedger(f"{self.tmp.name}/lifecycle.sqlite")
        self.lifecycle = DurableResidentLifecycle(self.ledger, "jarvis-desktop")

    def tearDown(self) -> None:
        self.ledger.close()
        self.tmp.cleanup()

    def authorize(self, *, operation_id: str = "auth-1", expires_at: str = T5):
        return self.lifecycle.authorize_start(
            actor="local-user",
            authority_ref="gesture:explicit-start",
            reason="User requested the resident to run",
            requested_at=T1,
            expires_at=expires_at,
            operation_id=operation_id,
        )

    def test_initial_state_is_stopped_without_invented_execution(self) -> None:
        snapshot = self.lifecycle.snapshot()
        self.assertEqual(snapshot.phase, ResidentPhase.STOPPED)
        self.assertEqual(snapshot.desired_state, DesiredState.STOPPED)
        self.assertEqual(snapshot.pending_action, "NONE")
        self.assertEqual(snapshot.event_count, 0)

    def test_full_lifecycle_separates_requests_from_observations(self) -> None:
        authorized = self.authorize()
        self.assertEqual(authorized.phase, ResidentPhase.START_AUTHORIZED)
        self.assertEqual(authorized.pending_action, "START")
        self.assertEqual(authorized.authorization_requested_at, T1)

        running = self.lifecycle.observe_running(
            authorization_event_id="auth-1",
            process_ref="pid:4242;image:jarvis.exe",
            observed_at=T2,
            operation_id="running-1",
        )
        self.assertEqual(running.phase, ResidentPhase.RUNNING)
        self.assertEqual(running.desired_state, DesiredState.RUNNING)
        self.assertEqual(running.pending_action, "NONE")

        stopping = self.lifecycle.request_stop(
            actor="local-user",
            reason="Explicit durable stop",
            requested_at=T3,
            operation_id="stop-1",
        )
        self.assertEqual(stopping.phase, ResidentPhase.RUNNING)
        self.assertEqual(stopping.desired_state, DesiredState.STOPPED)
        self.assertEqual(stopping.pending_action, "STOP")

        stopped = self.lifecycle.observe_stopped(
            stop_request_event_id="stop-1",
            observation_ref="process:4242:not-present",
            observed_at=T4,
            operation_id="stopped-1",
        )
        self.assertEqual(stopped.phase, ResidentPhase.STOPPED)
        self.assertEqual(stopped.desired_state, DesiredState.STOPPED)
        self.assertEqual(stopped.pending_action, "NONE")
        self.assertEqual(stopped.event_count, 4)
        self.assertTrue(self.ledger.verify().valid)

    def test_start_never_occurs_without_exact_active_authorization(self) -> None:
        with self.assertRaisesRegex(LifecycleError, "START_NOT_AUTHORIZED"):
            self.lifecycle.observe_running(
                authorization_event_id="missing",
                process_ref="pid:1",
                observed_at=T2,
                operation_id="running-unauthorized",
            )
        self.assertEqual(self.lifecycle.snapshot().event_count, 0)

        self.authorize()
        with self.assertRaisesRegex(LifecycleError, "AUTHORIZATION_REFERENCE_MISMATCH"):
            self.lifecycle.observe_running(
                authorization_event_id="auth-other",
                process_ref="pid:1",
                observed_at=T2,
                operation_id="running-wrong-auth",
            )
        self.assertEqual(self.lifecycle.snapshot().event_count, 1)

    def test_expired_or_time_regressing_start_is_rejected_before_append(self) -> None:
        self.authorize(expires_at=T2)
        with self.assertRaisesRegex(LifecycleError, "START_AUTHORIZATION_EXPIRED"):
            self.lifecycle.observe_running(
                authorization_event_id="auth-1",
                process_ref="pid:2",
                observed_at=T2,
                operation_id="running-expired",
            )
        self.assertEqual(self.lifecycle.snapshot().event_count, 1)

        with self.assertRaisesRegex(LifecycleError, "LIFECYCLE_TIME_REGRESSION"):
            self.lifecycle.observe_running(
                authorization_event_id="auth-1",
                process_ref="pid:2",
                observed_at=T0,
                operation_id="running-before-auth",
            )
        self.assertEqual(self.lifecycle.snapshot().event_count, 1)

    def test_stop_can_revoke_authorization_before_process_exists(self) -> None:
        self.authorize()
        requested = self.lifecycle.request_stop(
            actor="local-user",
            reason="Changed mind before launch",
            requested_at=T2,
            operation_id="stop-before-run",
        )
        self.assertEqual(requested.phase, ResidentPhase.START_AUTHORIZED)
        self.assertEqual(requested.pending_action, "STOP")

        stopped = self.lifecycle.observe_stopped(
            stop_request_event_id="stop-before-run",
            observation_ref="host:no-process-created",
            observed_at=T3,
            operation_id="stopped-before-run",
        )
        self.assertEqual(stopped.phase, ResidentPhase.STOPPED)
        self.assertIsNone(stopped.process_ref)

    def test_idempotency_replays_exact_command_and_rejects_conflict(self) -> None:
        first = self.authorize()
        second = self.authorize()
        self.assertEqual(first.event_count, 1)
        self.assertEqual(second.event_count, 1)

        with self.assertRaisesRegex(LifecycleError, "IDEMPOTENCY_CONFLICT"):
            self.lifecycle.authorize_start(
                actor="local-user",
                authority_ref="gesture:different",
                reason="Different payload under reused operation id",
                requested_at=T1,
                expires_at=T5,
                operation_id="auth-1",
            )
        self.assertEqual(self.lifecycle.snapshot().event_count, 1)

    def test_stop_reference_and_chronology_fail_closed(self) -> None:
        self.authorize()
        self.lifecycle.observe_running(
            authorization_event_id="auth-1",
            process_ref="pid:8",
            observed_at=T2,
            operation_id="running-1",
        )
        with self.assertRaisesRegex(LifecycleError, "LIFECYCLE_TIME_REGRESSION"):
            self.lifecycle.request_stop(
                actor="local-user",
                reason="Impossible historical stop",
                requested_at=T1,
                operation_id="stop-too-early",
            )
        self.assertEqual(self.lifecycle.snapshot().event_count, 2)

        self.lifecycle.request_stop(
            actor="local-user",
            reason="Valid stop",
            requested_at=T3,
            operation_id="stop-valid",
        )
        with self.assertRaisesRegex(LifecycleError, "STOP_REQUEST_REFERENCE_MISMATCH"):
            self.lifecycle.observe_stopped(
                stop_request_event_id="wrong-stop",
                observation_ref="pid:8:not-present",
                observed_at=T4,
                operation_id="stopped-wrong-ref",
            )
        self.assertEqual(self.lifecycle.snapshot().event_count, 3)

    def test_residents_are_confederated_not_state_fused(self) -> None:
        second = DurableResidentLifecycle(self.ledger, "jarvis-telegram")
        self.authorize()
        self.assertEqual(self.lifecycle.snapshot().phase, ResidentPhase.START_AUTHORIZED)
        self.assertEqual(second.snapshot().phase, ResidentPhase.STOPPED)
        self.assertEqual(second.snapshot().event_count, 0)

        second.authorize_start(
            actor="local-user",
            authority_ref="gesture:telegram-start",
            reason="Start only the Telegram resident",
            requested_at=T1,
            expires_at=T5,
            operation_id="telegram-auth",
        )
        self.assertEqual(self.lifecycle.snapshot().event_count, 1)
        self.assertEqual(second.snapshot().event_count, 1)


if __name__ == "__main__":
    unittest.main()
