from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import unittest

from kch_psa.canonical import canonical_json


ROOT = Path(__file__).resolve().parents[1]
RECEIPT_CANONICAL_SHA256 = (
    "8eb8444f4ec4ef99408fabe4e911984674493ff35e8defe2ee00aedb0cee9fd4"
)


class ProcessSupervisorArtifactTests(unittest.TestCase):
    def test_versioned_witness_receipt_preserves_canonical_content(self) -> None:
        path = ROOT / "docs" / "receipts" / "PROCESS_SUPERVISOR_WITNESS_20261106_R1.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        canonical_digest = sha256(canonical_json(payload).encode("utf-8")).hexdigest()

        self.assertEqual(canonical_digest, RECEIPT_CANONICAL_SHA256)
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["lifecycle_phase"], "STOPPED")
        self.assertEqual(payload["ledger_event_count"], 4)
        self.assertEqual(
            payload["ledger_head"],
            "efd0b9e9bd4de9294ea650242e9121adf87b7c73aabbe30f8c12418d3b304fca",
        )

    def test_process_supervisor_schemas_are_versioned_draft_2020_12(self) -> None:
        managed = json.loads(
            (ROOT / "schemas" / "managed-process-record.schema.json").read_text(
                encoding="utf-8"
            )
        )
        witness = json.loads(
            (ROOT / "schemas" / "process-supervisor-witness.schema.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(
            managed["$schema"], "https://json-schema.org/draft/2020-12/schema"
        )
        self.assertEqual(
            managed["properties"]["schema"]["const"],
            "kch-psa.managed-process-record.v0.1.0",
        )
        self.assertEqual(
            witness["$schema"], "https://json-schema.org/draft/2020-12/schema"
        )
        statuses = {
            item["properties"]["status"]["const"]
            for item in (witness["$defs"]["passReceipt"], witness["$defs"]["failReceipt"])
        }
        self.assertEqual(statuses, {"PASS", "FAIL"})


if __name__ == "__main__":
    unittest.main()
