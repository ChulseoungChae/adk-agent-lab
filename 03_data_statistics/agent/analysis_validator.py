"""분석 결과 검증·보강 판단 — output 파일 기반 결정론적 체크."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def _run_names(statistics_path: Path) -> set[str]:
    data = _load_json(statistics_path)
    if not data:
        return set()
    runs = data.get("runs", [])
    if not isinstance(runs, list):
        return set()
    return {str(item.get("name", "")) for item in runs if item.get("name")}


def _count_findings(report_path: Path) -> int:
    if not report_path.exists():
        return 0
    text = report_path.read_text(encoding="utf-8")
    match = re.search(r"## 주요 발견\s*\n(.*?)(?:\n## |\Z)", text, re.DOTALL)
    if not match:
        return 0
    section = match.group(1)
    return len(re.findall(r"^\d+\.\s", section, re.MULTILINE))


def _high_missing_columns(profile_path: Path) -> list[str]:
    profile = _load_json(profile_path)
    if not profile:
        return []
    result: list[str] = []
    for col in profile.get("columns", []):
        if not isinstance(col, dict):
            continue
        if float(col.get("missing_pct", 0)) > 10:
            result.append(str(col.get("name", "")))
    return [name for name in result if name]


def validate_analysis_output(output_dir: Path) -> dict[str, Any]:
    """output 디렉터리의 분석 산출물을 검증하고 보강 필요 여부를 반환합니다."""
    profile_path = output_dir / "profile.json"
    statistics_path = output_dir / "statistics.json"
    report_path = output_dir / "report.md"
    charts_dir = output_dir / "charts"

    profile = _load_json(profile_path)
    hints = list(profile.get("analysis_hints", [])) if profile else []
    numeric_cols = list(profile.get("numeric_columns", [])) if profile else []
    categorical_cols = list(profile.get("categorical_columns", [])) if profile else []
    run_names = _run_names(statistics_path)
    chart_count = len(list(charts_dir.glob("*.png"))) if charts_dir.is_dir() else 0
    findings_count = _count_findings(report_path)
    high_missing = _high_missing_columns(profile_path)

    checks: list[dict[str, Any]] = []

    def add_check(name: str, passed: bool, detail: str, required: bool = True) -> None:
        checks.append({"name": name, "passed": passed, "detail": detail, "required": required})

    add_check("profile_exists", profile_path.exists(), "profile.json 존재")
    add_check(
        "descriptive_stats",
        "descriptive_stats" in run_names,
        "run_descriptive_stats 실행 필요",
    )

    if "correlation_analysis_available" in hints:
        add_check(
            "correlation",
            "correlation" in run_names,
            "상관 분석(correlation) 미실행",
        )
    if "groupby_analysis_available" in hints:
        add_check(
            "groupby_stats",
            "groupby_stats" in run_names,
            "그룹별 집계(groupby_stats) 미실행",
        )
    if categorical_cols:
        add_check(
            "categorical_summary",
            "categorical_summary" in run_names,
            "범주형 요약(categorical_summary) 미실행",
        )
    if numeric_cols:
        add_check(
            "outliers",
            "outliers" in run_names,
            "이상치 탐지(outliers) 미실행",
        )

    add_check("charts", chart_count >= 1, f"차트 없음 (현재 {chart_count}개)")
    add_check("report_exists", report_path.exists(), "report.md 없음")
    add_check(
        "findings_count",
        findings_count >= 3,
        f"주요 발견 3개 이상 필요 (현재 {findings_count}개)",
    )

    if high_missing and report_path.exists():
        report_text = report_path.read_text(encoding="utf-8")
        missing_mentioned = any(name in report_text for name in high_missing)
        add_check(
            "high_missing_mentioned",
            missing_mentioned,
            f"결측 10% 초과 컬럼 언급 필요: {', '.join(high_missing)}",
        )

    required_checks = [c for c in checks if c.get("required", True)]
    passed = sum(1 for c in required_checks if c["passed"])
    total = len(required_checks)
    score = round(passed / total * 100, 1) if total else 0.0
    complete = passed == total

    missing_analyses: list[str] = []
    recommendations: list[str] = []

    for check in checks:
        if check["passed"]:
            continue
        if check["name"] in {
            "descriptive_stats",
            "correlation",
            "groupby_stats",
            "categorical_summary",
            "outliers",
        }:
            missing_analyses.append(check["name"])
        recommendations.append(f"{check['name']}: {check['detail']}")

    if not complete:
        if "descriptive_stats" not in run_names:
            recommendations.append("run_descriptive_stats를 먼저 실행하세요.")
        if chart_count == 0:
            recommendations.append("generate_charts로 시각화를 저장하세요.")
        if findings_count < 3:
            recommendations.append(
                "save_analysis_report의 findings를 Tool 결과 기반으로 3개 이상 작성하세요."
            )

    return {
        "complete": complete,
        "score": score,
        "passed_checks": passed,
        "total_checks": total,
        "checks": checks,
        "missing_analyses": missing_analyses,
        "issues": [c["detail"] for c in checks if not c["passed"]],
        "recommendations": recommendations,
        "metrics": {
            "statistics_run_count": len(run_names),
            "chart_count": chart_count,
            "findings_count": findings_count,
            "run_names": sorted(run_names),
        },
    }


def save_validation(output_dir: Path, validation: dict[str, Any]) -> Path:
    path = output_dir / "validation.json"
    path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def reinforcement_prompt(validation: dict[str, Any]) -> str:
    """보강 라운드용 ADK 프롬프트."""
    if validation.get("complete"):
        return ""

    missing = ", ".join(validation.get("missing_analyses", [])) or "없음"
    issues = "\n".join(f"- {item}" for item in validation.get("issues", []))
    recs = "\n".join(f"- {item}" for item in validation.get("recommendations", []))

    return f"""
validate_analysis로 확인한 결과 분석이 **아직 완료되지 않았습니다** (점수 {validation.get('score', 0)}%).

## 누락된 분석 Tool
{missing}

## 미통과 항목
{issues}

## 보강 지시
{recs}

요구사항:
- 위 항목만 보완하세요. 이미 완료된 Tool은 불필요하게 반복하지 마세요.
- **숫자는 Tool 반환값만** 사용하세요.
- save_analysis_report로 리포트를 **업데이트**하세요.
- generate_charts가 안 됐으면 실행하세요.
- 완료 후 validate_analysis → read_analysis_state 순으로 확인하세요.
- 사용자에게 질문하지 마세요.
""".strip()
