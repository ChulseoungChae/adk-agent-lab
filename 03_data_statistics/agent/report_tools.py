"""통계 실행·리포트·차트 ADK Tools."""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .config import (
    AUTO_PUSH_RESULTS,
    AUTO_SYNC_RESULTS,
    CHARTS_DIR,
    GIT_REMOTE,
    METADATA_PATH,
    OUTPUT_ROOT,
    PROFILE_PATH,
    REPORT_PATH,
    RESULTS_REPO,
    STATISTICS_PATH,
    VALIDATION_PATH,
)
from .data_tools import get_loaded_dataframe
from .session_log import log_event, log_tool
from . import stats_engine
from .analysis_validator import save_validation, validate_analysis_output

_statistics_runs: list[dict[str, Any]] = []


def _load_statistics_store() -> list[dict[str, Any]]:
    if STATISTICS_PATH.exists():
        data = json.loads(STATISTICS_PATH.read_text(encoding="utf-8"))
        runs = data.get("runs", [])
        return runs if isinstance(runs, list) else []
    return []


def _save_statistics_store() -> None:
    payload = {
        "updated_at": datetime.now().isoformat(),
        "runs": _statistics_runs,
    }
    STATISTICS_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _append_run(name: str, result: dict[str, Any]) -> dict[str, Any]:
    global _statistics_runs
    if not _statistics_runs:
        _statistics_runs = _load_statistics_store()
    entry = {
        "name": name,
        "ran_at": datetime.now().isoformat(),
        "result": result,
    }
    _statistics_runs.append(entry)
    _save_statistics_store()
    return entry


def _require_frame() -> pd.DataFrame:
    frame = get_loaded_dataframe()
    if frame is None:
        raise RuntimeError("데이터가 로드되지 않았습니다. 먼저 load_data를 호출하세요.")
    return frame


