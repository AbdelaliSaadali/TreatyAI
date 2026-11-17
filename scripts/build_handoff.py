"""Build credential-free TreatyAI source and Salesforce teammate bundles.

Requires only Python's standard library and the already-installed project deps.
It NEVER includes the SQLite database, Git history or any Keychain credential.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import re
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import db
from engine import build_decision, customer_journey_proposals
from main import app
from models import DecisionBatch

RELEASE = "v0.3.0"
HANDOFF = ROOT / "handoff"
SECRET_PATTERN = re.compile(r"gsk_[A-Za-z0-9]{30,}")
OMIT_DIRS = {".git", ".venv", "venv", "__pycache__", "data", ".pytest_cache",
             ".mypy_cache", ".ruff_cache", "node_modules"}
OMIT_SUFFIXES = {".pyc", ".pyo", ".sqlite3", ".db", ".zip", ".log"}
OMIT_NAMES = {".DS_Store", ".env", ".env.local", ".env.production"}


def allowed(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    return (path.is_file()
            and not any(part in OMIT_DIRS for part in relative.parts)
            and path.name not in OMIT_NAMES
            and path.suffix not in OMIT_SUFFIXES
            and not path.is_symlink())


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def generate_contract_examples() -> None:
    HANDOFF.mkdir(exist_ok=True)
    # Generate a valid typed sample without reading the existing demo database.
    sample_proposals = customer_journey_proposals("C-1042", expected_state_version=1)
    batch = {
        "scenario_id": "salesforce-partner-example",
        "customer_id": "C-1042",
        "proposals": [p.public_dict() for p in sample_proposals],
    }
    DecisionBatch.model_validate(batch)
    write_json(HANDOFF / "sample_request.json", batch)

    # Generate an authentic response/receipt using an ISOLATED temporary database.
    original_dir, original_path = db.DATA_DIR, db.DB_PATH
    try:
        with tempfile.TemporaryDirectory(prefix="treatyai-bundle-") as folder:
            db.DATA_DIR = Path(folder)
            db.DB_PATH = Path(folder) / "sample.sqlite3"
            db.init_db()
            customer = db.get_customer("C-1042")
            proposals = customer_journey_proposals("C-1042", customer["state_version"])
            preview = build_decision("salesforce-partner-example", customer, proposals)
            result = db.create_decision("salesforce-partner-example", customer["id"], preview)
            assert result["status"] == "committed"
            assert result["verification"]["passed"]
            assert db.verify_receipt(result["decision_id"])["valid"]
            write_json(HANDOFF / "sample_verified_response.json", result)
    finally:
        db.DATA_DIR, db.DB_PATH = original_dir, original_path

    spec = app.openapi()
    assert "TreatyAIIntegrationBearer" in spec["components"]["securitySchemes"]
    assert "/api/decisions/coordinate" in spec["paths"]
    assert spec["paths"]["/api/decisions/coordinate"]["post"]["security"]
    write_json(HANDOFF / "openapi.json", spec)
    write_json(HANDOFF / "release_manifest.json", {
        "release": RELEASE,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "salesforce_deployed": False,
        "live_groq_verified": False,
        "crm_data": "synthetic-only",
        "exposed_credentials": False,
        "deployment_mode": "local-loopback",
        "integration_auth": "separate bearer token, disabled until configured",
        "external_side_effects": False,
    })


def checked_files() -> list[Path]:
    files = sorted((p for p in ROOT.rglob("*") if allowed(p)),
                   key=lambda p: str(p.relative_to(ROOT)))
    for path in files:
        if path.suffix in {".py", ".js", ".html", ".css", ".md", ".json", ".sh",
                           ".cls", ".xml", ".txt"}:
            content = path.read_text(encoding="utf-8", errors="replace")
            if SECRET_PATTERN.search(content):
                raise RuntimeError("Potential Groq credential detected in source: " + str(path))
    return files


def build_archive(path: Path, entries: list[Path], relative_to: Path) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=8) as target:
        for file in entries:
            target.write(file, arcname=str(file.relative_to(relative_to)))
    with zipfile.ZipFile(path) as check:
        if check.testzip() is not None:
            raise RuntimeError("Archive validation failed: " + str(path))


def main() -> None:
    generate_contract_examples()
    files = checked_files()
    source_archive = ROOT.parent / ("TreatyAI-" + RELEASE + "-source.zip")
    handoff_archive = ROOT.parent / ("TreatyAI-" + RELEASE + "-Salesforce-Handoff.zip")
    build_archive(source_archive, files, ROOT.parent)
    handoff = [file for file in files if (
        "handoff" in file.relative_to(ROOT).parts
        or "salesforce" in file.relative_to(ROOT).parts
        or file.name in ("SALESFORCE_INTEGRATION.md", "ARCHITECTURE.md",
                         "models.py", "verifier.py")
    )]
    build_archive(handoff_archive, handoff, ROOT)
    print("Source archive:", source_archive, "bytes:", source_archive.stat().st_size)
    print("Salesforce handoff:", handoff_archive, "bytes:", handoff_archive.stat().st_size)
    print("Included files:", len(files), "| handoff files:", len(handoff))
    print("Integrity: valid ZIPs, no detectable Groq credentials, no SQLite DB")


if __name__ == "__main__":
    main()
