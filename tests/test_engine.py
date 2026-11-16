from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import timedelta
import json
import sqlite3
import tempfile
import unittest

import db
from engine import (
    build_decision,
    consent_violation_proposals,
    customer_journey_proposals,
    make_proposal,
    run_benchmark,
)


def customer(**overrides):
    data = {
        "id": "C-TEST",
        "name": "Test Customer",
        "segment": "Premium",
        "remaining_budget_mad": 150.0,
        "marketing_consent": True,
        "open_critical_case": True,
        "communications_last_24h": 0,
        "max_communications_per_24h": 1,
        "state_version": 1,
    }
    data.update(overrides)
    return data


class DecisionEngineTests(unittest.TestCase):
    def test_global_budget_and_temporal_precedence(self):
        state = customer()
        proposals = customer_journey_proposals("C-TEST", expected_state_version=1)
        result = build_decision("customer-journey", state, proposals)

        self.assertTrue(result["verification"]["passed"])
        self.assertEqual(result["plan"]["total_compensation_mad"], 150)
        outcomes = {x["proposal_id"]: x for x in result["plan"]["outcomes"]}
        self.assertEqual(outcomes["PROP-SVC-100"]["status"], "approved")
        self.assertEqual(outcomes["PROP-RET-100"]["status"], "adjusted")
        self.assertEqual(outcomes["PROP-RET-100"]["approved_amount_mad"], 50)
        self.assertEqual(outcomes["PROP-MKT-EMAIL"]["status"], "deferred")
        self.assertGreaterEqual(len(result["conflict_graph"]["edges"]), 2)

    def test_proposal_cannot_target_another_customer(self):
        state = customer()
        proposal = make_proposal("WRONG-CUSTOMER", "service-agent", "C-OTHER", "issue_credit", amount=20)
        with self.assertRaisesRegex(ValueError, "CUSTOMER_SCOPE_MISMATCH"):
            build_decision("scope-test", state, [proposal])

    def test_withdrawn_consent_cannot_be_overridden_by_agent_text(self):
        state = customer(
            id="C-1043",
            marketing_consent=False,
            open_critical_case=False,
            remaining_budget_mad=75,
        )
        proposals = consent_violation_proposals("C-1043", expected_state_version=1)
        result = build_decision("consent-boundary", state, proposals)
        outcomes = {x["proposal_id"]: x for x in result["plan"]["outcomes"]}

        self.assertEqual(outcomes["PROP-MKT-OPT-OUT"]["status"], "rejected")
        self.assertIn("MARKETING_CONSENT_WITHDRAWN", outcomes["PROP-MKT-OPT-OUT"]["reason_codes"])
        self.assertEqual(outcomes["PROP-RET-CALL"]["status"], "approved")
        self.assertTrue(result["verification"]["passed"])

    def test_expired_proposal_is_rejected(self):
        from engine import utc_now
        state = customer(open_critical_case=False)
        now = utc_now()
        proposal = make_proposal("EXPIRED-01", "service-agent", "C-TEST", "issue_credit", amount=20)
        proposal = proposal.model_copy(update={"proposed_at": now - timedelta(minutes=2), "expires_at": now - timedelta(minutes=1)})
        result = build_decision("expiry-test", state, [proposal])
        self.assertEqual(result["plan"]["outcomes"][0]["status"], "rejected")
        self.assertIn("PROPOSAL_EXPIRED", result["plan"]["outcomes"][0]["reason_codes"])

    def test_agent_cannot_exceed_delegated_scope(self):
        state = customer(open_critical_case=False)
        proposal = make_proposal(
            "BAD-SCOPE", "marketing-agent", "C-TEST", "issue_credit",
            amount=25, utility=80,
        )
        result = build_decision("scope-test", state, [proposal])
        outcome = result["plan"]["outcomes"][0]
        self.assertEqual(outcome["status"], "rejected")
        self.assertIn("DELEGATED_SCOPE_MISSING", outcome["reason_codes"])

    def test_human_approval_is_not_autonomously_committed(self):
        state = customer(open_critical_case=False)
        proposal = make_proposal(
            "HUMAN-01", "service-agent", "C-TEST", "issue_credit",
            amount=25, utility=80, requires_human=True,
        )
        result = build_decision("human-gate", state, [proposal])
        self.assertEqual(result["status"], "awaiting_human")
        self.assertEqual(result["plan"]["total_compensation_mad"], 0)

    def test_benchmark_has_zero_treatyai_invariant_violations(self):
        result = run_benchmark(30)
        self.assertEqual(result["cases"], 30)
        self.assertGreater(result["baseline"]["global_budget_violations"], 0)
        self.assertGreater(result["baseline"]["contact_limit_violations"], 0)
        self.assertEqual(result["treatyai"]["global_budget_violations"], 0)
        self.assertEqual(result["treatyai"]["contact_limit_violations"], 0)
        self.assertEqual(result["treatyai"]["invariant_violations"], 0)


class PersistenceAndConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original_data_dir = db.DATA_DIR
        self.original_db_path = db.DB_PATH
        db.DATA_DIR = Path(self.temp.name)
        db.DB_PATH = Path(self.temp.name) / "test.sqlite3"
        db.init_db()

    def tearDown(self):
        db.DATA_DIR = self.original_data_dir
        db.DB_PATH = self.original_db_path
        self.temp.cleanup()

    def test_commit_is_idempotent(self):
        state = db.get_customer("C-1042")
        proposals = customer_journey_proposals("C-1042", expected_state_version=state["state_version"])
        preview = build_decision("customer-journey", state, proposals)
        first = db.create_decision("customer-journey", "C-1042", preview)
        self.assertEqual(first["status"], "committed")
        self.assertTrue(db.verify_receipt(first["decision_id"])["valid"])
        with self.assertRaises(sqlite3.IntegrityError):
            db.create_decision("customer-journey", "C-1042", preview)

    def test_receipt_payload_tampering_is_detected(self):
        state = db.get_customer("C-1042")
        proposals = customer_journey_proposals("C-1042", expected_state_version=state["state_version"])
        preview = build_decision("customer-journey", state, proposals)
        decision = db.create_decision("customer-journey", "C-1042", preview)
        with db.transaction(immediate=True) as conn:
            row = conn.execute("SELECT receipt_json FROM decisions WHERE id=?", (decision["decision_id"],)).fetchone()
            receipt = json.loads(row["receipt_json"])
            receipt["status"] = "tampered"
            conn.execute("UPDATE decisions SET receipt_json=? WHERE id=?", (db.canonical_json(receipt), decision["decision_id"]))
        self.assertFalse(db.verify_receipt(decision["decision_id"])["valid"])

    def test_concurrent_requests_cannot_overspend_shared_budget(self):
        db.reset_demo()
        state = db.get_customer("C-2099")
        version = state["state_version"]
        proposals = [
            make_proposal("RACE-A", "service-agent", "C-2099", "issue_credit", amount=100, utility=90, allow_partial=True, expected_state_version=version),
            make_proposal("RACE-B", "retention-agent", "C-2099", "issue_credit", amount=100, utility=80, allow_partial=True, expected_state_version=version),
        ]

        def submit(proposal):
            snapshot = db.get_customer("C-2099")
            preview = build_decision("race", snapshot, [proposal])
            return db.create_decision("race", "C-2099", preview)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, proposals))

        final = db.get_customer("C-2099")
        total = sum(r["plan"]["total_compensation_mad"] for r in results)
        self.assertEqual(total, 150)
        self.assertEqual(final["remaining_budget_mad"], 0)
        self.assertTrue(any(r["state_revalidation"]["revalidated"] for r in results))

    def test_event_chain_verifies_and_detects_tampering(self):
        db.reset_demo()
        self.assertTrue(db.verify_event_chain()["valid"])
        with db.transaction(immediate=True) as conn:
            conn.execute("UPDATE events SET payload_json='{}' WHERE id=1")
        self.assertFalse(db.verify_event_chain()["valid"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
