"""Adversarial and randomized invariants for the governance core.

The tests use only Python's standard library and deterministic synthetic data.
"""
from __future__ import annotations

from copy import deepcopy
from itertools import product
import random
import unittest

from engine import AGENTS, _variants, build_decision, build_conflict_graph, make_proposal
from verifier import verify_plan


def customer(**changes):
    state = {
        "id": "C-PROP",
        "name": "Synthetic test customer",
        "segment": "Premium",
        "remaining_budget_mad": 100.0,
        "marketing_consent": True,
        "open_critical_case": False,
        "communications_last_24h": 0,
        "max_communications_per_24h": 1,
        "state_version": 1,
    }
    state.update(changes)
    return state


def proposals_for(state, credit_amounts=(40, 40, 40)):
    agents = ["service-agent", "retention-agent", "billing-agent"]
    return [
        make_proposal(
            f"CASE-{state['id']}-{i}", agents[i], state["id"], "issue_credit",
            amount=amount, allow_partial=True, utility=90 - 10*i,
            priority=i+1, expected_state_version=state["state_version"],
        )
        for i, amount in enumerate(credit_amounts)
    ]


class GraphAndInvariantTests(unittest.TestCase):
    def test_three_way_budget_conflict_not_visible_pairwise(self):
        state = customer()
        proposals = proposals_for(state)
        graph = build_conflict_graph(proposals, state)
        edges = [e for e in graph["edges"] if e["type"] == "aggregate_budget"]
        self.assertEqual(len(edges), 3)
        self.assertTrue(build_decision("triple-budget", state, proposals)["verification"]["passed"])

    def test_contact_conflict_only_when_total_exceeds_capacity(self):
        state = customer(max_communications_per_24h=2)
        props = [
            make_proposal("CONTACT-MKT", "marketing-agent", state["id"], "send_marketing", channel="email"),
            make_proposal("CONTACT-CALL", "retention-agent", state["id"], "schedule_callback", channel="phone"),
        ]
        self.assertEqual([e for e in build_conflict_graph(props, state)["edges"]
                          if e["type"] == "contact_frequency"], [])
        state["max_communications_per_24h"] = 1
        self.assertEqual(len([e for e in build_conflict_graph(props, state)["edges"]
                              if e["type"] == "contact_frequency"]), 1)

    def test_irreversible_and_case_resolution_require_human(self):
        state = customer(open_critical_case=True)
        for action, irreversible in [("resolve_case", False), ("issue_credit", True)]:
            props = [
                make_proposal("HUMAN-"+action, "service-agent", state["id"], action,
                              amount=30 if action == "issue_credit" else 0,
                              reversible=not irreversible),
            ]
            decision = build_decision("human", state, props)
            self.assertEqual(decision["status"], "awaiting_human")
            self.assertEqual(decision["plan"]["outcomes"][0]["status"], "needs_human")
            self.assertFalse(decision["plan"]["selected"])

    def test_tampered_budget_total_cannot_pass_verifier(self):
        state = customer()
        props = proposals_for(state, (60, 60, 40))
        plan = build_decision("tamper", state, props)["plan"]
        changed = deepcopy(plan)
        changed["total_compensation_mad"] = 0
        self.assertFalse(verify_plan(props, state, changed, AGENTS)["passed"])

    def test_tampered_action_amount_cannot_pass_verifier(self):
        state = customer()
        props = proposals_for(state, (60, 40, 30))
        plan = deepcopy(build_decision("tamper", state, props)["plan"])
        plan["selected"][0]["amount_mad"] = 500
        self.assertFalse(verify_plan(props, state, plan, AGENTS)["passed"])

    def test_tampered_score_cannot_pass_verifier(self):
        state = customer()
        props = proposals_for(state, (60, 40, 30))
        plan = deepcopy(build_decision("tamper", state, props)["plan"])
        plan["objective_score"] += 1000
        self.assertFalse(verify_plan(props, state, plan, AGENTS)["passed"])

    def test_duplicate_and_unknown_selected_actions_are_not_verified(self):
        state = customer()
        props = proposals_for(state, (50, 40, 30))
        plan = deepcopy(build_decision("tamper", state, props)["plan"])
        plan["selected"].append(deepcopy(plan["selected"][0]))
        self.assertFalse(verify_plan(props, state, plan, AGENTS)["passed"])
        plan["selected"][-1]["proposal_id"] = "UNKNOWN-PROPOSAL"
        self.assertFalse(verify_plan(props, state, plan, AGENTS)["passed"])

    def test_fabricated_outcome_cannot_pass_verifier(self):
        state = customer(marketing_consent=False)
        prop = make_proposal("MKT-FALSE", "marketing-agent", state["id"], "send_marketing", channel="email")
        plan = deepcopy(build_decision("tamper", state, [prop])["plan"])
        plan["outcomes"][0]["status"] = "approved"
        self.assertFalse(verify_plan([prop], state, plan, AGENTS)["passed"])

    def test_randomized_policy_invariants(self):
        rng = random.Random(41729)
        for index in range(180):
            state = customer(
                remaining_budget_mad=rng.choice((0, 25, 50, 75, 100, 150, 250)),
                marketing_consent=rng.choice((True, False)),
                open_critical_case=rng.choice((True, False)),
                communications_last_24h=rng.choice((0, 1, 2)),
                max_communications_per_24h=rng.choice((1, 2, 3)),
            )
            props = []
            for i in range(rng.randint(2, 5)):
                action, agent = rng.choice((
                    ("issue_credit", "service-agent"),
                    ("issue_credit", "retention-agent"),
                    ("issue_credit", "billing-agent"),
                    ("send_marketing", "marketing-agent"),
                    ("schedule_callback", "retention-agent"),
                ))
                props.append(make_proposal(
                    f"FUZZ-{index}-{i}", agent, state["id"], action,
                    amount=rng.choice((25, 50, 75, 100)) if action == "issue_credit" else 0,
                    channel="email" if action == "send_marketing" else "phone" if action == "schedule_callback" else "none",
                    allow_partial=action == "issue_credit",
                    priority=rng.randint(1, 5),
                    utility=rng.randint(1, 100),
                ))
            decision = build_decision("fuzz", state, props)
            with self.subTest(case=index):
                self.assertTrue(decision["verification"]["passed"])
                self.assertLessEqual(decision["plan"]["total_compensation_mad"],
                                     state["remaining_budget_mad"] + 1e-9)
                self.assertLessEqual(decision["plan"]["outbound_actions"],
                                     max(0,state["max_communications_per_24h"] -
                                             state["communications_last_24h"]))
                for outcome in decision["plan"]["outcomes"]:
                    if outcome["action_type"] == "send_marketing" and (
                        not state["marketing_consent"] or state["open_critical_case"]
                    ):
                        self.assertNotIn(outcome["status"], ("approved", "adjusted"))

    def test_optimizer_matches_exhaustive_small_credit_oracle(self):
        rng = random.Random(894)
        for trial in range(45):
            state = customer(remaining_budget_mad=rng.choice((50, 75, 100, 120, 150)))
            amounts = (rng.choice((25, 40, 50, 60, 75)), rng.choice((25, 40, 50, 60, 75)), rng.choice((25, 40, 50, 60, 75)))
            props = proposals_for(state, amounts)
            decision = build_decision("oracle", state, props)
            candidates = [[None] + _variants(p) for p in props]
            oracle = 0
            for combination in product(*candidates):
                chosen = [c for c in combination if c is not None]
                if sum(c["amount_mad"] for c in chosen) <= state["remaining_budget_mad"] + 1e-9:
                    oracle = max(oracle, sum(c["utility"] for c in chosen))
            with self.subTest(trial=trial):
                self.assertEqual(decision["plan"]["objective_score"], oracle)


if __name__ == "__main__":
    unittest.main(verbosity=2)
