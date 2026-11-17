"""Independent TreatyAI plan verifier.

Does not import the optimizer or trust its summaries, scores or explanations.
It independently derives all safety-critical totals and compares the reported
outcome plan against the actual typed proposals and authoritative customer state.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any

from models import DecisionContract


def _near(a: Any, b: Any) -> bool:
    try:
        left = float(a)
        right = float(b)
        return math.isfinite(left) and math.isfinite(right) and abs(left - right) < 1e-6
    except (ValueError, TypeError, OverflowError):
        return False


def _check(check_id: str, label: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"id": check_id, "label": label, "passed": bool(passed), "detail": detail}


def verify_plan(proposals: list[DecisionContract], customer: dict[str, Any],
                plan: dict[str, Any], agents: dict[str, dict[str, Any]]) -> dict[str, Any]:
    proposals_by_id = {p.proposal_id: p for p in proposals}
    options = plan.get("selected", [])
    outcomes = plan.get("outcomes", [])
    if not isinstance(options, list):
        options = []
        structure_ok = False
    else:
        structure_ok = True
    if not isinstance(outcomes, list):
        outcomes = []
        structure_ok = False

    observed_ids: set[str] = set()
    observed_keys: set[str] = set()
    total = 0.0
    outbound = 0
    derived_score = 0
    authority_ok = True
    consent_ok = True
    idempotency_ok = True
    checks = []
    selected_amounts: dict[str, float] = {}

    for option in options:
        if not isinstance(option, dict):
            structure_ok = False
            continue
        proposal_id = option.get("proposal_id")
        if not isinstance(proposal_id, str) or proposal_id in observed_ids:
            structure_ok = False
            continue
        observed_ids.add(proposal_id)
        proposal = proposals_by_id.get(proposal_id)
        if proposal is None:
            structure_ok = False
            continue
        agent = agents.get(proposal.agent_id)
        if not agent:
            authority_ok = False
        elif proposal.action_type not in agent["scopes"]:
            authority_ok = False
        elif proposal.action_type == "issue_credit" and proposal.amount_mad > agent["max_credit_mad"]:
            authority_ok = False
        if (proposal.requires_human or not proposal.reversible
                or proposal.action_type == "resolve_case"
                or proposal.customer_id != customer["id"]):
            authority_ok = False
        if proposal.expires_at is not None and proposal.expires_at <= datetime.now(timezone.utc):
            authority_ok = False
        if option.get("action_type") != proposal.action_type:
            structure_ok = False
        if proposal.idempotency_key in observed_keys:
            idempotency_ok = False
        observed_keys.add(proposal.idempotency_key)
        amount = option.get("amount_mad")
        if not _near(amount, amount):
            structure_ok = False
            continue
        amount = float(amount)
        if amount < 0:
            authority_ok = False
            structure_ok = False
        if proposal.action_type == "issue_credit":
            if amount <= 0 or amount > proposal.amount_mad + 1e-6:
                authority_ok = False
            elif not proposal.allow_partial and not _near(amount, proposal.amount_mad):
                authority_ok = False
            else:
                choices = [proposal.amount_mad]
                if proposal.allow_partial and proposal.amount_mad >= 20:
                    choices.extend(round(proposal.amount_mad * ratio, 2) for ratio in (0.75, 0.5, 0.25))
                if not any(_near(amount, x) for x in choices):
                    structure_ok = False
            expected_utility = max(1, round(proposal.utility * amount / proposal.amount_mad -
                                              (4 if amount < proposal.amount_mad else 0)))
        else:
            if not _near(amount, 0):
                structure_ok = False
            expected_utility = proposal.utility
        if not _near(option.get("utility"), expected_utility):
            structure_ok = False
        if bool(option.get("adjusted")) != (proposal.action_type == "issue_credit" and amount < proposal.amount_mad):
            structure_ok = False
        total += amount
        derived_score += expected_utility
        selected_amounts[proposal_id] = amount
        if proposal.action_type in ("send_marketing", "schedule_callback"):
            outbound += 1
        if proposal.action_type == "send_marketing" and (
            not customer["marketing_consent"] or customer["open_critical_case"]
        ):
            consent_ok = False

    # An optimizer cannot self-report a different total, score or action count.
    if not _near(plan.get("total_compensation_mad"), total):
        structure_ok = False
    if not _near(plan.get("outbound_actions"), outbound):
        structure_ok = False
    if not _near(plan.get("objective_score"), derived_score):
        structure_ok = False
    if len(outcomes) != len(proposals):
        structure_ok = False

    outcome_ids: set[str] = set()
    for outcome in outcomes:
        if not isinstance(outcome, dict):
            structure_ok = False
            continue
        pid = outcome.get("proposal_id")
        if not isinstance(pid, str) or pid in outcome_ids or pid not in proposals_by_id:
            structure_ok = False
            continue
        outcome_ids.add(pid)
        proposal = proposals_by_id[pid]
        amount = selected_amounts.get(pid, 0.0)
        if outcome.get("agent_id") != proposal.agent_id or outcome.get("action_type") != proposal.action_type:
            structure_ok = False
        if not _near(outcome.get("original_amount_mad"), proposal.amount_mad):
            structure_ok = False
        if not _near(outcome.get("approved_amount_mad"), amount):
            structure_ok = False
        if pid in selected_amounts:
            expected_status = "adjusted" if amount < proposal.amount_mad else "approved"
            if outcome.get("status") != expected_status:
                structure_ok = False
        elif outcome.get("status") in ("approved", "adjusted"):
            structure_ok = False

    capacity = max(0, customer["max_communications_per_24h"] -
                   customer["communications_last_24h"])
    budget_ok = total <= customer["remaining_budget_mad"] + 1e-9
    contact_ok = outbound <= capacity
    checks.append(_check("plan_integrity", "Independent plan consistency", structure_ok,
                         "Selected actions, amount variants, totals, utility and outcome records match the contracts." if structure_ok
                         else "The optimizer reported inconsistent or unknown plan data."))
    checks.append(_check("delegated_authority", "Delegated authority", authority_ok,
                         "Every selected action is within its registered scope and requires no human approval." if authority_ok
                         else "At least one selected action violates delegated authority."))
    checks.append(_check("global_budget", "Global compensation budget", budget_ok,
                         f"{total:.0f} / {customer['remaining_budget_mad']:.0f} MAD allocated."))
    checks.append(_check("contact_limit", "Contact-frequency limit", contact_ok,
                         f"{outbound} / {capacity} outbound actions."))
    checks.append(_check("consent_and_journey", "Consent & journey precedence", consent_ok,
                         "No marketing action overrides consent or open-case suppression." if consent_ok
                         else "A marketing action violates customer consent or critical-case precedence."))
    checks.append(_check("idempotency", "Unique execution keys", idempotency_ok,
                         "Selected actions have distinct execution keys." if idempotency_ok
                         else "At least one execution key is reused."))
    return {
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
        "verified_compensation_mad": round(total, 2),
        "verified_outbound_actions": outbound,
        "verifier": "TreatyAI Independent Verifier v0.2",
    }
