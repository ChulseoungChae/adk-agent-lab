#!/usr/bin/env python3
"""data_statistics — CSV 통계 분석 ADK 에이전트 (단일·4모델 비교).

사용법:
  python3 run.py              # 4개 모델 순차 분석 (기본)
  python3 run.py compare      # 위와 동일
  python3 run.py single       # OLLAMA_MODEL 1개만
  python3 run.py tools        # Tool만 로컬 테스트 (LLM 없음)
  python3 run.py report       # comparison_summary로 output/README 재생성
  python3 run.py sync         # output/ Git 커밋+push
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
AGENT_PKG = AGENT_DIR.name

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

config = importlib.import_module(f"{AGENT_PKG}.config")
session_log = importlib.import_module(f"{AGENT_PKG}.session_log")
data_tools = importlib.import_module(f"{AGENT_PKG}.data_tools")
report_tools = importlib.import_module(f"{AGENT_PKG}.report_tools")
ollama_utils = importlib.import_module(f"{AGENT_PKG}.ollama_utils")
gpu_monitor_mod = importlib.import_module(f"{AGENT_PKG}.gpu_monitor")
validator_mod = importlib.import_module(f"{AGENT_PKG}.analysis_validator")
compare_report_mod = importlib.import_module(f"{AGENT_PKG}.compare_report")

COMPARE_MODELS = config.COMPARE_MODELS
DEFAULT_DATA_PATH = config.DEFAULT_DATA_PATH
LOG_PATH = config.LOG_PATH
OUTPUT_ROOT = config.OUTPUT_ROOT
GPU_CSV_PATH = config.GPU_CSV_PATH
GPU_SUMMARY_LOG_PATH = config.GPU_SUMMARY_LOG_PATH
GPU_MONITOR_ENABLED = config.GPU_MONITOR_ENABLED
GPU_MONITOR_INTERVAL_SEC = config.GPU_MONITOR_INTERVAL_SEC
LITELLM_TIMEOUT_SEC = config.LITELLM_TIMEOUT_SEC
MODEL_RUN_MAX_RETRIES = config.MODEL_RUN_MAX_RETRIES
ADK_MAX_ROUNDS = config.ADK_MAX_ROUNDS
COMPARISON_SUMMARY_PATH = config.COMPARISON_SUMMARY_PATH
OUTPUT_README_PATH = config.OUTPUT_README_PATH
COMPARE_CHARTS_DIR = config.COMPARE_CHARTS_DIR
prepare_for_model = ollama_utils.prepare_for_model
unload_all_models = ollama_utils.unload_all_models
GpuMonitor = gpu_monitor_mod.GpuMonitor
model_slug = config.model_slug
output_dir_for_model = config.output_dir_for_model
validate_analysis_output = validator_mod.validate_analysis_output
save_validation = validator_mod.save_validation
reinforcement_prompt = validator_mod.reinforcement_prompt
generate_output_readme = compare_report_mod.generate_output_readme
sync_output_root = report_tools.sync_output_root
log_event = session_log.log_event
log_session_start = session_log.log_session_start
log_session_end = session_log.log_session_end
AUTO_SYNC_RESULTS = config.AUTO_SYNC_RESULTS

AUTO_PROMPT = f"""
`{DEFAULT_DATA_PATH.name}` 데이터를 로드해 통계 분석을 수행하세요.

