"""모델별 통계 분석 비교 README·차트 생성."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

CHART_COLORS = ["#4C78A8", "#F58518", "#54A24B", "#E45756"]


def _short_label(model: str) -> str:
    return model.replace("gemma4:", "g4:").replace("qwen3.6:", "q3.6:").replace("qwen3-vl:", "q3-vl:")


def _save_chart(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def generate_compare_charts(
    *,
    results: list[dict[str, Any]],
    charts_dir: Path,
) -> list[str]:
    charts_dir.mkdir(parents=True, exist_ok=True)
    labels = [_short_label(item["model"]) for item in results]
    colors = CHART_COLORS[: len(results)]
    paths: list[str] = []

    elapsed = [float(item.get("elapsed_seconds") or 0) for item in results]
    fig, ax = plt.subplots()
    bars = ax.bar(labels, [v / 60 for v in elapsed], color=colors)
    ax.set_title("Stats Analysis — Elapsed Time by Model")
    ax.set_ylabel("Minutes")
    ax.bar_label(bars, fmt="%.1f", padding=3)
    name = "compare_elapsed.png"
    _save_chart(fig, charts_dir / name)
    paths.append(f"charts/{name}")

    scores = [float(item.get("validation_score") or 0) for item in results]
    fig, ax = plt.subplots()
    bars = ax.bar(labels, scores, color=colors)
    ax.set_title("Stats Analysis — Validation Score (%)")
    ax.set_ylabel("Score")
    ax.set_ylim(0, 100)
    ax.bar_label(bars, fmt="%.0f", padding=3)
    name = "compare_validation_score.png"
    _save_chart(fig, charts_dir / name)
    paths.append(f"charts/{name}")

    stats_runs = [int(item.get("statistics_run_count") or 0) for item in results]
    findings = [int(item.get("findings_count") or 0) for item in results]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    x = list(range(len(results)))
    width = 0.35
    ax.bar([i - width / 2 for i in x], stats_runs, width=width, label="Stats runs", color="#4C78A8")
    ax.bar([i + width / 2 for i in x], findings, width=width, label="Findings", color="#F58518")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_title("Stats Analysis — Tool Runs vs Report Findings")
    ax.legend()
    name = "compare_coverage.png"
    _save_chart(fig, charts_dir / name)
    paths.append(f"charts/{name}")

    return paths


def generate_output_readme(
    *,
    readme_path: Path,
    models: list[str],
    results: list[dict[str, Any]],
    charts_dir: Path,
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    chart_paths = generate_compare_charts(results=results, charts_dir=charts_dir)

    lines = [
        "# 03_data_statistics — 모델별 통계 분석 비교",
        "",
        f"자동 생성: {now}",
        "",
        "## 모델별 실행 결과",
        "",
        "| 모델 | 상태 | 검증 점수 | 통계 Tool | 발견 | 소요 시간 | 출력 폴더 |",
        "|------|------|-----------|-----------|------|-----------|-----------|",
    ]

    for item in results:
        model = item.get("model", "")
        lines.append(
            f"| `{model}` | {item.get('status', '-')} "
            f"| {item.get('validation_score', '-')}% "
            f"| {item.get('statistics_run_count', '-')} "
            f"| {item.get('findings_count', '-')} "
            f"| {item.get('elapsed_seconds', '-')}s "
            f"| `{item.get('slug', '')}/` |"
        )

    lines.extend(["", "## 비교 그래프", ""])
    titles = {
        "compare_elapsed.png": "모델별 소요 시간 (분)",
        "compare_validation_score.png": "검증 점수 (%)",
        "compare_coverage.png": "통계 Tool 실행 수 vs 리포트 발견 수",
    }
    for chart_path in chart_paths:
        filename = Path(chart_path).name
        title = titles.get(filename, filename)
        lines.extend([f"### {title}", "", f"![{title}]({chart_path})", ""])

    for item in results:
        model = item.get("model", "")
        slug = item.get("slug", "")
        validation = item.get("validation", {})
        lines.extend([f"## `{model}` 검증 상세", ""])
        if validation:
            lines.append(f"- 완료: **{'예' if validation.get('complete') else '아니오'}**")
            lines.append(f"- 점수: {validation.get('score', '-')}%")
            issues = validation.get("issues", [])
            if issues:
                lines.append("- 미통과:")
                for issue in issues:
                    lines.append(f"  - {issue}")
        lines.append(f"- 리포트: `{slug}/report.md`")
        lines.append("")

    lines.extend(
        [
            "## 참고",
            "",
            "- 모델별 상세: `{slug}/profile.json`, `statistics.json`, `validation.json`",
            "- GPU 시계열: `gpu_usage.csv`",
            "- JSON 요약: `comparison_summary.json`",
            "",
        ]
    )

    text = "\n".join(lines)
    readme_path.write_text(text, encoding="utf-8")
    return text
