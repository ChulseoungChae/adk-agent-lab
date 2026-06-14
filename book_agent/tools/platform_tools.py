"""반도체 AI 어시스턴트 플랫폼(http://bigsoft.iptime.org:10200) 연동 도구."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

import requests

from book_agent.config import ASSISTANT_API_BASE, HTTP_TIMEOUT, PLATFORM_API_BASE


def _get(url: str, params: dict | None = None) -> Any:
    response = requests.get(url, params=params, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    return response.json()


def _post(url: str, payload: dict) -> Any:
    response = requests.post(url, json=payload, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    return response.json()


def _truncate(items: list, limit: int = 20) -> dict:
    return {
        "total": len(items),
        "shown": min(len(items), limit),
        "items": items[:limit],
    }


def fetch_anomaly_logs(limit: int = 20) -> dict:
    """실시간 이상감지 로그를 조회합니다.

    반도체 AI 어시스턴트 플랫폼의 실시간 이상감지(index4) 데이터를 가져옵니다.
    책의 '이상 사례' 챕터나 공정 분석 장에 활용할 수 있습니다.

    Args:
        limit: 반환할 최대 로그 수 (기본 20).

    Returns:
        이상감지 로그 목록과 요약 정보.
    """
    logs = _get(f"{ASSISTANT_API_BASE}/platform/anomaly-logs")
    if not isinstance(logs, list):
        return {"error": "예상치 못한 응답 형식", "raw": logs}
    return _truncate(logs, limit)


def fetch_prediction_logs(limit: int = 20) -> dict:
    """예측 기반 이상감지 로그를 조회합니다.

    PatchTST 등 예측 모델의 예측값 대비 실제값 이상 기록을 가져옵니다.

    Args:
        limit: 반환할 최대 로그 수 (기본 20).

    Returns:
        예측 이상 로그 목록.
    """
    logs = _get(f"{ASSISTANT_API_BASE}/platform/prediction-logs")
    if not isinstance(logs, list):
        return {"error": "예상치 못한 응답 형식", "raw": logs}
    return _truncate(logs, limit)


def fetch_equipment_history(
    process_recipe: str = "",
    limit: int = 30,
) -> dict:
    """과거 공정 이력(equipment_history)을 검색합니다.

    공정 레시피별 PJOB 이력, 시작/종료 시간, 종료 상태를 조회합니다.
    책의 '공정 이력' 또는 '케이스 스터디' 챕터에 활용하세요.

    Args:
        process_recipe: 필터할 레시피명. 빈 문자열이면 전체 조회.
        limit: 반환할 최대 건수.

    Returns:
        공정 이력 목록.
    """
    params = {}
    if process_recipe and process_recipe != "전체":
        params["process_recipe"] = process_recipe
    history = _get(f"{PLATFORM_API_BASE}/api/equipment_history", params=params)
    if not isinstance(history, list):
        return {"error": "예상치 못한 응답 형식", "raw": history}
    return _truncate(history, limit)


def search_process_recipes() -> dict:
    """등록된 공정 레시피 목록을 조회합니다.

    과거 공정 이력 검색 전에 사용 가능한 레시피 이름을 확인합니다.

    Returns:
        레시피 이름 목록.
    """
    recipes = _get(f"{PLATFORM_API_BASE}/api/equipment_history/recipes")
    return {"recipes": recipes}


def fetch_generator_status() -> dict:
    """데이터 생성기(공정 데이터 수집) 상태를 확인합니다.

    장비가 RUN 상태인지, 마지막 데이터 수집 시각 등을 확인합니다.

    Returns:
        생성기 상태 정보.
    """
    return _get(f"{PLATFORM_API_BASE}/api/generator_status")


def list_platform_reports(limit: int = 10) -> dict:
    """플랫폼에 저장된 일/월간 리포트 목록을 조회합니다.

    이상감지 집계 리포트를 책의 '통계·트렌드' 챕터에 인용할 수 있습니다.

    Args:
        limit: 반환할 최대 리포트 수.

    Returns:
        리포트 메타데이터 목록.
    """
    data = _get(f"{ASSISTANT_API_BASE}/reports")
    reports = data.get("reports", []) if isinstance(data, dict) else []
    return _truncate(reports, limit)


def get_report_content(report_id: str) -> dict:
    """특정 리포트의 전체 내용을 조회합니다.

    Args:
        report_id: 리포트 ID (예: report_monthly_2026-01).

    Returns:
        리포트 제목, 기간, 이상감지 통계 등 전체 JSON.
    """
    return _get(f"{ASSISTANT_API_BASE}/reports/{report_id}/content")


def create_platform_report(
    report_type: str = "daily",
    days_ago: int = 1,
) -> dict:
    """플랫폼에서 새 이상감지 리포트를 생성합니다.

    Args:
        report_type: 'daily' 또는 'monthly'.
        days_ago: daily일 때 며칠 전 리포트를 생성할지 (기본 1=어제).

    Returns:
        생성된 리포트 메타데이터.
    """
    end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0)
    if report_type == "monthly":
        start = end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start = (end - timedelta(days=days_ago)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end = start.replace(hour=23, minute=59, second=59)

    payload = {
        "report_type": report_type,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
    }
    return _post(f"{ASSISTANT_API_BASE}/reports", payload)
