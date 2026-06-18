"""순수 Python(pandas) 통계 엔진 — LLM이 아닌 결정론적 계산."""

from __future__ import annotations

from typing import Any

import pandas as pd


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


def profile_dataframe(df: pd.DataFrame) -> dict[str, Any]:
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
        else:
            col_info["kind"] = "categorical"
            top = series.value_counts(dropna=True).head(5)
            col_info["top_values"] = _json_safe(top.to_dict())

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

    return {
        "row_count": row_count,
        "column_count": col_count,
        "columns": columns,
        "numeric_columns": numeric_cols,
        "datetime_columns": datetime_cols,
        "categorical_columns": categorical_cols,
        "analysis_hints": hints,
    }


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