def _current_branch() -> str:
    result = subprocess.run(
        ["git", "-C", str(RESULTS_REPO), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or "main"


def sync_output_root(message: str = "Update stats output") -> dict[str, Any]:
    """프로젝트 output/ 전체를 커밋·push합니다."""
    output_dir = OUTPUT_ROOT
    if not (RESULTS_REPO / ".git").is_dir():
        result: dict[str, Any] = {"synced": False, "error": f"Git 레포 없음: {RESULTS_REPO}"}
        log_event(f"SYNC SKIP | {result['error']}", level=logging.ERROR)
        return result

    git_output = str(output_dir.relative_to(RESULTS_REPO))
    status = subprocess.run(
        ["git", "-C", str(RESULTS_REPO), "status", "--porcelain", git_output],
        capture_output=True,
        text=True,
        check=False,
    )
    if not status.stdout.strip():
        return {"synced": False, "message": "커밋할 변경사항 없음"}

    subprocess.run(["git", "-C", str(RESULTS_REPO), "add", git_output], check=True)
    commit = subprocess.run(
        ["git", "-C", str(RESULTS_REPO), "commit", "-m", message],
        capture_output=True,
        text=True,
        check=False,
    )
    if commit.returncode != 0:
        return {"synced": False, "message": message, "stderr": commit.stderr.strip()}

    log_event(f"SYNC OK   | commit: {message}")
    result = {
        "synced": True,
        "message": message,
        "stdout": commit.stdout.strip(),
        "pushed": False,
    }

    if AUTO_PUSH_RESULTS:
        branch = _current_branch()
        push = subprocess.run(
            ["git", "-C", str(RESULTS_REPO), "push", GIT_REMOTE, branch],
            capture_output=True,
            text=True,
            check=False,
        )
        if push.returncode == 0:
            result["pushed"] = True
        else:
            result["push_error"] = push.stderr.strip() or push.stdout.strip()

    return result


def sync_results(message: str = "Update stats output") -> dict[str, Any]:
    """하위 호환 — output/ 루트 동기화."""
    return sync_output_root(message)


def _maybe_sync(message: str) -> dict[str, Any] | None:
    if not AUTO_SYNC_RESULTS:
        return None
    result = sync_results(message)
    return result if result.get("synced") else None


@log_tool("run_descriptive_stats")
def run_descriptive_stats(columns: list[str] | None = None) -> dict[str, Any]:
    """수치형 컬럼의 기술통계(count, mean, std, min, max, 분위수)를 계산합니다.

  숫자는 이 Tool이 계산한 값만 리포트에 사용하세요. LLM이 임의로 숫자를 만들지 마세요.

    Args:
        columns: 분석할 컬럼 목록. 비우면 모든 수치형 컬럼.

    Returns:
        컬럼별 describe 통계.
    """
    frame = _require_frame()
    result = stats_engine.descriptive_stats(frame, columns)
    _append_run("descriptive_stats", result)
    return {"status": "ok", **result}


@log_tool("run_correlation")
def run_correlation(columns: list[str] | None = None) -> dict[str, Any]:
    """수치형 컬럼 간 피어슨 상관계수 행렬을 계산합니다.

    Args:
        columns: 분석할 컬럼 목록. 비우면 모든 수치형 컬럼.

    Returns:
        상관계수 matrix.
    """
    frame = _require_frame()
    result = stats_engine.correlation_matrix(frame, columns)
    _append_run("correlation", result)
    return {"status": "ok", **result}


@log_tool("run_groupby_stats")
def run_groupby_stats(
    group_by: str,
    value_columns: list[str],
    agg: str = "mean",
) -> dict[str, Any]:
    """범주형 컬럼 기준으로 수치 컬럼을 집계합니다.

    Args:
        group_by: 그룹 기준 컬럼 (예: recipe, equipment_id).
        value_columns: 집계할 수치 컬럼 목록.
        agg: mean, sum, count, std, min, max, median 중 하나.

    Returns:
        그룹별 집계 결과.
    """
    frame = _require_frame()
    result = stats_engine.groupby_stats(frame, group_by, value_columns, agg)
    _append_run("groupby_stats", result)
    return {"status": "ok", **result}


@log_tool("run_categorical_summary")
def run_categorical_summary(columns: list[str]) -> dict[str, Any]:
    """범주형 컬럼의 빈도·상위 값을 집계합니다.

    Args:
        columns: 분석할 범주형 컬럼 목록.

    Returns:
        컬럼별 top_values 빈도.
    """
    frame = _require_frame()
    result = stats_engine.categorical_summary(frame, columns)
    _append_run("categorical_summary", result)
    return {"status": "ok", **result}


@log_tool("detect_outliers")
def detect_outliers(column: str, method: str = "iqr") -> dict[str, Any]:
    """수치 컬럼의 이상치를 탐지합니다 (IQR 방식).

    Args:
        column: 분석할 수치 컬럼.
        method: 현재 iqr만 지원.

    Returns:
        이상치 개수, 경계값.
    """
    if method != "iqr":
        raise ValueError("현재 method='iqr'만 지원합니다.")
    frame = _require_frame()
    result = stats_engine.detect_outliers_iqr(frame, column)
    _append_run("outliers", result)
    return {"status": "ok", **result}


@log_tool("generate_charts")
def generate_charts(histogram_columns: list[str] | None = None) -> dict[str, Any]:
    """수치 컬럼 히스토그램·상관 히트맵을 PNG로 저장합니다.

    Args:
        histogram_columns: 히스토그램을 그릴 컬럼. 비우면 수치형 상위 3개.

    Returns:
        생성된 차트 파일 경로 목록.
    """
    frame = _require_frame()
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    chart_paths: list[str] = []

    numeric = list(frame.select_dtypes(include="number").columns)
    if histogram_columns:
        hist_cols = [c for c in histogram_columns if c in numeric][:4]
    else:
        hist_cols = numeric[:3]

    for col in hist_cols:
        fig, ax = plt.subplots(figsize=(7, 4))
        series = frame[col].dropna()
        ax.hist(series, bins=min(30, max(10, series.nunique())), color="#4C78A8", edgecolor="white")
        ax.set_title(f"Histogram: {col}")
        ax.set_xlabel(col)
        ax.set_ylabel("Count")
        fig.tight_layout()
        safe_name = str(col).replace("/", "_").replace(" ", "_")
        out = CHARTS_DIR / f"hist_{safe_name}.png"
        fig.savefig(out, bbox_inches="tight")
        plt.close(fig)
        chart_paths.append(str(out.relative_to(REPORT_PATH.parent)))

    if len(numeric) >= 2:
        corr = frame[numeric].corr(numeric_only=True)
        fig, ax = plt.subplots(figsize=(8, 6))
        im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1)
        ax.set_xticks(range(len(corr.columns)))
        ax.set_yticks(range(len(corr.columns)))
        ax.set_xticklabels(corr.columns, rotation=45, ha="right", fontsize=8)
        ax.set_yticklabels(corr.columns, fontsize=8)
        ax.set_title("Correlation Heatmap")
        fig.colorbar(im, ax=ax, fraction=0.046)
        fig.tight_layout()
        heatmap_path = CHARTS_DIR / "correlation_heatmap.png"
        fig.savefig(heatmap_path, bbox_inches="tight")
        plt.close(fig)
        chart_paths.append(str(heatmap_path.relative_to(REPORT_PATH.parent)))

    return {"status": "ok", "charts": chart_paths}


@log_tool("validate_analysis")
def validate_analysis() -> dict[str, Any]:
    """현재 분석 산출물을 검증하고 보강이 필요한 항목을 반환합니다.

    profile·statistics·report·charts를 대조해 누락된 분석과 리포트 이슈를 찾습니다.
    결과는 validation.json에 저장됩니다.

    Returns:
        complete, score, missing_analyses, issues, recommendations.
    """
    output_dir = REPORT_PATH.parent
    validation = validate_analysis_output(output_dir)
    save_validation(output_dir, validation)
    return {
        "status": "validated",
        "path": str(VALIDATION_PATH),
        **validation,
    }


@log_tool("save_analysis_report")
def save_analysis_report(
    title: str,
    summary: str,
    findings: list[str],
) -> dict[str, Any]:
    """한국어 분석 리포트를 Markdown으로 저장합니다.

    summary와 findings에는 반드시 Tool이 반환한 숫자·사실만 인용하세요.

    Args:
        title: 리포트 제목 (한국어).
        summary: 전체 요약 (한국어, 3~5문장).
        findings: 주요 발견 사항 목록 (한국어, Tool 결과 기반).

    Returns:
        저장 경로.
    """
    metadata = {
        "title": title,
        "updated_at": datetime.now().isoformat(),
    }
    METADATA_PATH.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        f"# {title}",
        "",
        f"생성 시각: {metadata['updated_at']}",
        "",
        "## 요약",
        "",
        summary.strip(),
        "",
        "## 주요 발견",
        "",
    ]
    for index, finding in enumerate(findings, start=1):
        lines.append(f"{index}. {finding.strip()}")
    lines.extend(["", "## 참고 파일", ""])

    if PROFILE_PATH.exists():
        lines.append(f"- 프로파일: `{PROFILE_PATH.name}`")
    if STATISTICS_PATH.exists():
        lines.append(f"- 통계 결과: `{STATISTICS_PATH.name}`")
    for chart in sorted(CHARTS_DIR.glob("*.png")):
        rel = chart.relative_to(REPORT_PATH.parent)
        lines.append(f"- ![{chart.stem}]({rel})")
        lines.append("")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")

    result: dict[str, Any] = {
        "status": "saved",
        "path": str(REPORT_PATH),
        "title": title,
        "finding_count": len(findings),
    }
    sync = _maybe_sync(f"Stats report: {title}")
    if sync:
        result["git_sync"] = sync
    return result


@log_tool("read_analysis_state")
def read_analysis_state() -> dict[str, Any]:
    """현재까지의 분석 상태(프로파일, 통계 실행, 리포트, 차트)를 읽습니다.

    Returns:
        메타데이터, 파일 존재 여부, 통계 실행 횟수.
    """
    runs = _statistics_runs or _load_statistics_store()
    charts = [str(p.relative_to(REPORT_PATH.parent)) for p in sorted(CHARTS_DIR.glob("*.png"))]

    validation_summary = None
    if VALIDATION_PATH.exists():
        validation_summary = json.loads(VALIDATION_PATH.read_text(encoding="utf-8"))

    state: dict[str, Any] = {
        "metadata": None,
        "profile_exists": PROFILE_PATH.exists(),
        "statistics_run_count": len(runs),
        "report_exists": REPORT_PATH.exists(),
        "validation_exists": VALIDATION_PATH.exists(),
        "validation": validation_summary,
        "charts": charts,
    }

    if METADATA_PATH.exists():
        state["metadata"] = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    if PROFILE_PATH.exists():
        profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        state["profile_summary"] = {
            "row_count": profile.get("row_count"),
            "column_count": profile.get("column_count"),
            "analysis_hints": profile.get("analysis_hints"),
        }

    return state
