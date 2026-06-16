"""GPU 사용량 모니터링 — nvidia-smi 기반 CSV 샘플링 및 통계 기록."""

from __future__ import annotations

import csv
import subprocess
import threading
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

CSV_FIELDS = [
    "timestamp",
    "model",
    "gpu_index",
    "gpu_name",
    "gpu_util_pct",
    "mem_util_pct",
    "mem_used_mb",
    "mem_total_mb",
    "temperature_c",
    "power_w",
]

STAT_FIELDS = [
    "gpu_util_pct",
    "mem_util_pct",
    "mem_used_mb",
    "temperature_c",
    "power_w",
]

SMI_QUERY = (
    "index,name,utilization.gpu,utilization.memory,"
    "memory.used,memory.total,temperature.gpu,power.draw"
)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _parse_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value.strip())
    except (TypeError, ValueError):
        return default


def _query_gpus() -> list[dict[str, Any]]:
    result = subprocess.run(
        [
            "nvidia-smi",
            f"--query-gpu={SMI_QUERY}",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "nvidia-smi 실행 실패")

    rows: list[dict[str, Any]] = []
    for line in result.stdout.strip().splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 8:
            continue
        rows.append(
            {
                "gpu_index": int(_parse_float(parts[0])),
                "gpu_name": parts[1],
                "gpu_util_pct": _parse_float(parts[2]),
                "mem_util_pct": _parse_float(parts[3]),
                "mem_used_mb": _parse_float(parts[4]),
                "mem_total_mb": _parse_float(parts[5]),
                "temperature_c": _parse_float(parts[6]),
                "power_w": _parse_float(parts[7]),
            }
        )
    return rows


def _stat(values: list[float]) -> dict[str, float]:
    if not values:
        return {"min": 0.0, "max": 0.0, "avg": 0.0}
    return {
        "min": round(min(values), 2),
        "max": round(max(values), 2),
        "avg": round(sum(values) / len(values), 2),
    }


def compute_gpu_stats(samples: list[dict[str, Any]]) -> dict[str, Any]:
    by_gpu: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        by_gpu[int(sample["gpu_index"])].append(sample)

    per_gpu: dict[str, Any] = {}
    for gpu_index in sorted(by_gpu):
        gpu_samples = by_gpu[gpu_index]
        gpu_name = gpu_samples[0].get("gpu_name", f"GPU {gpu_index}")
        metrics: dict[str, dict[str, float]] = {}
        for field in STAT_FIELDS:
            metrics[field] = _stat(
                [float(sample[field]) for sample in gpu_samples]
            )
        per_gpu[str(gpu_index)] = {
            "gpu_name": gpu_name,
            "metrics": metrics,
        }

    aggregate: dict[str, dict[str, float]] = {}
    for field in STAT_FIELDS:
        aggregate[field] = _stat([float(sample[field]) for sample in samples])

    return {
        "sample_count": len(samples),
        "gpu_count": len(per_gpu),
        "per_gpu": per_gpu,
        "aggregate": aggregate,
    }


class GpuMonitor:
    """백그라운드에서 GPU 사용량을 CSV에 기록하고 종료 시 통계를 남깁니다."""

    def __init__(
        self,
        *,
        model: str,
        csv_path: Path,
        summary_log_path: Path,
        interval_sec: float = 5.0,
        enabled: bool = True,
    ) -> None:
        self.model = model
        self.csv_path = csv_path
        self.summary_log_path = summary_log_path
        self.interval_sec = interval_sec
        self.enabled = enabled
        self._samples: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._started_at: str | None = None

    def __enter__(self) -> GpuMonitor:
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    def start(self) -> None:
        if not self.enabled:
            return
        self._started_at = _now()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> dict[str, Any] | None:
        if not self.enabled:
            return None

        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval_sec + 5)

        with self._lock:
            samples = list(self._samples)

        if not samples:
            stats = {
                "model": self.model,
                "started_at": self._started_at,
                "finished_at": _now(),
                "interval_sec": self.interval_sec,
                "sample_count": 0,
                "per_gpu": {},
                "aggregate": {},
                "warning": "GPU 샘플 없음 (nvidia-smi 미사용 또는 작업 시간이 너무 짧음)",
            }
            self._write_summary(stats)
            return stats

        stats_body = compute_gpu_stats(samples)
        stats = {
            "model": self.model,
            "started_at": self._started_at,
            "finished_at": _now(),
            "interval_sec": self.interval_sec,
            **stats_body,
        }
        self._write_summary(stats)
        return stats

    def _run_loop(self) -> None:
        self._ensure_csv_header()
        while not self._stop_event.is_set():
            try:
                self._sample_once()
            except Exception as exc:
                self._append_summary_line(f"GPU MONITOR ERROR | model={self.model} | {exc}")
            if self._stop_event.wait(self.interval_sec):
                break

    def _sample_once(self) -> None:
        timestamp = _now()
        gpu_rows = _query_gpus()
        rows: list[dict[str, Any]] = []
        for gpu in gpu_rows:
            row = {
                "timestamp": timestamp,
                "model": self.model,
                **gpu,
            }
            rows.append(row)

        with self._lock:
            self._samples.extend(rows)
        self._append_csv_rows(rows)

    def _ensure_csv_header(self) -> None:
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        if self.csv_path.exists() and self.csv_path.stat().st_size > 0:
            return
        with self.csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            writer.writeheader()

    def _append_csv_rows(self, rows: list[dict[str, Any]]) -> None:
        with self.csv_path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            for row in rows:
                writer.writerow(row)

    def _append_summary_line(self, line: str) -> None:
        self.summary_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.summary_log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{_now()} | {line}\n")

    def _write_summary(self, stats: dict[str, Any]) -> None:
        separator = "=" * 80
        subsep = "-" * 80
        lines = [
            "",
            separator,
            (
                f"GPU SUMMARY | finished={stats.get('finished_at')} | model={stats.get('model')} "
                f"| samples={stats.get('sample_count', 0)} | interval={stats.get('interval_sec')}s"
            ),
            separator,
        ]

        warning = stats.get("warning")
        if warning:
            lines.append(f"WARNING | {warning}")
        else:
            for gpu_index, gpu_info in stats.get("per_gpu", {}).items():
                name = gpu_info.get("gpu_name", "")
                lines.append(f"GPU {gpu_index} ({name})")
                for metric, values in gpu_info.get("metrics", {}).items():
                    lines.append(
                        f"  {metric}: min={values['min']} max={values['max']} avg={values['avg']}"
                    )
            lines.append(subsep)
            lines.append("AGGREGATE (all GPUs, all samples)")
            for metric, values in stats.get("aggregate", {}).items():
                lines.append(
                    f"  {metric}: min={values['min']} max={values['max']} avg={values['avg']}"
                )

        lines.extend([separator, ""])
        text = "\n".join(lines) + "\n"
        self.summary_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.summary_log_path.open("a", encoding="utf-8") as handle:
            handle.write(text)
