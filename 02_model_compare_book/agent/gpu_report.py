"""GPU CSV 기반 output/README.md 리포트·성능 비교 그래프 생성."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime
import os
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .config import COMPARE_MODELS

CHART_COLORS = ["#4C78A8", "#F58518", "#54A24B", "#E45756"]

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


def _short_model_label(model: str) -> str:
    return model.replace("gemma4:", "g4:").replace("qwen3.6:", "q3.6:").replace("qwen3-vl:", "q3-vl:")


def _setup_chart_style() -> None:
    plt.rcParams.update(
        {
            "figure.figsize": (9, 4.5),
            "figure.dpi": 120,
            "axes.grid": True,
            "grid.alpha": 0.3,
            "font.size": 10,
        }
    )


def _save_chart(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def generate_comparison_charts(
    *,
    csv_path: Path,
    charts_dir: Path,
    models: list[str] | None = None,
    book_results: list[dict[str, Any]] | None = None,
    summary_path: Path | None = None,
) -> list[str]:
    """성능 비교 PNG를 생성하고 README용 상대 경로 목록을 반환합니다."""
    models = models or COMPARE_MODELS
    if book_results is None and summary_path is not None:
        book_results = _load_book_results(summary_path)

    book_map = _book_results_map(book_results)
    rows = _load_csv_rows(csv_path)
    grouped = _group_by_model(rows)
    model_stats = {model: analyze_model_samples(grouped.get(model, [])) for model in models}

    _setup_chart_style()
    chart_paths: list[str] = []

    labels = [_short_model_label(model) for model in models]
    colors = CHART_COLORS[: len(models)]

    elapsed = [
        float(book_map.get(model, {}).get("elapsed_seconds") or 0) for model in models
    ]
    chapters = [
        int(book_map.get(model, {}).get("chapter_count") or 0) for model in models
    ]
    vram_avg = [model_stats[model]["total_mem_used_mb"]["avg"] for model in models]
    util_avg = [model_stats[model]["total_gpu_util_pct"]["avg"] for model in models]
    power_avg = [model_stats[model]["total_power_w"]["avg"] for model in models]

    fig, ax = plt.subplots()
    bars = ax.bar(labels, [value / 60 for value in elapsed], color=colors)
    ax.set_title("Model Compare — Elapsed Time")
    ax.set_ylabel("Minutes")
    ax.bar_label(bars, fmt="%.1f", padding=3)
    chart_name = "compare_elapsed.png"
    _save_chart(fig, charts_dir / chart_name)
    chart_paths.append(f"charts/{chart_name}")

    fig, ax = plt.subplots()
    bars = ax.bar(labels, chapters, color=colors)
    ax.set_title("Model Compare — Completed Chapters")
    ax.set_ylabel("Chapters")
    ax.bar_label(bars, padding=3)
    chart_name = "compare_chapters.png"
    _save_chart(fig, charts_dir / chart_name)
    chart_paths.append(f"charts/{chart_name}")

    fig, ax = plt.subplots(figsize=(10, 4.5))
    x_positions = list(range(len(models)))
    width = 0.25
    ax.bar(
        [pos - width for pos in x_positions],
        vram_avg,
        width=width,
        label="VRAM avg (MB)",
        color="#4C78A8",
    )
    ax.bar(
        x_positions,
        util_avg,
        width=width,
        label="GPU util avg (%)",
        color="#F58518",
    )
    ax.bar(
        [pos + width for pos in x_positions],
        power_avg,
        width=width,
        label="Power avg (W)",
        color="#54A24B",
    )
    ax.set_xticks(x_positions)
    ax.set_xticklabels(labels)
    ax.set_title("Model Compare — GPU Usage (Average)")
    ax.legend(loc="upper right")
    chart_name = "compare_gpu_avg.png"
    _save_chart(fig, charts_dir / chart_name)
    chart_paths.append(f"charts/{chart_name}")

    fig, ax = plt.subplots(figsize=(10, 4.5))
    for index, model in enumerate(models):
        model_rows = grouped.get(model, [])
        if not model_rows:
            continue
        times: list[float] = []
        values: list[float] = []
        start: datetime | None = None
        for row in model_rows:
            raw_ts = row.get("timestamp", "")
            raw_mem = row.get("total_mem_used_mb", "")
            if not raw_ts or raw_mem in ("", None):
                continue
            try:
                ts = datetime.strptime(raw_ts, "%Y-%m-%d %H:%M:%S")
                mem = float(raw_mem)
            except ValueError:
                continue
            if start is None:
                start = ts
            times.append((ts - start).total_seconds() / 60.0)
            values.append(mem)
        if times:
            ax.plot(
                times,
                values,
                label=_short_model_label(model),
                color=colors[index],
                linewidth=1.2,
                alpha=0.9,
            )
    ax.set_title("VRAM Usage Over Time (4 GPUs Total)")
    ax.set_xlabel("Elapsed (min)")
    ax.set_ylabel("VRAM (MB)")
    ax.legend(loc="upper right", fontsize=8)
    chart_name = "compare_vram_timeseries.png"
    _save_chart(fig, charts_dir / chart_name)
    chart_paths.append(f"charts/{chart_name}")

    return chart_paths


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

    charts_dir = readme_path.parent / "charts"
    chart_paths = generate_comparison_charts(
        csv_path=csv_path,
        charts_dir=charts_dir,
        models=models,
        book_results=book_results,
        summary_path=summary_path,
    )

    lines.extend(["", "## 성능 비교 그래프", ""])
    chart_titles = {
        "compare_elapsed.png": "집필 소요 시간 (분)",
        "compare_chapters.png": "완성 챕터 수",
        "compare_gpu_avg.png": "GPU 사용량 평균 (VRAM·util·전력)",
        "compare_vram_timeseries.png": "VRAM 시계열 (4 GPU 합산)",
    }
    for chart_path in chart_paths:
        filename = Path(chart_path).name
        title = chart_titles.get(filename, filename)
        lines.extend([f"### {title}", "", f"![{title}]({chart_path})", ""])

    lines.extend(
        [
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
            "- 그래프 원본: `charts/`",
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
