#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONDONTWRITEBYTECODE=1
PORT="$(printenv TREATYAI_PORT 2>/dev/null || printf '8765')"
echo ""
echo "  TreatyAI — Decision Governance"
echo "  Local workspace: http://127.0.0.1:$PORT"
echo "  API reference:   http://127.0.0.1:$PORT/api/docs"
echo "  Stop with:       Ctrl+C"
echo ""
exec python3 -m uvicorn main:app --host 127.0.0.1 --port "$PORT" --no-access-log
