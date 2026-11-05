from dataclasses import replace
from datetime import datetime, timezone
import unittest
from uuid import uuid4

from kch_psa.canonical import canonical_json, digest
from kch_psa.contracts import (
    ApprovalRequest,
    AxisState,
    EngineProbe,
    EngineState,
    ExecutionReceipt,
    OperationStatus,
    SideEffectState,
    empty_deployment_axes,
    now,
)


class ContractTests(unittest.TestCase):
    def test_canonical_json_is_order_independent(self):
        self.assertEqual(canonical_json({"b": 2, "a": 1}), canonical_json({"a": 1, "b": 2}))
        self.assertEqual(digest({"b": 2, "a": 1}), digest({"a": 1, "b": 2}))

    def test_canonical_json_rejects_non_string_mapping_keys(self):
        with self.assertRaisesRegex(TypeError, "MAPPING_KEYS_MUST_BE_STRINGS"):
            canonical_json({1: "numeric", "1": "text"})

    def test_probe_requires_all_deployment_axes(self):
        with self.assertRaisesRegex(ValueError, "DEPLOYMENT_AXES_MISMATCH"):
            EngineProbe(
                engine_id="engine",
                adapter_version="0.1.0",
                observed_at=now(),
                state=EngineState.AVAILABLE,
                versions={},
                capabilities={},
                deployment_axes={"code": AxisState.PRESENT},
            )

    def test_failed_receipt_requires_error(self):
        timestamp = now()
        with self.assertRaisesRegex(ValueError, "FAILED_RECEIPT_REQUIRES_ERROR"):
            ExecutionReceipt(
                receipt_id=str(uuid4()),
                mission_id="mission",
                engine_id="engine",
                operation="probe",
                status=OperationStatus.FAIL,
                started_at=timestamp,
                ended_at=timestamp,
                request_sha256=digest({}),
                result_sha256=None,
                side_effect=SideEffectState.NONE,
                event_chain_head=None,
            )

    def test_approval_is_finite_and_default_deny(self):
        request = ApprovalRequest(
            approval_id="approval-1",
            mission_id="mission",
            engine_session_id="session",
            tool_name="filesystem.write",
            effect_class="LOCAL_REVERSIBLE",
            resource="C:/tmp/target",
            requested_at="2026-11-05T10:00:00Z",
            expires_at="2026-11-05T10:05:00Z",
            input_sha256=digest({"path": "C:/tmp/target"}),
        )
        self.assertEqual(request.default_decision, "DENY")
        with self.assertRaisesRegex(ValueError, "APPROVAL_DEFAULT_MUST_DENY"):
            replace(request, default_decision="ALLOW")


if __name__ == "__main__":
    unittest.main()
