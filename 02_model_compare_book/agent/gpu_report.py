"""GPU CSV 기반 output/README.md 리포트 생성."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime
import os
from pathlib import Path
from typing import Any

from .config import COMPARE_MODELS

MAX_GPUS = int(os.getenv("GPU_MONITOR_COUNT", "4"))


def _stat(values: list[float]) -> dict[str, float]:
    if not values:
        return {"min": 0.0, "max": 0.0, "avg": 0.0}
    return {
        "min": round(min(values), 1),
        "max": round(max(values), 1),
        "avg": round(sum(values) / len(values), 1),
    }


def _fmt_triple(stats: dict[str, float]) -> str:
    return f"{stats['min']} / {stats['avg']} / {stats['max']}"


def _load_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        return []
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def _group_by_model(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        model = row.get("model", "").strip()
        if model:
            grouped[model].append(row)
    return grouped


def _column_stats(rows: list[dict[str, str]], column: str) -> dict[str, float]:
    values: list[float] = []
    for row in rows:
        raw = row.get(column, "")
        if raw in ("", None):
            continue
        try:
            values.append(float(raw))
        except ValueError:
            continue
    return _stat(values)


def analyze_model_samples(rows: list[dict[str, str]]) -> dict[str, Any]:
    if not rows:
        return {"sample_count": 0}

    timestamps = [row.get("timestamp", "") for row in rows if row.get("timestamp")]
    per_gpu: dict[int, dict[str, dict[str, float]]] = {}
    for index in range(MAX_GPUS):
        per_gpu[index] = {
            "util_pct": _column_stats(rows, f"gpu{index}_util_pct"),
            "mem_used_mb": _column_stats(rows, f"gpu{index}_mem_used_mb"),
            "mem_util_pct": _column_stats(rows, f"gpu{index}_mem_util_pct"),
            "power_w": _column_stats(rows, f"gpu{index}_power_w"),
        }

    return {
        "sample_count": len(rows),
        "started_at": min(timestamps) if timestamps else "",
        "finished_at": max(timestamps) if timestamps else "",
        "per_gpu": per_gpu,
        "total_gpu_util_pct": _column_stats(rows, "total_gpu_util_pct"),
        "total_mem_used_mb": _column_stats(rows, "total_mem_used_mb"),
        "total_power_w": _column_stats(rows, "total_power_w"),
    }


def _book_results_map(book_results: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    if not book_results:
        return {}
    return {item["model"]: item for item in book_results if item.get("model")}


def _load_book_results(summary_path: Path) -> list[dict[str, Any]]:
    if not summary_path.exists():
        return []
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    models = data.get("models", [])
    return models if isinstance(models, list) else []


def generate_output_readme(
    *,
    csv_path: Path,
    readme_path: Path,
    models: list[str] | None = None,
    book_results: list[dict[str, Any]] | None = None,
    summary_path: Path | None = None,
) -> str:
    """gpu_usage.csv와 집필 결과를 바탕으로 output/README.md를 생성합니다."""
    models = models or COMPARE_MODELS
    if book_results is None and summary_path is not None:
        book_results = _load_book_results(summary_path)

    rows = _load_csv_rows(csv_path)
    grouped = _group_by_model(rows)
    book_map = _book_results_map(book_results)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "# 02_model_compare_book — 실행 결과 요약",
        "",
        f"자동 생성: {now}  ",
        f"데이터 출처: `{csv_path.name}`",
        "",
        "## 모델별 집필 결과",
        "",
        "| 모델 | 상태 | 챕터 | 소요 시간 | 출력 폴더 |",
        "|------|------|------|-----------|-----------|",
    ]

    for model in models:
        book = book_map.get(model, {})
        slug = book.get("slug", model.replace(":", "_").replace(".", "_").replace("-", "_"))
        status = book.get("status", "-")
        chapters = book.get("chapter_count", "-")
        elapsed = book.get("elapsed_seconds", "-")
        if isinstance(elapsed, (int, float)):
            elapsed = f"{elapsed}s"
        lines.append(f"| `{model}` | {status} | {chapters} | {elapsed} | `{slug}/` |")

    lines.extend(
        [
            "",
            "## GPU 사용량 요약",
            "",
            "각 셀은 **최소 / 평균 / 최대** 순입니다.",
            "",
            "### 모델 간 비교 (VRAM·GPU 합산)",
            "",
            "| 모델 | 샘플 수 | VRAM 합산 (MB) | GPU util 합산 (%) | 전력 합산 (W) |",
            "|------|---------|----------------|-------------------|---------------|",
        ]
    )

    model_stats: dict[str, dict[str, Any]] = {}
    for model in models:
        stats = analyze_model_samples(grouped.get(model, []))
        model_stats[model] = stats
        if stats.get("sample_count", 0) == 0:
            lines.append(f"| `{model}` | 0 | - | - | - |")
            continue
        lines.append(
            f"| `{model}` | {stats['sample_count']} "
            f"| {_fmt_triple(stats['total_mem_used_mb'])} "
            f"| {_fmt_triple(stats['total_gpu_util_pct'])} "
            f"| {_fmt_triple(stats['total_power_w'])} |"
        )

    for model in models:
        stats = model_stats.get(model, {})
        lines.extend(["", f"### `{model}`", ""])
        if stats.get("sample_count", 0) == 0:
            lines.append("CSV에 해당 모델 샘플이 없습니다.")
            continue

        lines.append(
            f"- 샘플: **{stats['sample_count']}회** "
            f"({stats['started_at']} ~ {stats['finished_at']})"
        )
        lines.extend(
            [
                "",
                "#### GPU별",
                "",
                "| GPU | VRAM 사용 (MB) | GPU util (%) | VRAM 대역폭 util (%) | 전력 (W) |",
                "|-----|----------------|--------------|----------------------|----------|",
            ]
        )

        for index in range(MAX_GPUS):
            gpu = stats["per_gpu"][index]
            lines.append(
                f"| GPU {index} "
                f"| {_fmt_triple(gpu['mem_used_mb'])} "
                f"| {_fmt_triple(gpu['util_pct'])} "
                f"| {_fmt_triple(gpu['mem_util_pct'])} "
                f"| {_fmt_triple(gpu['power_w'])} |"
            )

        lines.extend(
            [
                "",
                "#### 4 GPU 합산",
                "",
                "| 항목 | 최소 / 평균 / 최대 |",
                "|------|-------------------|",
                f"| VRAM 합산 (MB) | {_fmt_triple(stats['total_mem_used_mb'])} |",
                f"| GPU util 합산 (%) | {_fmt_triple(stats['total_gpu_util_pct'])} |",
                f"| 전력 합산 (W) | {_fmt_triple(stats['total_power_w'])} |",
            ]
        )

    lines.extend(
        [
            "",
            "## 참고",
            "",
            "- 상세 시계열: `gpu_usage.csv`",
            "- 세션별 텍스트 로그: `gpu_usage_summary.log`, `agent.log`",
            "- 집필 JSON 요약: `comparison_summary.json`",
            "",
        ]
    )

    text = "\n".join(lines)
    readme_path.parent.mkdir(parents=True, exist_ok=True)
    readme_path.write_text(text, encoding="utf-8")
    return text
