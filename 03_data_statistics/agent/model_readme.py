"""모델별 output/README.md 자동 생성 — JSON·차트를 한국어 Markdown으로 정리."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def _fmt_num(value: Any, digits: int = 4) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _find_run(runs: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for item in reversed(runs):
        if item.get("name") == name:
            return item.get("result", {})
    return None


def _build_findings_from_stats(
    profile: dict[str, Any] | None,
    runs: list[dict[str, Any]],
) -> list[str]:
    findings: list[str] = []
    if profile:
        findings.append(
            f"데이터 규모: {profile.get('row_count', '?')}행 × {profile.get('column_count', '?')}열"
        )
        high_missing = [
            c["name"]
            for c in profile.get("columns", [])
            if isinstance(c, dict) and float(c.get("missing_pct", 0)) > 10
        ]
        if high_missing:
            findings.append(f"결측 10% 초과 컬럼: {', '.join(high_missing)}")
        if profile.get("data_period"):
            period = profile["data_period"]
            findings.append(
                f"데이터 주기({period.get('column', '')}): "
                f"{period.get('inferred_frequency', '-')}"
            )
        file_info = profile.get("file_info", {})
        if file_info.get("size_human"):
            findings.append(f"파일 크기: {file_info['size_human']}")

    corr = _find_run(runs, "correlation")
    if corr and corr.get("matrix"):
        matrix = corr["matrix"]
        best_pair = None
        best_val = 0.0
        cols = corr.get("columns", [])
        for i, col_a in enumerate(cols):
            for col_b in cols[i + 1 :]:
                val = matrix.get(col_a, {}).get(col_b)
                if val is not None and abs(float(val)) > abs(best_val):
                    best_val = float(val)
                    best_pair = (col_a, col_b)
        if best_pair:
            findings.append(
                f"최고 상관: {best_pair[0]} ↔ {best_pair[1]} = {_fmt_num(best_val)}"
            )

    outliers = _find_run(runs, "outliers")
    if outliers and outliers.get("column"):
        findings.append(
            f"이상치({outliers['column']}): {outliers.get('outlier_count', 0)}건 "
            f"({outliers.get('outlier_pct', 0)}%)"
        )

    groupby = _find_run(runs, "groupby_stats")
    if groupby and groupby.get("group_by"):
        findings.append(
            f"그룹 집계({groupby['group_by']}): {groupby.get('group_count', 0)}개 그룹"
        )

    return findings[:6]


def build_report_from_artifacts(output_dir: Path) -> Path | None:
    """statistics.json·profile.json으로 report.md를 결정론적으로 생성합니다."""
    profile = _load_json(output_dir / "profile.json")
    stats = _load_json(output_dir / "statistics.json")
    if not stats:
        return None

    runs = stats.get("runs", [])
    if not isinstance(runs, list) or not runs:
        return None

    metadata = _load_json(output_dir / "analysis_metadata.json") or {}
    title = metadata.get("title") or "센서 데이터 통계 분석 보고서 (자동 생성)"
    findings = _build_findings_from_stats(profile, runs)
    if len(findings) < 3:
        findings.append("통계 Tool 실행 결과는 statistics.json에 저장되어 있습니다.")
    while len(findings) < 3:
        findings.append("추가 분석은 README.md의 상세 표를 참고하세요.")

    summary = (
        "본 보고서는 Tool이 계산한 statistics.json·profile.json을 바탕으로 "
        "자동 정리되었습니다. 수치는 JSON 원본과 동일합니다."
    )

    lines = [
        f"# {title}",
        "",
        f"생성 시각: {datetime.now().isoformat()}",
        "",
        "## 요약",
        "",
        summary,
        "",
        "## 주요 발견",
        "",
    ]
    for index, finding in enumerate(findings, start=1):
        lines.append(f"{index}. {finding}")

    report_path = output_dir / "report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def generate_model_readme(output_dir: Path, *, model: str = "") -> str:
    """모델 output 폴더의 JSON·차트를 README.md로 정리합니다."""
    profile = _load_json(output_dir / "profile.json")
    stats = _load_json(output_dir / "statistics.json")
    validation = _load_json(output_dir / "validation.json")
    metadata = _load_json(output_dir / "analysis_metadata.json") or {}
    report_path = output_dir / "report.md"

    if not report_path.exists():
        build_report_from_artifacts(output_dir)

    charts = sorted((output_dir / "charts").glob("*.png")) if (output_dir / "charts").is_dir() else []
    runs = stats.get("runs", []) if stats else []
    if not isinstance(runs, list):
        runs = []

    model_label = model or metadata.get("model", output_dir.name)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"# {model_label} — 통계 분석 결과",
        "",
        f"자동 생성: {now}",
        "",
        "## 실행 요약",
        "",
        "| 항목 | 값 |",
        "|------|-----|",
        f"| 모델 | `{model_label}` |",
        f"| 검증 점수 | {validation.get('score', '-') if validation else '-'}% |",
        f"| 검증 완료 | {'예' if validation and validation.get('complete') else '아니오'} |",
        f"| 통계 Tool 실행 | {len(runs)}회 |",
        f"| 차트 | {len(charts)}개 |",
    ]

    if profile:
        file_info = profile.get("file_info", {})
        lines.extend(
            [
                "",
                "## 데이터 개요",
                "",
                f"- 행 수: **{profile.get('row_count', '?')}**",
                f"- 열 수: **{profile.get('column_count', '?')}**",
            ]
        )
        if file_info:
            lines.append(
                f"- 파일 크기: **{file_info.get('size_human', '-')}** "
                f"(`{file_info.get('name', '-')}`)"
            )
        data_period = profile.get("data_period")
        if data_period:
            lines.append(
                f"- 데이터 주기 (`{data_period.get('column', '')}`): "
                f"**{data_period.get('inferred_frequency', '-')}** "
                f"(중앙 간격 {data_period.get('median_interval_human', '-')})"
            )
        elif profile.get("datetime_intervals"):
            for col, interval in profile["datetime_intervals"].items():
                lines.append(
                    f"- 데이터 주기 (`{col}`): **{interval.get('inferred_frequency', '-')}**"
                )
        lines.extend(
            [
                f"- 수치형: {', '.join(profile.get('numeric_columns', [])) or '없음'}",
                f"- 범주형: {', '.join(profile.get('categorical_columns', [])) or '없음'}",
                f"- 분석 힌트: {', '.join(profile.get('analysis_hints', [])) or '없음'}",
            ]
        )

        cat_breakdown = profile.get("categorical_breakdown", {})
        if cat_breakdown:
            lines.extend(["", "### 문자열·범주형 필드 분석", ""])
            for col_name, info in cat_breakdown.items():
                lines.append(f"#### `{col_name}`")
                lines.append("")
                lines.append(
                    f"- 고유값: {info.get('unique_count', 0)}개 "
                    f"(카테고리 {info.get('category_count', 0)}종)"
                )
                dist = info.get("value_distribution") or info.get("top_values") or {}
                if dist:
                    lines.append("")
                    lines.append("| 값 | 건수 |")
                    lines.append("|-----|------|")
                    for value, count in dist.items():
                        lines.append(f"| `{value}` | {count} |")
                lines.append("")

        lines.extend(
            [
                "### 컬럼 프로파일",
                "",
                "| 컬럼 | 종류 | 결측률(%) |",
                "|------|------|-----------|",
            ]
        )
        for col in profile.get("columns", []):
            if not isinstance(col, dict):
                continue
            lines.append(
                f"| `{col.get('name', '')}` | {col.get('kind', '')} "
                f"| {col.get('missing_pct', 0)} |"
            )

    desc = _find_run(runs, "descriptive_stats")
    if desc and desc.get("statistics"):
        lines.extend(["", "## 기술통계 (descriptive_stats)", ""])
        for col_name, values in desc["statistics"].items():
            if not isinstance(values, dict):
                continue
            lines.append(f"### `{col_name}`")
            lines.append("")
            lines.append("| 지표 | 값 |")
            lines.append("|------|-----|")
            for key in ("count", "mean", "std", "min", "25%", "50%", "75%", "max"):
                if key in values:
                    lines.append(f"| {key} | {_fmt_num(values[key])} |")
            lines.append("")

    corr = _find_run(runs, "correlation")
    if corr and corr.get("columns") and corr.get("matrix"):
        lines.extend(["", "## 상관계수 (correlation)", ""])
        cols = corr["columns"]
        header = "| | " + " | ".join(f"`{c}`" for c in cols) + " |"
        sep = "|---|" + "|".join(["---"] * len(cols)) + "|"
        lines.extend([header, sep])
        matrix = corr["matrix"]
        for row_name in cols:
            cells = [f"`{row_name}`"]
            for col_name in cols:
                val = matrix.get(row_name, {}).get(col_name)
                cells.append(_fmt_num(val))
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")

    for run in runs:
        if run.get("name") != "groupby_stats":
            continue
        result = run.get("result", {})
        lines.extend(
            [
                "",
                f"## 그룹별 집계 — `{result.get('group_by', '')}` ({result.get('agg', '')})",
                "",
            ]
        )
        data = result.get("data", [])
        if data and isinstance(data, list):
            keys = list(data[0].keys())
            lines.append("| " + " | ".join(keys) + " |")
            lines.append("| " + " | ".join(["---"] * len(keys)) + " |")
            for row in data:
                lines.append("| " + " | ".join(_fmt_num(row.get(k)) for k in keys) + " |")
        lines.append("")

    outliers = _find_run(runs, "outliers")
    if outliers:
        lines.extend(
            [
                "",
                "## 이상치 탐지 (IQR)",
                "",
                f"- 컬럼: `{outliers.get('column', '')}`",
                f"- 이상치: {outliers.get('outlier_count', 0)}건 ({outliers.get('outlier_pct', 0)}%)",
                f"- 경계: {_fmt_num(outliers.get('lower_bound'))} ~ {_fmt_num(outliers.get('upper_bound'))}",
                "",
            ]
        )

    if charts:
        box_charts = [c for c in charts if c.name.startswith("box")]
        other_charts = [c for c in charts if not c.name.startswith("box")]
        if box_charts:
            lines.extend(["", "## 박스플롯 (값 범위)", ""])
            for chart in box_charts:
                rel = chart.relative_to(output_dir)
                lines.extend([f"### {chart.stem}", "", f"![{chart.stem}]({rel})", ""])
        if other_charts:
            lines.extend(["", "## 시각화", ""])
            for chart in other_charts:
                rel = chart.relative_to(output_dir)
                lines.extend([f"### {chart.stem}", "", f"![{chart.stem}]({rel})", ""])

    if validation:
        lines.extend(["", "## 검증 결과", ""])
        lines.append(f"- 점수: **{validation.get('score')}%** ({validation.get('passed_checks')}/{validation.get('total_checks')})")
        issues = validation.get("issues", [])
        if issues:
            lines.append("- 미통과:")
            for issue in issues:
                lines.append(f"  - {issue}")

    if report_path.exists():
        lines.extend(["", "## LLM 리포트", "", f"상세 서술: [`report.md`](report.md)", ""])

    lines.extend(
        [
            "## 원본 파일",
            "",
            "- [`profile.json`](profile.json)",
            "- [`statistics.json`](statistics.json)",
            "- [`validation.json`](validation.json)",
            "",
        ]
    )

    text = "\n".join(lines)
    readme_path = output_dir / "README.md"
    readme_path.write_text(text, encoding="utf-8")
    return text
