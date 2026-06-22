"""순수 Python(pandas) 통계 엔진 — LLM이 아닌 결정론적 계산."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def _human_file_size(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    size = float(size_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size_bytes} B"


def _format_timedelta(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}초"
    if seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}분"
    hours = seconds / 3600
    return f"{hours:.2f}시간"


def _analyze_datetime_interval(series: pd.Series) -> dict[str, Any] | None:
    valid = series.dropna().sort_values()
    if len(valid) < 2:
        return None

    deltas = valid.diff().dropna()
    if deltas.empty:
        return None

    median_sec = float(deltas.median().total_seconds())
    mean_sec = float(deltas.mean().total_seconds())
    min_sec = float(deltas.min().total_seconds())
    max_sec = float(deltas.max().total_seconds())

    return {
        "sample_count": int(len(deltas)),
        "median_interval_sec": round(median_sec, 2),
        "median_interval_human": _format_timedelta(median_sec),
        "mean_interval_sec": round(mean_sec, 2),
        "mean_interval_human": _format_timedelta(mean_sec),
        "min_interval_sec": round(min_sec, 2),
        "max_interval_sec": round(max_sec, 2),
        "inferred_frequency": _format_timedelta(median_sec),
    }


def _json_safe(value: Any) -> Any:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, AttributeError):
            pass
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def profile_dataframe(
    df: pd.DataFrame,
    *,
    data_path: Path | str | None = None,
) -> dict[str, Any]:
    row_count, col_count = df.shape
    columns: list[dict[str, Any]] = []

    for name in df.columns:
        series = df[name]
        dtype = str(series.dtype)
        missing = int(series.isna().sum())
        missing_pct = round(missing / row_count * 100, 2) if row_count else 0.0
        unique = int(series.nunique(dropna=True))
        col_info: dict[str, Any] = {
            "name": str(name),
            "dtype": dtype,
            "missing_count": missing,
            "missing_pct": missing_pct,
            "unique_count": unique,
        }

        if pd.api.types.is_numeric_dtype(series):
            desc = series.describe()
            col_info["kind"] = "numeric"
            col_info["stats"] = _json_safe(desc.to_dict())
        elif pd.api.types.is_datetime64_any_dtype(series):
            col_info["kind"] = "datetime"
            valid = series.dropna()
            if not valid.empty:
                col_info["min"] = _json_safe(valid.min())
                col_info["max"] = _json_safe(valid.max())
            interval = _analyze_datetime_interval(series)
            if interval:
                col_info["interval"] = interval
        else:
            col_info["kind"] = "categorical"
            counts = series.value_counts(dropna=False)
            top = counts.head(5)
            col_info["top_values"] = _json_safe(top.to_dict())
            col_info["value_distribution"] = _json_safe(counts.head(20).to_dict())
            col_info["category_count"] = int(counts.shape[0])

        columns.append(col_info)

    numeric_cols = [c["name"] for c in columns if c.get("kind") == "numeric"]
    datetime_cols = [c["name"] for c in columns if c.get("kind") == "datetime"]
    categorical_cols = [c["name"] for c in columns if c.get("kind") == "categorical"]

    hints: list[str] = []
    if datetime_cols:
        hints.append("datetime_column_detected")
    if len(numeric_cols) >= 2:
        hints.append("correlation_analysis_available")
    if categorical_cols and numeric_cols:
        hints.append("groupby_analysis_available")
    if any(c["missing_pct"] > 10 for c in columns):
        hints.append("high_missing_values")

    profile: dict[str, Any] = {
        "row_count": row_count,
        "column_count": col_count,
        "columns": columns,
        "numeric_columns": numeric_cols,
        "datetime_columns": datetime_cols,
        "categorical_columns": categorical_cols,
        "analysis_hints": hints,
    }

    if data_path:
        path = Path(data_path)
        if path.exists():
            size_bytes = path.stat().st_size
            profile["file_info"] = {
                "path": str(path.resolve()),
                "name": path.name,
                "size_bytes": size_bytes,
                "size_human": _human_file_size(size_bytes),
            }

    datetime_intervals: dict[str, Any] = {}
    for col in datetime_cols:
        interval = _analyze_datetime_interval(df[col])
        if interval:
            datetime_intervals[col] = interval
    if datetime_intervals:
        profile["datetime_intervals"] = datetime_intervals
        primary = datetime_cols[0]
        profile["data_period"] = {
            "column": primary,
            **datetime_intervals[primary],
        }

    if categorical_cols:
        profile["categorical_breakdown"] = {
            col["name"]: {
                "unique_count": col.get("unique_count", 0),
                "category_count": col.get("category_count", 0),
                "top_values": col.get("top_values", {}),
                "value_distribution": col.get("value_distribution", {}),
            }
            for col in columns
            if col.get("kind") == "categorical"
        }

    return profile


def descriptive_stats(df: pd.DataFrame, columns: list[str] | None = None) -> dict[str, Any]:
    if columns:
        missing = [c for c in columns if c not in df.columns]
        if missing:
            raise ValueError(f"존재하지 않는 컬럼: {missing}")
        target = df[columns]
    else:
        target = df.select_dtypes(include="number")

    if target.empty:
        return {"error": "수치형 컬럼이 없습니다.", "columns": []}

    desc = target.describe().transpose()
    result: dict[str, Any] = {}
    for col_name, row in desc.iterrows():
        result[str(col_name)] = _json_safe(row.to_dict())
    return {"columns": list(result.keys()), "statistics": result}


def correlation_matrix(df: pd.DataFrame, columns: list[str] | None = None) -> dict[str, Any]:
    if columns:
        missing = [c for c in columns if c not in df.columns]
        if missing:
            raise ValueError(f"존재하지 않는 컬럼: {missing}")
        target = df[columns].select_dtypes(include="number")
    else:
        target = df.select_dtypes(include="number")

    if target.shape[1] < 2:
        return {"error": "상관 분석에 필요한 수치형 컬럼이 2개 미만입니다."}

    corr = target.corr(numeric_only=True).round(4)
    return {
        "columns": list(corr.columns),
        "matrix": _json_safe(corr.to_dict()),
    }


def groupby_stats(
    df: pd.DataFrame,
    group_by: str,
    value_columns: list[str],
    agg: str = "mean",
) -> dict[str, Any]:
    if group_by not in df.columns:
        raise ValueError(f"존재하지 않는 group_by 컬럼: {group_by}")

    allowed_agg = {"mean", "sum", "count", "std", "min", "max", "median"}
    if agg not in allowed_agg:
        raise ValueError(f"지원하지 않는 agg: {agg}. 허용: {sorted(allowed_agg)}")

    missing = [c for c in value_columns if c not in df.columns]
    if missing:
        raise ValueError(f"존재하지 않는 value 컬럼: {missing}")

    grouped = df.groupby(group_by, dropna=False)[value_columns]
    if agg == "count":
        result_df = grouped.count()
    elif agg == "mean":
        result_df = grouped.mean(numeric_only=True)
    elif agg == "sum":
        result_df = grouped.sum(numeric_only=True)
    elif agg == "std":
        result_df = grouped.std(numeric_only=True)
    elif agg == "min":
        result_df = grouped.min(numeric_only=True)
    elif agg == "max":
        result_df = grouped.max(numeric_only=True)
    else:
        result_df = grouped.median(numeric_only=True)

    result_df = result_df.round(4)
    return {
        "group_by": group_by,
        "value_columns": value_columns,
        "agg": agg,
        "group_count": int(result_df.shape[0]),
        "data": _json_safe(result_df.reset_index().to_dict(orient="records")),
    }


def categorical_summary(df: pd.DataFrame, columns: list[str]) -> dict[str, Any]:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"존재하지 않는 컬럼: {missing}")

    summaries: dict[str, Any] = {}
    for col in columns:
        counts = df[col].value_counts(dropna=False).head(20)
        summaries[col] = {
            "unique_count": int(df[col].nunique(dropna=True)),
            "top_values": _json_safe(counts.to_dict()),
        }
    return {"columns": columns, "summaries": summaries}


def detect_outliers_iqr(df: pd.DataFrame, column: str) -> dict[str, Any]:
    if column not in df.columns:
        raise ValueError(f"존재하지 않는 컬럼: {column}")
    if not pd.api.types.is_numeric_dtype(df[column]):
        raise ValueError(f"수치형 컬럼이 아닙니다: {column}")

    series = df[column].dropna()
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    mask = (df[column] < lower) | (df[column] > upper)
    outlier_count = int(mask.sum())

    return {
        "column": column,
        "method": "iqr",
        "q1": _json_safe(q1),
        "q3": _json_safe(q3),
        "iqr": _json_safe(iqr),
        "lower_bound": _json_safe(lower),
        "upper_bound": _json_safe(upper),
        "outlier_count": outlier_count,
        "outlier_pct": round(outlier_count / len(df) * 100, 2) if len(df) else 0.0,
    }
