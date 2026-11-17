"""End-to-end UI smoke test using existing Brave + Playwright (optional).

Starts an isolated local server on a temporary SQLite database; no network APIs,
Groq credentials, Salesforce accounts or existing demo records are touched.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
BRAVE = Path("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser")


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def run():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit("Playwright is optional for UI QA; no installation was performed.") from exc
    if not BRAVE.exists():
        raise SystemExit("Brave browser executable was not found.")

    with tempfile.TemporaryDirectory(prefix="treatyai-ui-") as temp:
        port = free_port()
        base = f"http://127.0.0.1:{port}"
        child_code = (
            "import sys;from pathlib import Path;import db,main,uvicorn;"
            "db.DATA_DIR=Path(sys.argv[1]);db.DB_PATH=db.DATA_DIR/'browser-test.sqlite3';"
            "uvicorn.run(main.app,host='127.0.0.1',port=int(sys.argv[2]),log_level='error')"
        )
        server = subprocess.Popen(
            [sys.executable, "-c", child_code, temp, str(port)],
            cwd=str(ROOT),
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        try:
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError("Isolated test server terminated before startup.")
                try:
                    with urlopen(base + "/api/health", timeout=0.3) as response:
                        if json.load(response)["status"] == "operational":
                            break
                except Exception:
                    time.sleep(0.1)
            else:
                raise RuntimeError("Isolated test server did not become ready.")

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    executable_path=str(BRAVE), headless=True,
                    args=["--no-first-run", "--disable-extensions", "--disable-background-networking"],
                )
                errors = []

                def verify(page, label, expected):
                    page.wait_for_load_state("networkidle")
                    page.wait_for_function(
                        "(needle) => (document.querySelector('h1')?.textContent || '').includes(needle)",
                        arg=expected, timeout=8000,
                    )
                    heading = page.locator("h1").first.inner_text(timeout=8000)
                    assert expected in heading, f"{label} has wrong title: {heading}"
                    overflow = page.evaluate(
                        "() => document.documentElement.scrollWidth - window.innerWidth"
                    )
                    assert overflow < 3, f"{label} overflows viewport by {overflow}px"
                    print("PASS", label, "|", heading)

                desktop = browser.new_page(viewport={"width": 1440, "height": 900})
                desktop.on("pageerror", lambda error: errors.append(str(error)))
                desktop.goto(base, wait_until="networkidle")
                verify(desktop, "Overview / desktop", "Good decisions")

                desktop.locator('.nav-item[data-view="decision"]').click()
                verify(desktop, "Decision room / desktop", "decision room")
                desktop.locator("[data-run-selected]").first.click()
                desktop.locator(".decision-summary").first.wait_for(timeout=10000)
                assert desktop.locator(".verification-row").count() >= 6

                desktop.locator('.nav-item[data-view="receipts"]').click()
                verify(desktop, "Receipts / desktop", "Decision receipts")
                desktop.locator("[data-verify-receipt]").first.click()
                desktop.get_by_text("Receipt hash and audit anchor verified").wait_for(timeout=10000)
                desktop.locator("[data-verify-chain]").click()
                desktop.get_by_text("Audit chain valid", exact=False).wait_for(timeout=10000)

                desktop.locator('.nav-item[data-view="policies"]').click()
                verify(desktop, "Policy registry / desktop", "Rules that")
                assert desktop.locator(".policy-card").count() >= 9

                desktop.locator('.nav-item[data-view="benchmark"]').click()
                desktop.locator("[data-bench-run]").click()
                desktop.locator(".bench-metrics").wait_for(timeout=10000)
                verify(desktop, "TreatyBench / desktop", "Prove the invariant")

                # Build a real offline verified result for the UI mock;
                # AI trace values are deliberately synthetic and clearly tested as mocked.
                from urllib.request import Request
                request = Request(base + "/api/demo/reset", data=b"{}",
                                  headers={"Content-Type":"application/json"}, method="POST")
                with urlopen(request, timeout=8):
                    pass
                request = Request(base + "/api/scenarios/customer-journey/run", data=b"{}",
                                  headers={"Content-Type":"application/json"}, method="POST")
                with urlopen(request, timeout=8) as response:
                    mock_result = json.load(response)
                mock_result["ai_trace"] = {
                    "model_calls": 2,
                    "prompt_tokens": 180,
                    "completion_tokens": 45,
                    "elapsed_ms": 520,
                    "timeline": [
                        {
                            "phase": "specialist_proposal",
                            "agent_id": "service-agent",
                            "agent_name": "Service Agent",
                            "model": "MOCKED-GROQ-20B",
                            "latency_ms": 240,
                            "usage": {"total_tokens": 120},
                            "response": {
                                "decision": "propose",
                                "action_type": "issue_credit",
                                "rationale": "A synthetic model proposes compensation."
                            }
                        },
                        {
                            "phase": "mediation",
                            "agent_id": "mediation-agent",
                            "agent_name": "Mediation Agent",
                            "model": "MOCKED-GROQ-20B",
                            "latency_ms": 280,
                            "usage": {"total_tokens": 105},
                            "response": {
                                "negotiation_rationale": "A synthetic mediator recommends a bounded partial credit."
                            }
                        }
                    ],
                }
                desktop.route("**/api/ai/status", lambda route: route.fulfill(
                    json={
                        "configured": True, "provider": "GroqCloud",
                        "model": "openai/gpt-oss-20b",
                    }
                ))
                desktop.route("**/api/ai/run", lambda route: route.fulfill(json=mock_result))
                desktop.locator('.nav-item[data-view="agents"]').click()
                verify(desktop, "AI Agent Lab / desktop", "AI negotiation lab")
                desktop.locator("[data-ai-run]").click()
                desktop.locator(".ai-timeline-item").first.wait_for(timeout=10000)
                assert desktop.locator(".ai-timeline-item").count() == 2
                assert desktop.get_by_text("MOCKED-GROQ-20B").count() >= 1
                desktop.screenshot(path="/tmp/treatyai-ui-desktop.png", full_page=True)
                print("PASS Mocked Groq UI decision and trace")

                mobile = browser.new_page(
                    viewport={"width": 390, "height": 844},
                    device_scale_factor=1, is_mobile=True, has_touch=True,
                )
                mobile.on("pageerror", lambda error: errors.append(str(error)))
                mobile.goto(base + "/#agents", wait_until="networkidle")
                verify(mobile, "AI Agent Lab / mobile", "AI negotiation lab")
                assert mobile.locator("#groq-key-field").count() == 1
                assert mobile.locator("[data-ai-run]").is_disabled()
                mobile.screenshot(path="/tmp/treatyai-ui-mobile.png", full_page=True)
                mobile.goto(base + "/#decision", wait_until="networkidle")
                verify(mobile, "Decision room / mobile", "decision room")
                mobile.goto(base + "/#benchmark", wait_until="networkidle")
                verify(mobile, "TreatyBench / mobile", "Prove the invariant")

                assert not errors, f"Browser JS errors: {errors}"
                print("PASS No uncaught JavaScript exceptions")
                browser.close()
        finally:
            server.terminate()
            try:
                server.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.communicate()


if __name__ == "__main__":
    run()
