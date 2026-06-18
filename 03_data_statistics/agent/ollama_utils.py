"""Ollama 모델 언로드 — 모델 전환 시 VRAM 확보."""

from __future__ import annotations

import subprocess
import time

from .config import MODEL_SWITCH_DELAY_SEC
from .session_log import log_event


def list_running_models() -> list[str]:
    result = subprocess.run(
        ["ollama", "ps"],
        capture_output=True,
        text=True,
        check=False,
    )
    models: list[str] = []
    for line in result.stdout.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        models.append(line.split()[0])
    return models


def stop_model(model: str) -> bool:
    result = subprocess.run(
        ["ollama", "stop", model],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def unload_all_models(*, delay_sec: float | None = None) -> list[str]:
    """실행 중인 Ollama 모델을 모두 언로드합니다."""
    running = list_running_models()
    if not running:
        return []

    stopped: list[str] = []
    for model in running:
        if stop_model(model):
            stopped.append(model)

    wait = MODEL_SWITCH_DELAY_SEC if delay_sec is None else delay_sec
    if stopped and wait > 0:
        log_event(f"OLLAMA   | unloaded {stopped}, waiting {wait}s for VRAM")
        time.sleep(wait)
    return stopped


def prepare_for_model(model: str) -> None:
    """다음 모델 실행 전 VRAM을 비웁니다."""
    stopped = unload_all_models()
    if not stopped:
        log_event(f"OLLAMA   | prepare {model} (no models were running)")
