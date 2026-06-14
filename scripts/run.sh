#!/usr/bin/env bash
# book_agent 실행 스크립트
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# .env 로드
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

export OLLAMA_API_BASE="${OLLAMA_API_BASE:-http://localhost:11434}"
export PYTHONPATH="${REPO_ROOT}:${PYTHONPATH:-}"

MODE="${1:-web}"

case "$MODE" in
  web)
    echo "ADK Web UI 시작 (gemma4:26b + book_agent)"
    echo "  OLLAMA_API_BASE=$OLLAMA_API_BASE"
    echo "  ASSISTANT_API_BASE=${ASSISTANT_API_BASE:-http://bigsoft.iptime.org:10200/api}"
    adk web book_agent
    ;;
  run)
    shift || true
    adk run book_agent "$@"
    ;;
  api)
    adk api_server book_agent
    ;;
  *)
    echo "Usage: $0 {web|run|api}"
    exit 1
    ;;
esac
