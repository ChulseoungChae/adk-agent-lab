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
ollama_utils = importlib.import_module(f"{AGENT_PKG}.ollama_utils")
gpu_report_mod = importlib.import_module(f"{AGENT_PKG}.gpu_report")

COMPARE_MODELS = config.COMPARE_MODELS
LOG_PATH = config.LOG_PATH
OUTPUT_ROOT = config.OUTPUT_ROOT
GPU_CSV_PATH = config.GPU_CSV_PATH
GPU_SUMMARY_LOG_PATH = config.GPU_SUMMARY_LOG_PATH
GPU_MONITOR_ENABLED = config.GPU_MONITOR_ENABLED
GPU_MONITOR_INTERVAL_SEC = config.GPU_MONITOR_INTERVAL_SEC
LITELLM_TIMEOUT_SEC = config.LITELLM_TIMEOUT_SEC
MODEL_RUN_MAX_RETRIES = config.MODEL_RUN_MAX_RETRIES
ADK_MAX_ROUNDS = config.ADK_MAX_ROUNDS
COMPARE_CHAPTER_MIN = config.COMPARE_CHAPTER_MIN
COMPARE_CHAPTER_MAX = config.COMPARE_CHAPTER_MAX
prepare_for_model = ollama_utils.prepare_for_model
unload_all_models = ollama_utils.unload_all_models
GpuMonitor = gpu_monitor_mod.GpuMonitor
model_slug = config.model_slug
output_dir_for_model = config.output_dir_for_model
sync_results = book_tools.sync_results
log_event = session_log.log_event
log_session_start = session_log.log_session_start
log_session_end = session_log.log_session_end
AUTO_SYNC_RESULTS = config.AUTO_SYNC_RESULTS

AUTO_PROMPT = f"""
http://bigsoft.iptime.org:10200/ 반도체 AI 어시스턴트 플랫폼의 기능
(실시간 이상감지, 과거 공정 이력, 공정 결과 추론, 문서/RAG, 리포트)을
반도체 공정 엔지니어 대상 **한국어** 기술서로 집필하세요.

요구사항:
- **모든 결과물(제목, 목차, 챕터 본문)은 반드시 한국어로 작성**하세요. 영어 본문 금지.
- 중간에 사용자에게 질문하지 말고, 도구를 사용해 처음부터 끝까지 완료하세요.
- 플랫폼 API 도구로 실제 데이터를 조사·인용하세요.
- save_book_metadata → save_outline({COMPARE_CHAPTER_MIN}~{COMPARE_CHAPTER_MAX}장) → write_chapter(전 챕터) 순으로 저장하세요.
- **모델 비교용**이므로 챕터당 800~1500자로 간결하게 작성하세요. 너무 길게 쓰지 마세요.
- 완료 후 read_book_state로 결과를 확인하세요.
""".strip()

SUMMARY_PATH = OUTPUT_ROOT / "comparison_summary.json"
OUTPUT_README_PATH = config.OUTPUT_README_PATH
generate_output_readme = gpu_report_mod.generate_output_readme


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
    env["LITELLM_REQUEST_TIMEOUT"] = str(LITELLM_TIMEOUT_SEC)
    env["PYTHONIOENCODING"] = "utf-8"
    env.setdefault("LC_ALL", "C.UTF-8")
    env.setdefault("LANG", "C.UTF-8")
    return env


def _run_adk(model: str, extra_args: list[str] | None = None) -> None:
    cmd = ["adk", "run", AGENT_PKG]
    if extra_args:
        cmd.extend(extra_args)
    subprocess.run(cmd, check=True, env=_adk_env(model), cwd=str(PROJECT_DIR))


def _book_progress(model: str) -> dict:
    out_dir = output_dir_for_model(model)
    outline_path = out_dir / "outline.json"
    chapters_dir = out_dir / "chapters"

    expected: list[int] = []
    if outline_path.exists():
        outline = json.loads(outline_path.read_text(encoding="utf-8"))
        for chapter in outline.get("chapters", []):
            number = chapter.get("number") or chapter.get("chapter_number")
            if number is not None:
                expected.append(int(number))

    written_nums: set[int] = set()
    if chapters_dir.is_dir():
        for chapter_file in chapters_dir.glob("*.md"):
            prefix = chapter_file.name.split("_", 1)[0]
            try:
                written_nums.add(int(prefix))
            except ValueError:
                continue

    missing = [number for number in sorted(expected) if number not in written_nums]
    return {
        "expected_count": len(expected),
        "written_count": len(written_nums),
        "missing": missing,
        "complete": bool(expected) and not missing,
    }


