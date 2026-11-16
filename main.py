from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
import shutil
import sqlite3

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import db
from engine import AGENTS, POLICY_VERSION, build_decision, customer_journey_proposals, consent_violation_proposals, make_proposal, run_benchmark
from models import DecisionBatch, DecisionContract


ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"

app = FastAPI(
    title="TreatyAI Decision Governance API",
    version="0.1.0",
    description="Cross-agent decision governance, constrained resolution and verified execution.",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.on_event("startup")
def startup() -> None:
    db.init_db()


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health() -> dict[str, Any]:
    usage = shutil.disk_usage(ROOT)
    return {
        "status": "operational",
        "product": "TreatyAI",
        "mode": "deterministic-local-demo",
        "policy_version": POLICY_VERSION,
        "storage": {
            "database": str(db.DB_PATH),
            "database_bytes": db.DB_PATH.stat().st_size if db.DB_PATH.exists() else 0,
            "project_bytes": sum(p.stat().st_size for p in ROOT.rglob("*") if p.is_file() and "__pycache__" not in str(p)),
            "free_disk_gb": round(usage.free / (1024 ** 3), 2),
        },
    }


@app.get("/api/overview")
def overview() -> dict[str, Any]:
    data = db.get_overview()
    audit = db.verify_event_chain()
    return {
        **data,
        "audit": audit,
        "agents": len(AGENTS),
        "policy_version": POLICY_VERSION,
    }


@app.get("/api/agents")
def agents() -> dict[str, Any]:
    return {
        "agents": [
            {"id": key, **value}
            for key, value in AGENTS.items()
        ]
    }


@app.get("/api/policies")
def policies() -> dict[str, Any]:
    return {
        "version": POLICY_VERSION,
        "principles": [
            {"id": "P-01", "name": "Delegated authority", "severity": "hard", "description": "An agent may only propose actions within its registered capability scope and monetary limit."},
            {"id": "P-02", "name": "Global compensation ceiling", "severity": "hard", "description": "The combined value of selected credits must not exceed the customer's remaining allowance."},
            {"id": "P-03", "name": "Marketing consent", "severity": "hard", "description": "Marketing actions require active customer consent; prompts and agent rationale cannot override consent."},
            {"id": "P-04", "name": "Critical-case precedence", "severity": "hard", "description": "Promotional outreach is deferred while a critical customer case remains open."},
            {"id": "P-05", "name": "Contact-frequency limit", "severity": "hard", "description": "Outbound actions across agents share one customer-level contact allowance."},
            {"id": "P-06", "name": "Human approval boundary", "severity": "hard", "description": "Actions marked as requiring human approval cannot be autonomously committed."},
            {"id": "P-07", "name": "Idempotent execution", "severity": "hard", "description": "An approved proposal may be committed only once using its idempotency key."},
            {"id": "P-08", "name": "Evidence-linked decisions", "severity": "governance", "description": "Decision receipts preserve proposal evidence, policy version, verification results and outcome rationale."},
            {"id": "P-09", "name": "Customer scope and freshness", "severity": "hard", "description": "Every proposal must target the transaction customer and be re-evaluated against the latest customer-state version before commit."},
        ],
    }


@app.get("/api/scenarios")
def scenarios() -> dict[str, Any]:
    return {
        "scenarios": [
            {
                "id": "customer-journey",
                "name": "Customer journey conflict",
                "category": "Cross-agent budget + temporal conflict",
                "customer_id": "C-1042",
                "customer_name": "Nadia El Amrani",
                "description": "Service and retention agents request overlapping compensation while marketing proposes an untimely campaign.",
                "proposals": 3,
                "difficulty": "High",
            },
            {
                "id": "consent-boundary",
                "name": "Consent boundary attack",
                "category": "Consent + prompt injection",
                "customer_id": "C-1043",
                "customer_name": "Youssef Bennani",
                "description": "A marketing proposal includes an instruction-like note attempting to override a withdrawn consent state.",
                "proposals": 2,
                "difficulty": "Critical",
            },
        ]
    }


def _scenario_payload(scenario_id: str) -> tuple[str, list[DecisionContract]]:
    if scenario_id == "customer-journey":
        return "C-1042", customer_journey_proposals("C-1042")
    if scenario_id == "consent-boundary":
        return "C-1043", consent_violation_proposals("C-1043")
    raise HTTPException(status_code=404, detail="Unknown scenario")


@app.post("/api/scenarios/{scenario_id}/run")
def run_scenario(scenario_id: str) -> dict[str, Any]:
    customer_id, proposals = _scenario_payload(scenario_id)
    customer = db.get_customer(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    proposals = [p.model_copy(update={"expected_state_version": customer["state_version"]}) for p in proposals]
    preview = build_decision(scenario_id, customer, proposals)
    try:
        result = db.create_decision(scenario_id, customer_id, preview, commit_actions=True)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return result


@app.post("/api/demo/reset")
def reset_demo() -> dict[str, Any]:
    return db.reset_demo()


@app.post("/api/concurrency/run")
def run_concurrency() -> dict[str, Any]:
    # Reset a dedicated synthetic customer, then submit two 100 MAD proposals
    # concurrently. Each transaction re-reads and locks the shared budget.
    db.reset_demo()
    customer_id = "C-2099"
    initial_customer = db.get_customer(customer_id)
    expected_version = initial_customer["state_version"]
    proposals = [
        make_proposal("RACE-AGENT-A", "service-agent", customer_id, "issue_credit", amount=100, priority=1, utility=90, allow_partial=True, rationale="Concurrent service compensation request.", expected_state_version=expected_version),
        make_proposal("RACE-AGENT-B", "retention-agent", customer_id, "issue_credit", amount=100, priority=2, utility=80, allow_partial=True, rationale="Concurrent retention compensation request.", expected_state_version=expected_version),
    ]

    def submit(proposal: DecisionContract) -> dict[str, Any]:
        customer = db.get_customer(customer_id)
        preview = build_decision("concurrency-race", customer, [proposal])
        return db.create_decision("concurrency-race", customer_id, preview, commit_actions=True)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(submit, p) for p in proposals]
        results = [future.result() for future in futures]

    final_customer = db.get_customer(customer_id)
    committed = sum(r["plan"]["total_compensation_mad"] for r in results if r["status"] == "committed")
    return {
        "test": "concurrent-shared-budget",
        "initial_budget_mad": 150,
        "requested_total_mad": 200,
        "committed_total_mad": round(committed, 2),
        "remaining_budget_mad": final_customer["remaining_budget_mad"],
        "no_overspend": committed <= 150 and final_customer["remaining_budget_mad"] >= -1e-9,
        "results": [
            {
                "decision_id": r["decision_id"],
                "status": r["status"],
                "outcomes": r["plan"]["outcomes"],
                "committed_mad": r["plan"]["total_compensation_mad"],
                "receipt_hash": r["receipt"]["receipt_hash"],
                "state_revalidation": r["state_revalidation"],
            }
            for r in results
        ],
        "customer": final_customer,
        "explanation": "SQLite BEGIN IMMEDIATE serializes the prepare/verify/commit critical section. The second request is re-evaluated against the updated remaining budget.",
    }


@app.post("/api/bench/run")
def benchmark() -> dict[str, Any]:
    return db.save_benchmark(run_benchmark(30))


@app.get("/api/bench/latest")
def latest_benchmark() -> dict[str, Any]:
    result = db.latest_benchmark()
    return result or {"available": False}




@app.post("/api/decisions/coordinate")
def coordinate(batch: DecisionBatch) -> dict[str, Any]:
    """Accept a batch of agent intents through the future integration boundary."""
    customer = db.get_customer(batch.customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    preview = build_decision(batch.scenario_id, customer, batch.proposals)
    try:
        return db.create_decision(batch.scenario_id, batch.customer_id, preview, commit_actions=True)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.get("/api/decisions")
def decisions(limit: int = Query(default=30, ge=1, le=100)) -> dict[str, Any]:
    return {"decisions": db.list_decisions(limit)}


@app.get("/api/decisions/{decision_id}")
def decision(decision_id: str) -> dict[str, Any]:
    result = db.get_decision(decision_id)
    if not result:
        raise HTTPException(status_code=404, detail="Decision not found")
    return result


@app.get("/api/events")
def events(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
    return {"events": db.list_events(limit), "integrity": db.verify_event_chain()}


@app.get("/api/audit/verify")
def audit_verify() -> dict[str, Any]:
    return db.verify_event_chain()


@app.get("/api/receipts/{decision_id}/verify")
def verify_receipt(decision_id: str) -> dict[str, Any]:
    result = db.verify_receipt(decision_id)
    if not result:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return result


@app.get("/api/receipts")
def receipts(limit: int = Query(default=30, ge=1, le=100)) -> dict[str, Any]:
    rows = db.list_decisions(limit)
    return {
        "receipts": [
            {
                "decision_id": row["decision_id"],
                "scenario_id": row["scenario_id"],
                "customer_id": row["customer_id"],
                "status": row["status"],
                "created_at": row["created_at"],
                "receipt": row["receipt"],
                "summary": row["summary"],
            }
            for row in rows
        ]
    }
