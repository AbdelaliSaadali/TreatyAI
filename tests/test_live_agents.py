from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

import db
from groq_provider import GroqProvider, GroqConfigurationError, GroqGenerationError
from live_agents import LiveRunRequest, run_live, SpecialistDecision, json_schema


class FakeGroqProvider:
    model = "openai/gpt-oss-20b"

    def __init__(self, *, broken_phase: str | None = None):
        self.broken_phase = broken_phase
        self.calls: list[str] = []

    def complete(self, *, system, user, schema_name, schema, max_tokens):
        self.calls.append(schema_name)
        if self.broken_phase == schema_name:
            raise GroqGenerationError("Simulated provider failure")
        if schema_name == "treatyai_specialist":
            agent = user["agent_identity"]
            action = user["assigned_action_type"]
            amount = 100 if action == "issue_credit" else 0
            output = {
                "decision": "propose",
                "action_type": action,
                "amount_mad": amount,
                "priority": 1 if agent == "service-agent" else 2 if agent == "retention-agent" else 4,
                "utility": 96 if agent == "service-agent" else 80 if agent == "retention-agent" else 55,
                "allow_partial": action == "issue_credit",
                "rationale": "Synthetic specialist recommends a bounded business action.",
                "negotiation_offer": "Accept partial compensation if budget is scarce.",
                "evidence_refs": user["allowed_evidence"],
            }
        elif schema_name == "treatyai_mediator":
            output = {
                "conflict_summary": "Two credit proposals compete over one customer allowance.",
                "risk_flags": ["shared_budget", "open_critical_case"],
                "suggested_service_mad": 100,
                "suggested_retention_mad": 50,
                "marketing_disposition": "defer",
                "negotiation_rationale": "Prioritize service compensation and permit reduced retention credit.",
                "human_review_advised": False,
            }
        elif schema_name == "treatyai_counteroffer":
            amount = user["mediator_suggested_credit_mad"]
            output = {
                "accept": True,
                "counteroffer_mad": amount,
                "rationale": "Agreed to the proposed compromise.",
            }
        else:
            raise AssertionError(f"Unexpected schema: {schema_name}")
        return {
            "output": output,
            "model": self.model,
            "latency_ms": 10,
            "usage": {"prompt_tokens": 200, "completion_tokens": 80, "total_tokens": 280},
        }


class LiveWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_dir, self.old_path = db.DATA_DIR, db.DB_PATH
        db.DATA_DIR = Path(self.temp.name)
        db.DB_PATH = Path(self.temp.name) / "live-test.sqlite3"
        db.init_db()

    def tearDown(self):
        db.DATA_DIR, db.DB_PATH = self.old_dir, self.old_path
        self.temp.cleanup()

    def test_deep_live_negotiation_is_independent_and_verified(self):
        fake = FakeGroqProvider()
        decision = run_live(LiveRunRequest(scenario_id="customer-journey", negotiation="deep"), provider=fake)
        self.assertEqual(decision["status"], "committed")
        self.assertTrue(decision["verification"]["passed"])
        self.assertEqual(decision["plan"]["total_compensation_mad"], 150)
        self.assertEqual(decision["ai_trace"]["model_calls"], 6)
        self.assertFalse(decision["ai_trace"]["mediation_is_authoritative"])
        self.assertEqual(fake.calls.count("treatyai_specialist"), 3)
        self.assertEqual(fake.calls.count("treatyai_mediator"), 1)
        self.assertEqual(fake.calls.count("treatyai_counteroffer"), 2)
        self.assertTrue(db.verify_receipt(decision["decision_id"])["valid"])
        outcomes = {item["agent_id"]: item for item in decision["plan"]["outcomes"]}
        self.assertEqual(outcomes["service-agent"]["approved_amount_mad"], 100)
        self.assertEqual(outcomes["retention-agent"]["approved_amount_mad"], 50)
        self.assertEqual(outcomes["marketing-agent"]["status"], "deferred")

    def test_consent_attack_is_not_authorized_even_when_llm_proposes_it(self):
        decision = run_live(LiveRunRequest(scenario_id="consent-boundary"), provider=FakeGroqProvider())
        self.assertEqual(decision["status"], "committed")
        outcomes = {item["agent_id"]: item for item in decision["plan"]["outcomes"]}
        self.assertEqual(outcomes["marketing-agent"]["status"], "rejected")
        self.assertIn("MARKETING_CONSENT_WITHDRAWN", outcomes["marketing-agent"]["reason_codes"])
        self.assertEqual(outcomes["retention-agent"]["status"], "approved")
        self.assertTrue(db.verify_receipt(decision["decision_id"])["valid"])

    def test_provider_failure_does_not_commit_or_mutate(self):
        before = db.get_customer("C-1042")
        provider = FakeGroqProvider(broken_phase="treatyai_mediator")
        with self.assertRaises(GroqGenerationError):
            run_live(LiveRunRequest(scenario_id="customer-journey"), provider=provider)
        after = db.get_customer("C-1042")
        self.assertEqual(before["state_version"], after["state_version"])
        self.assertEqual(before["remaining_budget_mad"], after["remaining_budget_mad"])
        self.assertEqual(db.list_decisions(), [])

    def test_model_cannot_inject_unregistered_evidence(self):
        class MaliciousProvider(FakeGroqProvider):
            def complete(self, **kwargs):
                result = super().complete(**kwargs)
                if kwargs["schema_name"] == "treatyai_specialist":
                    result["output"]["evidence_refs"] = ["invented:proof"]
                return result
        with self.assertRaises(ValueError):
            run_live(LiveRunRequest(scenario_id="customer-journey"), provider=MaliciousProvider())
        self.assertEqual(db.list_decisions(), [])

    def test_tampered_llm_trace_is_detected(self):
        decision = run_live(LiveRunRequest(scenario_id="customer-journey"), provider=FakeGroqProvider())
        with db.transaction(immediate=True) as conn:
            row = conn.execute("SELECT decision_json FROM decisions WHERE id=?", (decision["decision_id"],)).fetchone()
            record = json.loads(row["decision_json"])
            record["ai_trace"]["mode"] = "fabricated"
            conn.execute("UPDATE decisions SET decision_json=? WHERE id=?", (db.canonical_json(record), decision["decision_id"]))
        self.assertFalse(db.verify_receipt(decision["decision_id"])["valid"])