요구사항:
- load_data → profile_data → 적절한 통계 Tool들 → generate_charts → save_analysis_report 순으로 완료
- **모든 숫자는 Tool 반환값만** 사용하세요. 임의 통계 금지.
- 리포트는 한국어로 작성하세요. findings 3개 이상.
- validate_analysis로 검증하고, 미완료면 보강 후 다시 검증하세요.
- 중간에 사용자에게 질문하지 마세요.
- 완료 후 read_analysis_state로 확인하세요.
""".strip()


def _adk_env(model: str) -> dict[str, str]:
    slug = model_slug(model)
    env = os.environ.copy()
    env.setdefault("OLLAMA_API_BASE", "http://localhost:11434")
    env["OLLAMA_MODEL"] = model
    env["STATS_OUTPUT_SUBDIR"] = slug
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


def _analysis_progress(model: str) -> dict:
    out_dir = output_dir_for_model(model)
    validation = validate_analysis_output(out_dir)
    return {
        "complete": validation.get("complete", False),
        "score": validation.get("score", 0),
        "validation": validation,
    }


def _prompt_for_round(model: str, round_num: int) -> str:
    progress = _analysis_progress(model)
    if progress["complete"]:
        return ""
    if round_num == 1:
        return AUTO_PROMPT
    return reinforcement_prompt(progress["validation"])


def _run_adk_until_complete(model: str) -> None:
    for round_num in range(1, ADK_MAX_ROUNDS + 1):
        progress = _analysis_progress(model)
        if progress["complete"]:
            log_event(
                f"STATS DONE | model={model} | score={progress['score']}%"
            )
            return

        prompt = _prompt_for_round(model, round_num)
        if not prompt:
            return

        log_event(
            f"ADK ROUND | model={model} | round={round_num}/{ADK_MAX_ROUNDS} "
            f"| score={progress['score']}%"
        )
        _run_adk(model, [prompt])

    progress = _analysis_progress(model)
    if not progress["complete"]:
        log_event(
            f"STATS INCOMPLETE | model={model} | score={progress['score']}%",
            level=logging.WARNING,
        )


def _resolve_status(model: str, subprocess_failed: bool) -> str:
    if subprocess_failed:
        return "failed"
    progress = _analysis_progress(model)
    if progress["complete"]:
        return "ok"
    out_dir = output_dir_for_model(model)
    if out_dir.joinpath("profile.json").exists() or out_dir.joinpath("report.md").exists():
        return "partial"
    return "failed"


def _annotate_model_result(model: str, elapsed: float, status: str) -> dict:
    out_dir = output_dir_for_model(model)
    out_dir.mkdir(parents=True, exist_ok=True)
    validation = validate_analysis_output(out_dir)
    save_validation(out_dir, validation)
    metrics = validation.get("metrics", {})

    meta_path = out_dir / "analysis_metadata.json"
    meta: dict = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))

    meta.update(
        {
            "model": model,
            "elapsed_seconds": round(elapsed, 1),
            "status": status,
            "validation_score": validation.get("score"),
            "validation_complete": validation.get("complete"),
            "finished_at": datetime.now().isoformat(),
        }
    )
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "model": model,
        "slug": model_slug(model),
        "output_dir": str(out_dir),
        "title": meta.get("title", ""),
        "elapsed_seconds": round(elapsed, 1),
        "status": status,
        "validation_score": validation.get("score"),
        "validation_complete": validation.get("complete"),
        "statistics_run_count": metrics.get("statistics_run_count", 0),
        "findings_count": metrics.get("findings_count", 0),
        "chart_count": metrics.get("chart_count", 0),
        "validation": validation,
        "finished_at": datetime.now().isoformat(),
    }


def _write_comparison_summary(results: list[dict]) -> None:
    summary = {"updated_at": datetime.now().isoformat(), "models": results}
    COMPARISON_SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log_event(f"SUMMARY  | saved {COMPARISON_SUMMARY_PATH}")


def _load_results_for_report() -> list[dict]:
    if not COMPARISON_SUMMARY_PATH.exists():
        return []
    data = json.loads(COMPARISON_SUMMARY_PATH.read_text(encoding="utf-8"))
    models = data.get("models", [])
    return models if isinstance(models, list) else []


def _write_output_readme(results: list[dict]) -> None:
    generate_output_readme(
        readme_path=OUTPUT_README_PATH,
        models=COMPARE_MODELS,
        results=results,
        charts_dir=COMPARE_CHARTS_DIR,
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
        "data": str(DEFAULT_DATA_PATH),
        "output": str(out_dir),
        "log": str(LOG_PATH),
    }
    if index is not None and total is not None:
        meta["progress"] = f"{index}/{total}"

    log_session_start(**meta)
    log_event(f"PROMPT | {AUTO_PROMPT[:120]}...")
    started = time.time()
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
        progress = _analysis_progress(model)
        end_meta: dict[str, str] = {
            "model": model,
            "status": status,
            "output": str(out_dir),
            "validation_score": f"{progress['score']}%",
        }
        if gpu_stats and gpu_stats.get("sample_count", 0) > 0:
            agg = gpu_stats.get("aggregate", {}).get("total_gpu_util_pct", {})
            end_meta["gpu_util_avg"] = f"{agg.get('avg', 0)}%"
        log_session_end(**end_meta)
        result = _annotate_model_result(model, elapsed, status)
        if gpu_stats:
            result["gpu_stats"] = gpu_stats
        return result


def _run_compare_all() -> None:
    log_session_start(
        mode="compare_batch",
        models=",".join(COMPARE_MODELS),
        data=str(DEFAULT_DATA_PATH),
        log=str(LOG_PATH),
    )
    batch_started = time.time()
    results: list[dict] = []

    for index, model in enumerate(COMPARE_MODELS, start=1):
        log_event(f"COMPARE | start model {index}/{len(COMPARE_MODELS)}: {model}")
        results.append(_run_single_model(model, index=index, total=len(COMPARE_MODELS)))
        log_event(
            f"COMPARE | done model {index}/{len(COMPARE_MODELS)}: {model} "
            f"| status={results[-1]['status']} "
            f"| score={results[-1]['validation_score']}% "
            f"| elapsed={results[-1]['elapsed_seconds']}s"
        )

    _write_comparison_summary(results)
    _write_output_readme(results)
    log_session_end(
        mode="compare_batch",
        models=len(COMPARE_MODELS),
        elapsed=f"{time.time() - batch_started:.1f}s",
    )
    if AUTO_SYNC_RESULTS:
        sync_output_root("Update stats model comparison")


def _run_tools_smoke_test() -> None:
    """LLM 없이 Tool + 검증 파이프라인 테스트."""
    load_data = data_tools.load_data
    profile_data = data_tools.profile_data
    run_descriptive_stats = report_tools.run_descriptive_stats
    run_correlation = report_tools.run_correlation
    run_groupby_stats = report_tools.run_groupby_stats
    run_categorical_summary = report_tools.run_categorical_summary
    detect_outliers = report_tools.detect_outliers
    generate_charts = report_tools.generate_charts
    save_analysis_report = report_tools.save_analysis_report
    validate_analysis = report_tools.validate_analysis
    read_analysis_state = report_tools.read_analysis_state

    print("=== Tool smoke test ===")
    loaded = load_data()
    profile = profile_data()
    numeric = profile.get("numeric_columns", [])
    categorical = profile.get("categorical_columns", [])

    run_descriptive_stats(numeric[:5] or None)
    if len(numeric) >= 2:
        run_correlation(numeric[:6])
    if categorical and numeric:
        run_groupby_stats(categorical[0], numeric[:2], "mean")
    if categorical:
        run_categorical_summary(categorical[:2])
    if numeric:
        detect_outliers(numeric[0])
    generate_charts(numeric[:3] or None)
    save_analysis_report(
        title="샘플 센서 데이터 통계 분석 (Tool 테스트)",
        summary="Tool smoke test로 생성된 리포트입니다.",
        findings=[
            f"행 수: {loaded['row_count']}, 열 수: {loaded['column_count']}",
            f"수치형 컬럼: {', '.join(numeric) or '없음'}",
            f"분석 힌트: {', '.join(profile.get('analysis_hints', []))}",
        ],
    )
    validation = validate_analysis()
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    print(json.dumps(read_analysis_state(), ensure_ascii=False, indent=2))
    print("=== Done ===")


def main() -> None:
    os.chdir(PROJECT_DIR)
    arg = sys.argv[1] if len(sys.argv) > 1 else "compare"

    if arg == "sync":
        msg = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "Update stats output"
        result = sync_output_root(msg)
        print(result.get("push_stdout") or result.get("stdout") or result.get("message") or result)
        return

    if arg == "tools":
        _run_tools_smoke_test()
        return

    if arg == "report":
        _write_output_readme(_load_results_for_report())
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
        log_session_start(mode="chat", model=model)
        try:
            _run_adk(model)
        finally:
            log_session_end(model=model)
        return

    if arg == "run":
        model = os.getenv("OLLAMA_MODEL", COMPARE_MODELS[0])
        extra = sys.argv[2:]
        log_session_start(mode="run", model=model)
        try:
            _run_adk(model, extra or None)
        finally:
            log_session_end(model=model)
        return

    print(
        "Usage: run.py [compare|single|chat|run|sync|report|tools]\n"
        "  compare (default) — 4개 모델 순차 통계 분석\n"
        "  single            — OLLAMA_MODEL 1개만\n"
        "  report            — comparison_summary로 README 재생성",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