def _prompt_for_round(model: str, round_num: int) -> str:
    progress = _book_progress(model)
    if round_num == 1 and progress["expected_count"] == 0 and progress["written_count"] == 0:
        return AUTO_PROMPT

    if progress["missing"]:
        missing = ", ".join(str(number) for number in progress["missing"])
        return f"""
read_book_state로 현재 책 상태를 확인하세요.

outline.json에 있는 **미작성 챕터({missing}번)**를 write_chapter로 **한국어** Markdown 저장하세요.
- 이미 저장된 메타데이터·목차는 다시 저장하지 마세요.
- 한 턴에 write_chapter를 여러 번 연속 호출해도 됩니다.
- 챕터당 800~1500자로 간결하게 작성하세요.
- 사용자에게 질문하지 말고 도구만 사용해 전 챕터 저장까지 완료하세요.
- 완료 후 read_book_state로 확인하세요.
""".strip()

    if progress["expected_count"] == 0:
        return AUTO_PROMPT

    return """
read_book_state로 확인하세요. outline은 있으나 챕터가 비어 있습니다.
outline의 모든 챕터를 write_chapter로 **한국어** 저장하세요. 질문하지 마세요.
""".strip()


def _run_adk_until_complete(model: str) -> None:
    for round_num in range(1, ADK_MAX_ROUNDS + 1):
        progress = _book_progress(model)
        if progress["complete"]:
            log_event(
                f"BOOK DONE | model={model} | chapters={progress['written_count']}/{progress['expected_count']}"
            )
            return

        prompt = _prompt_for_round(model, round_num)
        log_event(
            f"ADK ROUND | model={model} | round={round_num}/{ADK_MAX_ROUNDS} "
            f"| written={progress['written_count']}/{progress['expected_count'] or '?'}"
        )
        _run_adk(model, [prompt])

    progress = _book_progress(model)
    if not progress["complete"]:
        log_event(
            f"BOOK INCOMPLETE | model={model} | "
            f"chapters={progress['written_count']}/{progress['expected_count']}",
            level=logging.WARNING,
        )


def _resolve_status(model: str, subprocess_failed: bool) -> str:
    if subprocess_failed:
        return "failed"
    progress = _book_progress(model)
    if progress["complete"]:
        return "ok"
    if progress["expected_count"] or progress["written_count"]:
        return "partial"
    return "failed"


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


def _load_book_results_for_report() -> list[dict]:
    if not SUMMARY_PATH.exists():
        return []
    data = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    models = data.get("models", [])
    return models if isinstance(models, list) else []


def _write_output_readme(results: list[dict]) -> None:
    generate_output_readme(
        csv_path=GPU_CSV_PATH,
        readme_path=OUTPUT_README_PATH,
        models=COMPARE_MODELS,
        book_results=results,
        summary_path=SUMMARY_PATH,
    )
    log_event(f"REPORT   | saved {OUTPUT_README_PATH}")


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
    subprocess_failed = False
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
        last_error: subprocess.CalledProcessError | None = None
        for attempt in range(1, MODEL_RUN_MAX_RETRIES + 1):
            prepare_for_model(model)
            try:
                _run_adk_until_complete(model)
                last_error = None
                break
            except subprocess.CalledProcessError as exc:
                last_error = exc
                subprocess_failed = True
                log_event(
                    f"RUN FAIL | model={model} | attempt={attempt}/{MODEL_RUN_MAX_RETRIES} | code={exc.returncode}",
                    level=logging.ERROR,
                )
                unload_all_models()
        if last_error is not None:
            raise last_error
    except subprocess.CalledProcessError as exc:
        subprocess_failed = True
        log_event(f"RUN FAIL | model={model} | code={exc.returncode}", level=logging.ERROR)
    finally:
        unload_all_models(delay_sec=0)
        gpu_stats = monitor.stop()
        elapsed = time.time() - started
        status = _resolve_status(model, subprocess_failed)
        progress = _book_progress(model)
        end_meta: dict[str, str] = {
            "model": model,
            "status": status,
            "output": str(out_dir),
            "chapters": f"{progress['written_count']}/{progress['expected_count']}",
        }
        if gpu_stats and gpu_stats.get("sample_count", 0) > 0:
            agg = gpu_stats.get("aggregate", {}).get("total_gpu_util_pct", {})
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
    _write_output_readme(results)
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

    if arg == "report":
        _write_output_readme(_load_book_results_for_report())
        print(f"Generated {OUTPUT_README_PATH}")
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
        "Usage: run.py [compare|single|chat|sync|report]\n"
        "  compare (default) — 4개 모델 순차 집필\n"
        "  single            — OLLAMA_MODEL 1개만 집필\n"
        "  report            — gpu_usage.csv로 output/README.md 재생성",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