class ProviderContractTests(unittest.TestCase):
    def test_strict_json_schema_has_all_required_keys(self):
        schema = json_schema(SpecialistDecision)
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["required"]), set(schema["properties"]))

    def test_provider_sends_strict_schema_without_leaking_key_into_response(self):
        def handler(request):
            self.assertEqual(request.url.host, "api.groq.com")
            self.assertEqual(request.headers["authorization"], "Bearer test-placeholder")
            body = json.loads(request.content)
            self.assertTrue(body["response_format"]["json_schema"]["strict"])
            self.assertEqual(body["model"], "openai/gpt-oss-20b")
            payload = {"x": "safe"}
            return httpx.Response(200, json={
                "choices": [{"message": {"content": json.dumps(payload)}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
            })

        transport = httpx.MockTransport(handler)
        with httpx.Client(transport=transport) as client:
            provider = GroqProvider(api_key="test-placeholder", client=client)
            result = provider.complete(
                system="Return JSON",
                user={"test": True},
                schema_name="unit_test",
                schema={"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"], "additionalProperties": False},
            )
        self.assertEqual(result["output"], {"x": "safe"})
        self.assertEqual(result["usage"]["total_tokens"], 8)
        self.assertNotIn("test-placeholder", json.dumps(result))

    def test_remote_key_validation_checks_supported_models(self):
        from groq_provider import validate_remote_key
        with patch("groq_provider.httpx.get") as get:
            get.return_value = httpx.Response(200, json={
                "data": [{"id": "openai/gpt-oss-20b"}, {"id": "openai/gpt-oss-120b"}]
            })
            result = validate_remote_key("test-placeholder")
            self.assertTrue(result["validated"])
            self.assertIn("openai/gpt-oss-20b", result["available_models"])
            self.assertEqual(get.call_args.args[0], "https://api.groq.com/openai/v1/models")
            self.assertNotIn("test-placeholder", json.dumps(result))

    def test_remote_key_validation_rejects_unauthorized(self):
        from groq_provider import validate_remote_key
        with patch("groq_provider.httpx.get", return_value=httpx.Response(401)):
            with self.assertRaises(GroqConfigurationError):
                validate_remote_key("test-placeholder")

    def test_incomplete_groq_response_fails_closed(self):
        payload = {"choices": [{"message": {"content": "{}"}, "finish_reason": "length"}]}
        with httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=payload)
        )) as client:
            provider = GroqProvider(api_key="dummy-test", client=client)
            with self.assertRaises(GroqGenerationError):
                provider.complete(system="test", user={}, schema_name="test",
                                  schema={"type": "object", "properties": {},
                                          "required": [], "additionalProperties": False})

    def test_key_rejection_avoids_exposing_secret(self):
        with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(401))) as client:
            provider = GroqProvider(api_key="private-placeholder", client=client)
            with self.assertRaises(GroqConfigurationError) as cm:
                provider.complete(system="test", user={}, schema_name="test",
                                  schema={"type": "object", "properties": {}, "required": [], "additionalProperties": False})
            self.assertNotIn("private-placeholder", str(cm.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
