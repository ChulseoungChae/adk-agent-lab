#!/usr/bin/env python3
"""making_a_book — 책 작성 ADK 에이전트 실행 스크립트.

사용법:
  python3 run.py              # 자율 집필 (기본)
  python3 run.py chat         # 대화형 CLI
  python3 run.py web          # Web UI
  python3 run.py sync         # 결과물 GitHub 커밋+push
  python3 run.py run "프롬프트"  # 한 번 실행 후 종료
"""

from __future__ import annotations

import atexit
import importlib
import os
import subprocess
import sys
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = AGENT_DIR.parent
REPO_ROOT = PROJECT_DIR.parent
AGENT_PKG = AGENT_DIR.name

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

book_tools = importlib.import_module(f"{AGENT_PKG}.book_tools")
config = importlib.import_module(f"{AGENT_PKG}.config")
session_log = importlib.import_module(f"{AGENT_PKG}.session_log")

sync_results = book_tools.sync_results
AUTO_SYNC_RESULTS = config.AUTO_SYNC_RESULTS
LOG_PATH = config.LOG_PATH
log_event = session_log.log_event

AUTO_PROMPT = """
http://bigsoft.iptime.org:10200/ 반도체 AI 어시스턴트 플랫폼의 기능
(실시간 이상감지, 과거 공정 이력, 공정 결과 추론, 문서/RAG, 리포트)을
반도체 공정 엔지니어 대상 **한국어** 기술서로 집필하세요.

요구사항:
- **모든 결과물(제목, 목차, 챕터 본문)은 반드시 한국어로 작성**하세요. 영어 본문 금지.
- 중간에 사용자에게 질문하지 말고, 도구를 사용해 처음부터 끝까지 완료하세요.
- 플랫폼 API 도구로 실제 데이터를 조사·인용하세요.
- save_book_metadata → save_outline(8~12장) → write_chapter(전 챕터) 순으로 저장하세요.
- 각 챕터는 한국어로 충실하고 길게 작성하세요.
- 완료 후 read_book_state로 결과를 확인하세요.
""".strip()


def _adk_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("OLLAMA_API_BASE", "http://localhost:11434")
    env["PYTHONPATH"] = str(PROJECT_DIR)
    env["PYTHONIOENCODING"] = "utf-8"
    env.setdefault("LC_ALL", "C.UTF-8")
    env.setdefault("LANG", "C.UTF-8")
    return env


def _on_session_end() -> None:
    log_event("SESSION END")
    if AUTO_SYNC_RESULTS:
        sync_results("Update session log")


def _run_adk(mode: str, extra_args: list[str] | None = None) -> None:
    cmd = ["adk", mode, AGENT_PKG]
    if extra_args:
        cmd.extend(extra_args)
    subprocess.run(cmd, check=True, env=_adk_env(), cwd=str(PROJECT_DIR))


def main() -> None:
    os.chdir(PROJECT_DIR)
    _adk_env()

    arg = sys.argv[1] if len(sys.argv) > 1 else "auto"

    if arg == "sync":
        msg = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "Update book output"
        result = sync_results(msg)
        print(result.get("push_stdout") or result.get("stdout") or result.get("message") or result)
        return

    if arg in ("auto", ""):
        log_event(f"SESSION START | mode=auto | log={LOG_PATH}")
        atexit.register(_on_session_end)
        log_event(f"PROMPT | {AUTO_PROMPT[:120]}...")
        _run_adk("run", [AUTO_PROMPT])
        return

    if arg == "chat":
        log_event(f"SESSION START | mode=chat | log={LOG_PATH}")
        atexit.register(_on_session_end)
        _run_adk("run")
        return

    if arg in ("run", "web", "api"):
        log_event(f"SESSION START | mode={arg} | log={LOG_PATH}")
        atexit.register(_on_session_end)
        extra = sys.argv[2:] if arg == "run" else None
        _run_adk(arg, extra)
        return

    print(
        'Usage: run.py [auto|chat|web|api|sync|run "프롬프트"]',
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
