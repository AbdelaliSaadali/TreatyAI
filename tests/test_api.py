from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient
from unittest.mock import patch
import db
from main import app
import main
from engine import make_proposal


class ApiIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original_data_dir = db.DATA_DIR
        self.original_db_path = db.DB_PATH
        db.DATA_DIR = Path(self.temp.name)
        db.DB_PATH = Path(self.temp.name) / "api-test.sqlite3"
        self.integration_token = "integration-test-" + "a" * 35
        self.token_patch = patch.dict("os.environ", {"TREATYAI_INTEGRATION_TOKEN": self.integration_token})
        self.token_patch.start()

    def tearDown(self):
        db.DATA_DIR = self.original_data_dir
        db.DB_PATH = self.original_db_path
        self.temp.cleanup()
        self.token_patch.stop()

    def test_local_app_and_flagship_decision(self):
        with TestClient(app) as client:
            self.assertEqual(client.get("/").status_code, 200)
            health = client.get("/api/health").json()
            self.assertEqual(health["status"], "operational")

            result = client.post("/api/scenarios/customer-journey/run").json()
            self.assertEqual(result["status"], "committed")
            self.assertEqual(result["plan"]["total_compensation_mad"], 150)
            self.assertTrue(result["verification"]["passed"])
            receipt_check = client.get("/api/receipts/" + result["decision_id"] + "/verify").json()
            self.assertTrue(receipt_check["valid"])

            audit = client.get("/api/audit/verify").json()
            self.assertTrue(audit["valid"])
            self.assertGreaterEqual(audit["events_verified"], 3)

    def test_generic_agent_adapter_contract_and_replay_protection(self):
        with TestClient(app) as client:
            customer = db.get_customer("C-1043")
            proposal = make_proposal(
                "EXT-CALLBACK-01", "retention-agent", "C-1043",
                "schedule_callback", channel="phone", utility=65,
                expected_state_version=customer["state_version"],
            )
            payload = {
                "scenario_id": "external-adapter-demo",
                "customer_id": "C-1043",
                "proposals": [proposal.public_dict()],
            }
            headers = {"Authorization": "Bearer " + self.integration_token}
            denied = client.post("/api/decisions/coordinate", json=payload)
            self.assertEqual(denied.status_code, 401)
            first = client.post("/api/decisions/coordinate", json=payload, headers=headers)
            self.assertEqual(first.status_code, 200)
            self.assertEqual(first.json()["status"], "committed")
            replay = client.post("/api/decisions/coordinate", json=payload, headers=headers)
            self.assertEqual(replay.status_code, 409)

    def test_groq_setup_is_same_origin_and_never_echoes_secret(self):
        with TestClient(app) as client:
            payload = {"api_key": "gsk_" + "A" * 48}
            forbidden = client.post("/api/ai/configure", json=payload, headers={
                "Origin": "https://malicious.example",
            })
            self.assertEqual(forbidden.status_code, 403)
            with patch("main.store_groq_key") as store:
                with patch("main.validate_remote_key", return_value={"validated": True, "available_models": ["openai/gpt-oss-20b"]}):
                  with patch("main.groq_status", return_value={"configured": True}):
                    allowed = client.post("/api/ai/configure", json=payload, headers={
                        "Origin": "http://testserver",
                    })
                    # The test server hostname is intentionally not a permitted
                    # loopback host for the actual credential endpoint.
                    self.assertEqual(allowed.status_code, 403)
                    store.assert_not_called()
                    with TestClient(app, base_url="http://127.0.0.1:8765") as local_client:
                        configured = local_client.post("/api/ai/configure", json=payload,
                                                       headers={"Origin": "http://127.0.0.1:8765"})
                        self.assertEqual(configured.status_code, 200)
                        self.assertTrue(configured.json()["configured"])
                        self.assertNotIn(payload["api_key"], configured.text)
                        store.assert_called_once_with(payload["api_key"])

    def test_unconfigured_live_run_fails_closed(self):
        with TestClient(app) as client:
            with patch("groq_provider.resolve_key", return_value=None):
                before = db.get_customer("C-1042")
                response = client.post("/api/ai/run", json={
                    "scenario_id": "customer-journey", "negotiation": "deep",
                })
                self.assertEqual(response.status_code, 503)
                self.assertEqual(db.get_customer("C-1042")["remaining_budget_mad"],
                                 before["remaining_budget_mad"])
                self.assertEqual(db.list_decisions(), [])

    def test_external_adapter_refuses_unconfigured_auth(self):
        with TestClient(app) as client:
            with patch.dict("os.environ", {"TREATYAI_INTEGRATION_TOKEN": ""}):
                response = client.post("/api/decisions/coordinate", json={
                    "scenario_id": "disabled-gateway",
                    "customer_id": "C-1042",
                    "proposals": [],
                })
                self.assertEqual(response.status_code, 503)

    def test_security_headers_are_present_on_all_api_responses(self):
        with TestClient(app) as client:
            response = client.get("/api/overview")
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            self.assertEqual(response.headers["X-Frame-Options"], "DENY")
            self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
            self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

    def test_invalid_external_customer_scope_is_422(self):
        with TestClient(app) as client:
            proposal = make_proposal("WRONG-SCOPE-1", "service-agent", "C-1043",
                                     "issue_credit", amount=25)
            response = client.post("/api/decisions/coordinate", json={
                "scenario_id": "scope-isolation-test",
                "customer_id": "C-1042",
                "proposals": [proposal.public_dict()],
            }, headers={"Authorization": "Bearer " + self.integration_token})
            self.assertEqual(response.status_code, 422)
            self.assertFalse(db.list_decisions())

    def test_parallel_ai_runs_are_rate_limited(self):
        with TestClient(app) as client:
            main._AI_RUN_GATE.acquire()
            try:
                response = client.post("/api/ai/run", json={
                    "scenario_id": "customer-journey", "negotiation": "deep",
                })
                self.assertEqual(response.status_code, 429)
                self.assertFalse(db.list_decisions())
            finally:
                main._AI_RUN_GATE.release()

    def test_concurrency_and_benchmark_endpoints(self):
        with TestClient(app) as client:
            race = client.post("/api/concurrency/run").json()
            self.assertTrue(race["no_overspend"])
            self.assertEqual(race["committed_total_mad"], 150)

            benchmark = client.post("/api/bench/run").json()
            self.assertEqual(benchmark["cases"], 30)
            self.assertEqual(benchmark["treatyai"]["global_budget_violations"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
