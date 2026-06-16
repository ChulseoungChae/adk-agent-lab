#!/usr/bin/env python3
"""model_compare_book — 여러 Ollama 모델로 순차 집필·성능 비교.

사용법:
  python3 run.py              # 4개 모델 순차 집필 (기본)
  python3 run.py compare      # 위와 동일
  python3 run.py single       # OLLAMA_MODEL 1개만 집필
  python3 run.py sync         # 결과물 GitHub 커밋+push
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = AGENT_DIR.parent
REPO_ROOT = PROJECT_DIR.parent
AGENT_PKG = AGENT_DIR.name

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

config = importlib.import_module(f"{AGENT_PKG}.config")
book_tools = importlib.import_module(f"{AGENT_PKG}.book_tools")
session_log = importlib.import_module(f"{AGENT_PKG}.session_log")
gpu_monitor_mod = importlib.import_module(f"{AGENT_PKG}.gpu_monitor")

COMPARE_MODELS = config.COMPARE_MODELS
LOG_PATH = config.LOG_PATH
OUTPUT_ROOT = config.OUTPUT_ROOT
GPU_CSV_PATH = config.GPU_CSV_PATH
GPU_SUMMARY_LOG_PATH = config.GPU_SUMMARY_LOG_PATH
GPU_MONITOR_ENABLED = config.GPU_MONITOR_ENABLED
GPU_MONITOR_INTERVAL_SEC = config.GPU_MONITOR_INTERVAL_SEC
GpuMonitor = gpu_monitor_mod.GpuMonitor
model_slug = config.model_slug
output_dir_for_model = config.output_dir_for_model
sync_results = book_tools.sync_results
log_event = session_log.log_event
log_session_start = session_log.log_session_start
log_session_end = session_log.log_session_end
AUTO_SYNC_RESULTS = config.AUTO_SYNC_RESULTS

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

SUMMARY_PATH = OUTPUT_ROOT / "comparison_summary.json"


def _adk_env(model: str) -> dict[str, str]:
    slug = model_slug(model)
    env = os.environ.copy()
    env.setdefault("OLLAMA_API_BASE", "http://localhost:11434")
    env["OLLAMA_MODEL"] = model
    env["BOOK_OUTPUT_SUBDIR"] = slug
    # PYTHONPATH에 PROJECT_DIR을 넣으면 ADK가 agent/agent.py를
    # 패키지가 아닌 단일 모듈로 로드해 relative import가 깨집니다.
    # ADK가 agents_dir(PROJECT_DIR)를 sys.path에 직접 추가합니다.
    env.pop("PYTHONPATH", None)
    env["PYTHONIOENCODING"] = "utf-8"
    env.setdefault("LC_ALL", "C.UTF-8")
    env.setdefault("LANG", "C.UTF-8")
    return env


def _run_adk(model: str, extra_args: list[str] | None = None) -> None:
    cmd = ["adk", "run", AGENT_PKG]
    if extra_args:
        cmd.extend(extra_args)
    subprocess.run(cmd, check=True, env=_adk_env(model), cwd=str(PROJECT_DIR))


def _annotate_model_result(model: str, elapsed: float, status: str) -> dict:
    out_dir = output_dir_for_model(model)
    meta_path = out_dir / "book_metadata.json"
    chapter_count = len(list((out_dir / "chapters").glob("*.md"))) if (out_dir / "chapters").is_dir() else 0

    title = ""
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["model"] = model
        meta["elapsed_seconds"] = round(elapsed, 1)
        meta["status"] = status
        meta["finished_at"] = datetime.now().isoformat()
        meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        title = meta.get("title", "")

    return {
        "model": model,
        "slug": model_slug(model),
        "output_dir": str(out_dir),
        "title": title,
        "chapter_count": chapter_count,
        "elapsed_seconds": round(elapsed, 1),
        "status": status,
        "finished_at": datetime.now().isoformat(),
    }


def _write_comparison_summary(results: list[dict]) -> None:
    summary = {
        "updated_at": datetime.now().isoformat(),
        "models": results,
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log_event(f"SUMMARY  | saved {SUMMARY_PATH}")


def _run_single_model(
    model: str,
    *,
    index: int | None = None,
    total: int | None = None,
) -> dict:
    slug = model_slug(model)
    out_dir = output_dir_for_model(model)
    out_dir.mkdir(parents=True, exist_ok=True)

    meta: dict[str, str | int] = {
        "mode": "compare",
        "model": model,
        "output": str(out_dir),
        "log": str(LOG_PATH),
    }
    if index is not None and total is not None:
        meta["progress"] = f"{index}/{total}"

    log_session_start(**meta)
    log_event(f"PROMPT | {AUTO_PROMPT[:120]}...")
    started = time.time()
    status = "ok"
    gpu_stats: dict | None = None

    monitor = GpuMonitor(
        model=model,
        csv_path=GPU_CSV_PATH,
        summary_log_path=GPU_SUMMARY_LOG_PATH,
        interval_sec=GPU_MONITOR_INTERVAL_SEC,
        enabled=GPU_MONITOR_ENABLED,
    )

    try:
        monitor.start()
        _run_adk(model, [AUTO_PROMPT])
    except subprocess.CalledProcessError as exc:
        status = "failed"
        log_event(f"RUN FAIL | model={model} | code={exc.returncode}", level=logging.ERROR)
    finally:
        gpu_stats = monitor.stop()
        elapsed = time.time() - started
        end_meta: dict[str, str] = {
            "model": model,
            "status": status,
            "output": str(out_dir),
        }
        if gpu_stats and gpu_stats.get("sample_count", 0) > 0:
            agg = gpu_stats.get("aggregate", {}).get("gpu_util_pct", {})
            end_meta["gpu_util_avg"] = f"{agg.get('avg', 0)}%"
            end_meta["gpu_util_max"] = f"{agg.get('max', 0)}%"
        log_session_end(**end_meta)
        result = _annotate_model_result(model, elapsed, status)
        if gpu_stats:
            result["gpu_stats"] = gpu_stats
        if AUTO_SYNC_RESULTS:
            sync_results(f"[{model}] Model compare book output")
        return result


def _run_compare_all() -> None:
    log_session_start(
        mode="compare_batch",
        models=",".join(COMPARE_MODELS),
        log=str(LOG_PATH),
    )
    batch_started = time.time()
    results: list[dict] = []

    for index, model in enumerate(COMPARE_MODELS, start=1):
        log_event(f"COMPARE | start model {index}/{len(COMPARE_MODELS)}: {model}")
        results.append(
            _run_single_model(model, index=index, total=len(COMPARE_MODELS))
        )
        log_event(
            f"COMPARE | done model {index}/{len(COMPARE_MODELS)}: {model} "
            f"| status={results[-1]['status']} | elapsed={results[-1]['elapsed_seconds']}s"
        )

    _write_comparison_summary(results)
    log_session_end(
        mode="compare_batch",
        models=len(COMPARE_MODELS),
        elapsed=f"{time.time() - batch_started:.1f}s",
    )
    if AUTO_SYNC_RESULTS:
        sync_results("Update model comparison summary")


def main() -> None:
    os.chdir(PROJECT_DIR)
    arg = sys.argv[1] if len(sys.argv) > 1 else "compare"

    if arg == "sync":
        msg = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "Update model compare output"
        result = sync_results(msg)
        print(result.get("push_stdout") or result.get("stdout") or result.get("message") or result)
        return

    if arg in ("compare", "auto", ""):
        _run_compare_all()
        return

    if arg == "single":
        model = os.getenv("OLLAMA_MODEL", COMPARE_MODELS[0])
        result = _run_single_model(model)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if arg == "chat":
        model = os.getenv("OLLAMA_MODEL", COMPARE_MODELS[0])
        log_session_start(mode="chat", model=model, log=str(LOG_PATH))
        monitor = GpuMonitor(
            model=model,
            csv_path=GPU_CSV_PATH,
            summary_log_path=GPU_SUMMARY_LOG_PATH,
            interval_sec=GPU_MONITOR_INTERVAL_SEC,
            enabled=GPU_MONITOR_ENABLED,
        )
        try:
            monitor.start()
            _run_adk(model)
        finally:
            monitor.stop()
            log_session_end(mode="chat", model=model)
        return

    print(
        "Usage: run.py [compare|single|chat|sync]\n"
        "  compare (default) — 4개 모델 순차 집필\n"
        "  single            — OLLAMA_MODEL 1개만 집필",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
