import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from kch_psa.ledger import GENESIS_HASH, HashChainLedger


class LedgerTests(unittest.TestCase):
    def test_append_replay_and_chain(self):
        with TemporaryDirectory() as folder:
            path = Path(folder, "ledger.sqlite3")
            with HashChainLedger(path) as ledger:
                first = ledger.append("FIRST", {"value": 1})
                second = ledger.append("SECOND", {"value": 2})
                verification = ledger.verify()
                self.assertEqual(first.previous_hash, GENESIS_HASH)
                self.assertEqual(second.previous_hash, first.event_hash)
                self.assertTrue(verification.valid)
                self.assertEqual(verification.event_count, 2)
                self.assertEqual(verification.head, second.event_hash)

    def test_payload_tampering_is_detected(self):
        with TemporaryDirectory() as folder:
            path = Path(folder, "ledger.sqlite3")
            with HashChainLedger(path) as ledger:
                ledger.append("FIRST", {"value": 1})
            connection = sqlite3.connect(path)
            connection.execute("UPDATE events SET payload_json='{}' WHERE sequence=1")
            connection.commit()
            connection.close()
            with HashChainLedger(path) as ledger:
                verification = ledger.verify()
                self.assertFalse(verification.valid)
                self.assertEqual(verification.reason, "PAYLOAD_HASH_MISMATCH")

    def test_invalid_json_tampering_returns_failure_not_exception(self):
        with TemporaryDirectory() as folder:
            path = Path(folder, "ledger.sqlite3")
            with HashChainLedger(path) as ledger:
                ledger.append("FIRST", {"value": 1})
            connection = sqlite3.connect(path)
            connection.execute("UPDATE events SET payload_json='{' WHERE sequence=1")
            connection.commit()
            connection.close()
            with HashChainLedger(path) as ledger:
                verification = ledger.verify()
                self.assertFalse(verification.valid)
                self.assertEqual(verification.reason, "PAYLOAD_JSON_INVALID")

    def test_duplicate_event_id_is_rejected_without_chain_mutation(self):
        with TemporaryDirectory() as folder:
            path = Path(folder, "ledger.sqlite3")
            with HashChainLedger(path) as ledger:
                first = ledger.append("FIRST", {"value": 1}, event_id="fixed")
                with self.assertRaises(sqlite3.IntegrityError):
                    ledger.append("DUPLICATE", {"value": 2}, event_id="fixed")
                verification = ledger.verify()
                self.assertTrue(verification.valid)
                self.assertEqual(verification.event_count, 1)
                self.assertEqual(verification.head, first.event_hash)


if __name__ == "__main__":
    unittest.main()
