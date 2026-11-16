from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
import hashlib
import json
import sqlite3
import uuid


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "treatyai.sqlite3"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


@contextmanager
def transaction(immediate: bool = False) -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with transaction(immediate=True) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            segment TEXT NOT NULL,
            remaining_budget_mad REAL NOT NULL,
            marketing_consent INTEGER NOT NULL,
            open_critical_case INTEGER NOT NULL,
            communications_last_24h INTEGER NOT NULL,
            max_communications_per_24h INTEGER NOT NULL,
            state_version INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS decisions (
            id TEXT PRIMARY KEY,
            scenario_id TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            status TEXT NOT NULL,
            decision_json TEXT NOT NULL,
            receipt_json TEXT NOT NULL,
            receipt_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            decision_id TEXT,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            previous_hash TEXT NOT NULL,
            event_hash TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS idempotency (
            idempotency_key TEXT PRIMARY KEY,
            decision_id TEXT NOT NULL,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS benchmarks (
            id TEXT PRIMARY KEY,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)
        now = datetime.now(timezone.utc).isoformat()
        seeds = [
            ("C-1042", "Nadia El Amrani", "Premium", 150.0, 1, 1, 0, 1),
            ("C-1043", "Youssef Bennani", "Standard", 75.0, 0, 0, 0, 1),
            ("C-2099", "Concurrency Test Customer", "Premium", 150.0, 1, 0, 0, 2),
        ]
        for row in seeds:
            conn.execute("""
                INSERT OR IGNORE INTO customers
                (id,name,segment,remaining_budget_mad,marketing_consent,open_critical_case,
                 communications_last_24h,max_communications_per_24h,state_version,updated_at)
                VALUES (?,?,?,?,?,?,?,?,1,?)
            """, (*row, now))


def row_to_customer(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    data["marketing_consent"] = bool(data["marketing_consent"])
    data["open_critical_case"] = bool(data["open_critical_case"])
    return data


def get_customer(customer_id: str) -> dict[str, Any] | None:
    conn = connect()
    try:
        return row_to_customer(conn.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone())
    finally:
        conn.close()


def get_overview() -> dict[str, Any]:
    conn = connect()
    try:
        customers = [row_to_customer(r) for r in conn.execute("SELECT * FROM customers ORDER BY id")]
        decisions = [dict(r) for r in conn.execute("SELECT id,scenario_id,customer_id,status,receipt_hash,created_at FROM decisions ORDER BY created_at DESC LIMIT 8")]
        counts = conn.execute("SELECT COUNT(*) AS total FROM decisions").fetchone()["total"]
        event_count = conn.execute("SELECT COUNT(*) AS total FROM events").fetchone()["total"]
        return {"customers": customers, "recent_decisions": decisions, "decision_count": counts, "event_count": event_count}
    finally:
        conn.close()


def append_event(
    conn: sqlite3.Connection,
    event_type: str,
    payload: dict[str, Any],
    decision_id: str | None = None,
) -> dict[str, Any]:
    previous = conn.execute("SELECT event_hash FROM events ORDER BY id DESC LIMIT 1").fetchone()
    previous_hash = previous["event_hash"] if previous else "GENESIS"
    created_at = datetime.now(timezone.utc).isoformat()
    payload_json = canonical_json(payload)
    digest_input = "|".join([previous_hash, event_type, payload_json, created_at])
    event_hash = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()
    conn.execute(
        "INSERT INTO events(decision_id,event_type,payload_json,previous_hash,event_hash,created_at) VALUES(?,?,?,?,?,?)",
        (decision_id, event_type, payload_json, previous_hash, event_hash, created_at),
    )
    return {"event_type": event_type, "previous_hash": previous_hash, "event_hash": event_hash, "created_at": created_at}


def create_decision(
    scenario_id: str,
    customer_id: str,
    decision: dict[str, Any],
    *,
    commit_actions: bool = True,
) -> dict[str, Any]:
    decision_id = "DEC-" + uuid.uuid4().hex[:10].upper()
    created_at = datetime.now(timezone.utc).isoformat()
    with transaction(immediate=True) as conn:
        row = conn.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
        if row is None:
            raise ValueError(f"Unknown customer: {customer_id}")
        customer = row_to_customer(row)
        from models import DecisionContract
        from engine import build_decision

        proposals = [DecisionContract.model_validate(p) for p in decision["proposals"]]
        # Idempotency is checked while holding the same write lock as the commit.
        for proposal in proposals:
            replay = conn.execute(
                "SELECT decision_id FROM idempotency WHERE idempotency_key=?",
                (proposal.idempotency_key,),
            ).fetchone()
            if replay:
                raise sqlite3.IntegrityError(
                    f"IDEMPOTENCY_REPLAY: proposal {proposal.proposal_id} was already processed in {replay['decision_id']}"
                )

        stale = [
            p.proposal_id for p in proposals
            if p.expected_state_version is not None and p.expected_state_version != customer["state_version"]
        ]
        fresh = build_decision(scenario_id, customer, proposals)
        fresh["state_revalidation"] = {
            "snapshot_version": customer["state_version"],
            "stale_proposals_revalidated": stale,
            "revalidated": bool(stale),
            "detail": "Stale proposals were re-evaluated against the latest locked customer state before any commit." if stale else "All proposals referenced the current customer state version.",
        }

        if not fresh["verification"]["passed"]:
            fresh["status"] = "halted"
        if commit_actions and fresh["status"] == "verified" and fresh["plan"]["selected"]:
            total = fresh["plan"]["total_compensation_mad"]
            outbound = fresh["plan"]["outbound_actions"]
            updated = conn.execute("""
                UPDATE customers
                SET remaining_budget_mad=remaining_budget_mad-?,
                    communications_last_24h=communications_last_24h+?,
                    state_version=state_version+1,
                    updated_at=?
                WHERE id=? AND remaining_budget_mad>=?
                  AND communications_last_24h+?<=max_communications_per_24h
                  AND state_version=?
            """, (total, outbound, created_at, customer_id, total, outbound, customer["state_version"]))
            if updated.rowcount != 1:
                raise sqlite3.OperationalError("STATE_CHANGED_DURING_COMMIT: retry against a fresh customer snapshot")
            fresh["status"] = "committed"
            fresh["state_version_after"] = customer["state_version"] + 1
        else:
            if fresh["status"] != "awaiting_human":
                if fresh["verification"]["passed"] and not fresh["plan"]["selected"]:
                    fresh["status"] = "no_action"
                else:
                    fresh["status"] = "verified" if fresh["verification"]["passed"] else "halted"
            fresh["state_version_after"] = customer["state_version"]

        fresh["decision_id"] = decision_id
        fresh["created_at"] = created_at
        receipt_payload = {
            "decision_id": decision_id,
            "scenario_id": scenario_id,
            "customer_id": customer_id,
            "status": fresh["status"],
            "policy_version": fresh["policy_version"],
            "engine_version": fresh["engine_version"],
            "state_version_before": customer["state_version"],
            "state_version_after": fresh["state_version_after"],
            "stale_proposals_revalidated": stale,
            "verification": fresh["verification"],
            "outcomes": fresh["plan"]["outcomes"],
            "total_compensation_mad": fresh["plan"]["total_compensation_mad"],
            "created_at": created_at,
        }
        previous = conn.execute("SELECT event_hash FROM events ORDER BY id DESC LIMIT 1").fetchone()
        previous_hash = previous["event_hash"] if previous else "GENESIS"
        receipt_hash = hashlib.sha256((previous_hash + canonical_json(receipt_payload)).encode("utf-8")).hexdigest()
        receipt = {**receipt_payload, "previous_event_hash": previous_hash, "receipt_hash": receipt_hash}
        fresh["receipt"] = receipt
        conn.execute("""
            INSERT INTO decisions(id,scenario_id,customer_id,status,decision_json,receipt_json,receipt_hash,created_at)
            VALUES(?,?,?,?,?,?,?,?)
        """, (decision_id, scenario_id, customer_id, fresh["status"], canonical_json(fresh), canonical_json(receipt), receipt_hash, created_at))
        append_event(conn, "decision.prepared", {
            "decision_id": decision_id, "customer_id": customer_id,
            "proposals": len(proposals), "receipt_hash": receipt_hash,
        }, decision_id)
        append_event(conn, "decision.verified", {
            "decision_id": decision_id, "passed": fresh["verification"]["passed"],
            "checks": fresh["verification"]["checks"],
        }, decision_id)
        if fresh["status"] == "committed":
            append_event(conn, "decision.committed", {
                "decision_id": decision_id,
                "compensation_mad": fresh["plan"]["total_compensation_mad"],
                "outbound_actions": fresh["plan"]["outbound_actions"],
                "state_version_after": fresh["state_version_after"],
            }, decision_id)
        elif fresh["status"] == "no_action":
            append_event(conn, "decision.noop", {"decision_id": decision_id, "reason": "No feasible action was selected"}, decision_id)
        else:
            append_event(conn, "decision.halted", {"decision_id": decision_id, "status": fresh["status"]}, decision_id)

        outcomes = {x["proposal_id"]: x for x in fresh["plan"]["outcomes"]}
        for proposal in proposals:
            conn.execute(
                "INSERT INTO idempotency(idempotency_key,decision_id,result_json,created_at) VALUES(?,?,?,?)",
                (proposal.idempotency_key, decision_id, canonical_json(outcomes[proposal.proposal_id]), created_at),
            )
        return fresh


def reset_demo() -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    with transaction(immediate=True) as conn:
        conn.execute("""
            UPDATE customers SET remaining_budget_mad=150, marketing_consent=1,
            open_critical_case=1, communications_last_24h=0,
            max_communications_per_24h=1, state_version=state_version+1, updated_at=?
            WHERE id='C-1042'
        """, (now,))
        conn.execute("""
            UPDATE customers SET remaining_budget_mad=75, marketing_consent=0,
            open_critical_case=0, communications_last_24h=0,
            max_communications_per_24h=1, state_version=state_version+1, updated_at=?
            WHERE id='C-1043'
        """, (now,))
        conn.execute("""
            UPDATE customers SET remaining_budget_mad=150, marketing_consent=1,
            open_critical_case=0, communications_last_24h=0,
            max_communications_per_24h=2, state_version=state_version+1, updated_at=?
            WHERE id='C-2099'
        """, (now,))
        append_event(conn, "demo.reset", {"customer_ids": ["C-1042", "C-1043", "C-2099"]})
    return {"reset": True, "customers": [get_customer("C-1042"), get_customer("C-1043"), get_customer("C-2099")]}


def list_decisions(limit: int = 30) -> list[dict[str, Any]]:
    conn = connect()
    try:
        rows = conn.execute("SELECT decision_json FROM decisions ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [json.loads(row["decision_json"]) for row in rows]
    finally:
        conn.close()


def get_decision(decision_id: str) -> dict[str, Any] | None:
    conn = connect()
    try:
        row = conn.execute("SELECT decision_json FROM decisions WHERE id=?", (decision_id,)).fetchone()
        return json.loads(row["decision_json"]) if row else None
    finally:
        conn.close()


def list_events(limit: int = 50) -> list[dict[str, Any]]:
    conn = connect()
    try:
        rows = conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        output = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            output.append(item)
        return output
    finally:
        conn.close()


def verify_event_chain() -> dict[str, Any]:
    conn = connect()
    try:
        rows = conn.execute("SELECT * FROM events ORDER BY id ASC").fetchall()
        previous = "GENESIS"
        verified = 0
        failures = []
        for row in rows:
            payload = row["payload_json"]
            digest_input = "|".join([previous, row["event_type"], payload, row["created_at"]])
            expected = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()
            if row["previous_hash"] != previous or row["event_hash"] != expected:
                failures.append({"event_id": row["id"], "expected_previous": previous, "stored_previous": row["previous_hash"]})
                break
            previous = row["event_hash"]
            verified += 1
        return {"valid": not failures, "events_verified": verified, "event_count": len(rows), "failures": failures, "head_hash": previous}
    finally:
        conn.close()


def save_benchmark(result: dict[str, Any]) -> dict[str, Any]:
    benchmark_id = "BENCH-" + uuid.uuid4().hex[:10].upper()
    created_at = datetime.now(timezone.utc).isoformat()
    with transaction(immediate=True) as conn:
        conn.execute("INSERT INTO benchmarks(id,result_json,created_at) VALUES(?,?,?)", (benchmark_id, canonical_json(result), created_at))
        append_event(conn, "benchmark.completed", {"benchmark_id": benchmark_id, "cases": result["cases"], "baseline_violations": result["baseline"]["invariant_violations"], "treatyai_violations": result["treatyai"]["invariant_violations"]})
    return {"benchmark_id": benchmark_id, **result}


def latest_benchmark() -> dict[str, Any] | None:
    conn = connect()
    try:
        row = conn.execute("SELECT id,result_json,created_at FROM benchmarks ORDER BY created_at DESC LIMIT 1").fetchone()
        if not row:
            return None
        return {"benchmark_id": row["id"], **json.loads(row["result_json"]), "created_at": row["created_at"]}
    finally:
        conn.close()


def verify_receipt(decision_id: str) -> dict[str, Any] | None:
    conn = connect()
    try:
        row = conn.execute(
            "SELECT receipt_json,receipt_hash FROM decisions WHERE id=?",
            (decision_id,),
        ).fetchone()
        if row is None:
            return None
        receipt = json.loads(row["receipt_json"])
        previous_hash = receipt.get("previous_event_hash", "")
        stored_hash = receipt.get("receipt_hash", "")
        payload = {
            key: value for key, value in receipt.items()
            if key not in ("previous_event_hash", "receipt_hash")
        }
        expected_hash = hashlib.sha256(
            (previous_hash + canonical_json(payload)).encode("utf-8")
        ).hexdigest()
        prepared = conn.execute(
            "SELECT payload_json FROM events WHERE decision_id=? AND event_type='decision.prepared' ORDER BY id LIMIT 1",
            (decision_id,),
        ).fetchone()
        anchored_hash = json.loads(prepared["payload_json"]).get("receipt_hash") if prepared else None
    finally:
        conn.close()
    chain = verify_event_chain()
    valid = (
        stored_hash == expected_hash
        and row["receipt_hash"] == stored_hash
        and anchored_hash == stored_hash
        and chain["valid"]
    )
    return {
        "decision_id": decision_id,
        "valid": valid,
        "receipt_hash": stored_hash,
        "computed_hash": expected_hash,
        "anchored_in_event_chain": anchored_hash == stored_hash,
        "event_chain_valid": chain["valid"],
        "events_verified": chain["events_verified"],
    }
