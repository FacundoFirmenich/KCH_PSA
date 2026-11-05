import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from dataclasses import replace

from kch_psa.conformance import run_lifecycle
from kch_psa.ledger import HashChainLedger
from tests.support import RecordingConformanceEngine


class ConformanceTests(unittest.TestCase):
    def test_complete_no_effect_lifecycle_passes(self):
        with TemporaryDirectory() as folder:
            engine = RecordingConformanceEngine()
            with HashChainLedger(Path(folder, "ledger.sqlite3")) as ledger:
                result = asyncio.run(run_lifecycle(engine, mission_id="mission-test", ledger=ledger))
            self.assertEqual(result.status, "PASS")
            self.assertTrue(all(gate.passed for gate in result.gates))
            self.assertEqual(engine.calls, ["probe", "create", "cancel", "close"])

    def test_failure_is_preserved_and_emergency_close_attempted(self):
        with TemporaryDirectory() as folder:
            engine = RecordingConformanceEngine(fail_at="create")
            with HashChainLedger(Path(folder, "ledger.sqlite3")) as ledger:
                result = asyncio.run(run_lifecycle(engine, mission_id="mission-test", ledger=ledger))
            self.assertEqual(result.status, "FAIL")
            self.assertIn("create failure", result.error)
            self.assertEqual(engine.calls, ["probe", "create", "close"])
            self.assertTrue(result.gates[-1].passed)

    def test_receipt_from_another_mission_is_rejected(self):
        class WrongMissionEngine(RecordingConformanceEngine):
            async def cancel(self, session, reason):
                receipt = await super().cancel(session, reason)
                return replace(receipt, mission_id="foreign-mission")

        with TemporaryDirectory() as folder:
            engine = WrongMissionEngine()
            with HashChainLedger(Path(folder, "ledger.sqlite3")) as ledger:
                result = asyncio.run(run_lifecycle(engine, mission_id="mission-test", ledger=ledger))
            self.assertEqual(result.status, "FAIL")
            cancel_gate = next(gate for gate in result.gates if gate.gate == "CANCEL_NO_EFFECT")
            self.assertFalse(cancel_gate.passed)
            self.assertIn("MISSION", cancel_gate.evidence)


if __name__ == "__main__":
    unittest.main()
