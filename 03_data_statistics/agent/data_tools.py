"""데이터 로드·프로파일 ADK Tools."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .config import DATA_DIR, DEFAULT_DATA_PATH, PROFILE_PATH
from .session_log import log_tool
from . import stats_engine

_df: pd.DataFrame | None = None
_data_path: Path | None = None


def _load_frame_from_path(resolved: Path) -> pd.DataFrame:
    suffix = resolved.suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(resolved)
    elif suffix in (".json", ".jsonl"):
        frame = pd.read_json(resolved)
    else:
        raise ValueError(f"지원하지 않는 형식: {suffix} (csv, json만 지원)")

    for col in frame.columns:
        if "time" in str(col).lower() or "date" in str(col).lower():
            try:
                frame[col] = pd.to_datetime(frame[col])
            except (ValueError, TypeError):
                pass
    return frame


def reload_data_if_needed() -> bool:
    """ADK 새 라운드에서 메모리가 비었을 때 profile/default 경로로 자동 재로드."""
    global _df, _data_path
    if _df is not None:
        return True

    resolved = DEFAULT_DATA_PATH.resolve()
    if PROFILE_PATH.exists():
        profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        raw = profile.get("data_path")
        if raw:
            candidate = Path(str(raw)).expanduser()
            if candidate.exists():
                resolved = candidate.resolve()

    if not resolved.exists():
        return False

    _df = _load_frame_from_path(resolved)
    _data_path = resolved
    return True


def reload_data_for_output(output_dir: Path) -> bool:
    """지정 output 폴더의 profile.json 기준으로 데이터를 재로드합니다."""
    global _df, _data_path
    resolved = DEFAULT_DATA_PATH.resolve()
    profile_path = output_dir / "profile.json"
    if profile_path.exists():
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        raw = profile.get("data_path")
        if raw:
            candidate = Path(str(raw)).expanduser()
            if candidate.exists():
                resolved = candidate.resolve()
    if not resolved.exists():
        return False
    _df = _load_frame_from_path(resolved)
    _data_path = resolved
    return True


def _require_dataframe() -> pd.DataFrame:
    if not reload_data_if_needed():
        raise RuntimeError("데이터가 로드되지 않았습니다. 먼저 load_data를 호출하세요.")
    assert _df is not None
    return _df


def _resolve_path(path: str) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = DATA_DIR / candidate
    return candidate.resolve()


def get_loaded_dataframe() -> pd.DataFrame | None:
    return _df


def get_data_path() -> Path | None:
    return _data_path


@log_tool("load_data")
def load_data(path: str = "") -> dict[str, Any]:
    """CSV 데이터를 메모리에 로드합니다.

    path가 비어 있으면 기본 샘플 데이터를 사용합니다.
    상대 경로는 프로젝트 data/ 폴더 기준입니다.

    Args:
        path: CSV 파일 경로. 예: "sample_sensor.csv" 또는 절대 경로.

    Returns:
        행·열 수, 컬럼 목록, 데이터 경로.
    """
    global _df, _data_path

    resolved = _resolve_path(path) if path.strip() else DEFAULT_DATA_PATH.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"데이터 파일 없음: {resolved}")

    frame = _load_frame_from_path(resolved)

    _df = frame
    _data_path = resolved

    return {
        "status": "loaded",
        "path": str(resolved),
        "row_count": int(frame.shape[0]),
        "column_count": int(frame.shape[1]),
        "columns": [str(c) for c in frame.columns],
    }


@log_tool("sample_rows")
def sample_rows(n: int = 5) -> dict[str, Any]:
    """로드된 데이터의 앞부분 샘플 행을 반환합니다.

    Args:
        n: 반환할 행 수 (기본 5).

    Returns:
        샘플 행 목록.
    """
    frame = _require_dataframe()
    n = max(1, min(n, 20))
    sample = frame.head(n)
    return {
        "row_count": int(frame.shape[0]),
        "sample_count": n,
        "rows": json.loads(sample.to_json(orient="records", date_format="iso")),
    }


@log_tool("profile_data")
def profile_data() -> dict[str, Any]:
    """로드된 데이터의 구조·결측·dtype·기본 통계를 자동 진단합니다.

    결과는 output/profile.json에도 저장됩니다.
    이후 어떤 통계 Tool을 호출할지 계획할 때 반드시 참고하세요.

    Returns:
        프로파일 요약 (컬럼별 kind, 결측률, analysis_hints).
    """
    frame = _require_dataframe()
    profile = stats_engine.profile_dataframe(frame)
    profile["data_path"] = str(_data_path) if _data_path else None
    profile["profiled_at"] = datetime.now().isoformat()

    PROFILE_PATH.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "status": "profiled",
        "path": str(PROFILE_PATH),
        "row_count": profile["row_count"],
        "column_count": profile["column_count"],
        "numeric_columns": profile["numeric_columns"],
        "datetime_columns": profile["datetime_columns"],
        "categorical_columns": profile["categorical_columns"],
        "analysis_hints": profile["analysis_hints"],
        "columns": profile["columns"],
    }
