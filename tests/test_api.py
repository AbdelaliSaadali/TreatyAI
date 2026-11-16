from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient
import db
from main import app
from engine import make_proposal


class ApiIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original_data_dir = db.DATA_DIR
        self.original_db_path = db.DB_PATH
        db.DATA_DIR = Path(self.temp.name)
        db.DB_PATH = Path(self.temp.name) / "api-test.sqlite3"

    def tearDown(self):
        db.DATA_DIR = self.original_data_dir
        db.DB_PATH = self.original_db_path
        self.temp.cleanup()

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
            first = client.post("/api/decisions/coordinate", json=payload)
            self.assertEqual(first.status_code, 200)
            self.assertEqual(first.json()["status"], "committed")
            replay = client.post("/api/decisions/coordinate", json=payload)
            self.assertEqual(replay.status_code, 409)

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
