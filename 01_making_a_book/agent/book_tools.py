"""책 작성·저장 도구."""

from __future__ import annotations

import json
import logging
import re
import subprocess
from datetime import datetime
from typing import Any

from .config import (
    AUTO_PUSH_RESULTS,
    AUTO_SYNC_RESULTS,
    BOOK_OUTPUT_DIR,
    CHAPTERS_DIR,
    GIT_REMOTE,
    METADATA_PATH,
    OUTLINE_PATH,
    RESULTS_REPO,
)
from .session_log import log_event, log_tool


def _slugify(title: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", title, flags=re.UNICODE)
    slug = re.sub(r"[-\s]+", "_", slug.strip())
    return slug[:60] or "chapter"


def _current_branch() -> str:
    result = subprocess.run(
        ["git", "-C", str(RESULTS_REPO), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or "main"


def _git_output_path() -> str:
    return str(BOOK_OUTPUT_DIR.relative_to(RESULTS_REPO))


def sync_results(message: str = "Update book output") -> dict:
    """책 결과물(output/)을 커밋하고 원격 GitHub에 push합니다."""
    if not (RESULTS_REPO / ".git").is_dir():
        result = {"synced": False, "error": f"Git 레포 없음: {RESULTS_REPO}"}
        log_event(f"SYNC SKIP | {result['error']}", level=logging.ERROR)
        return result

    git_output = _git_output_path()
    status = subprocess.run(
        ["git", "-C", str(RESULTS_REPO), "status", "--porcelain", git_output],
        capture_output=True,
        text=True,
        check=False,
    )
    if not status.stdout.strip():
        result = {"synced": False, "message": "커밋할 변경사항 없음"}
        log_event("SYNC SKIP | 변경사항 없음")
        return result

    subprocess.run(
        ["git", "-C", str(RESULTS_REPO), "add", git_output],
        check=True,
    )
    commit = subprocess.run(
        ["git", "-C", str(RESULTS_REPO), "commit", "-m", message],
        capture_output=True,
        text=True,
        check=False,
    )
    if commit.returncode != 0:
        result = {
            "synced": False,
            "message": message,
            "stderr": commit.stderr.strip(),
        }
        log_event(f"SYNC FAIL | commit: {commit.stderr.strip()}", level=logging.ERROR)
        return result

    log_event(f"SYNC OK   | commit: {message}")
    result: dict[str, Any] = {
        "synced": True,
        "message": message,
        "stdout": commit.stdout.strip(),
        "pushed": False,
    }

    if AUTO_PUSH_RESULTS:
        branch = _current_branch()
        push = subprocess.run(
            ["git", "-C", str(RESULTS_REPO), "push", GIT_REMOTE, branch],
            capture_output=True,
            text=True,
            check=False,
        )
        if push.returncode == 0:
            result["pushed"] = True
            result["push_stdout"] = push.stdout.strip()
            log_event(f"PUSH OK   | {GIT_REMOTE}/{branch}")
        else:
            result["push_error"] = push.stderr.strip() or push.stdout.strip()
            log_event(f"PUSH FAIL | {result['push_error']}", level=logging.ERROR)

    return result


def _sync_results(message: str) -> dict | None:
    if not AUTO_SYNC_RESULTS:
        return None
    result = sync_results(message)
    return result if result.get("synced") else None


@log_tool("save_book_metadata")
def save_book_metadata(
    title: str,
    subtitle: str = "",
    audience: str = "",
    theme: str = "",
) -> dict:
    """책 메타데이터(제목, 부제, 독자층, 주제)를 저장합니다.

    책 작성을 시작하기 전에 반드시 호출하세요.
    title, subtitle, audience, theme는 모두 **한국어**로 작성하세요.

    Args:
        title: 책 제목 (한국어).
        subtitle: 부제목 (한국어).
        audience: 대상 독자 (한국어, 예: 반도체 공정 엔지니어).
        theme: 핵심 주제 (한국어).

    Returns:
        저장된 메타데이터.
    """
    metadata = {
        "title": title,
        "subtitle": subtitle,
        "audience": audience,
        "theme": theme,
        "updated_at": datetime.now().isoformat(),
    }
    METADATA_PATH.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    result = {"status": "saved", "path": str(METADATA_PATH), "metadata": metadata}
    sync = _sync_results(f"Update book metadata: {title}")
    if sync:
        result["git_sync"] = sync
    return result


@log_tool("save_outline")
def save_outline(chapters: list[dict[str, Any]]) -> dict:
    """책 목차를 JSON으로 저장합니다.

    chapters의 title, summary는 모두 **한국어**로 작성하세요.

    Args:
        chapters: 챕터 목록. 각 항목은 title, summary 키를 포함해야 합니다.
            예: [{"number": 1, "title": "서론", "summary": "..."}]

    Returns:
        저장 결과와 경로.
    """
    outline = {
        "chapters": chapters,
        "updated_at": datetime.now().isoformat(),
    }
    OUTLINE_PATH.write_text(
        json.dumps(outline, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    result = {
        "status": "saved",
        "path": str(OUTLINE_PATH),
        "chapter_count": len(chapters),
    }
    sync = _sync_results(f"Update outline ({len(chapters)} chapters)")
    if sync:
        result["git_sync"] = sync
    return result


@log_tool("write_chapter")
def write_chapter(chapter_number: int, title: str, content: str) -> dict:
    """챕터 본문을 Markdown 파일로 저장합니다.

    title과 content는 **한국어**로 작성하세요.

    Args:
        chapter_number: 챕터 번호 (1부터).
        title: 챕터 제목 (한국어).
        content: 챕터 본문 Markdown (한국어).

    Returns:
        저장된 파일 경로.
    """
    slug = _slugify(title)
    filename = f"{chapter_number:02d}_{slug}.md"
    path = CHAPTERS_DIR / filename

    header = f"# {chapter_number}. {title}\n\n"
    path.write_text(header + content.strip() + "\n", encoding="utf-8")

    result = {
        "status": "saved",
        "path": str(path),
        "chapter_number": chapter_number,
        "title": title,
        "char_count": len(content),
    }
    sync = _sync_results(f"Add chapter {chapter_number}: {title}")
    if sync:
        result["git_sync"] = sync
    return result


@log_tool("read_book_state")
def read_book_state() -> dict:
    """현재까지 작성된 책 상태(메타데이터, 목차, 챕터 목록)를 읽습니다.

    Returns:
        메타데이터, 목차, 저장된 챕터 파일 목록.
    """
    state: dict[str, Any] = {
        "metadata": None,
        "outline": None,
        "chapters": [],
    }

    if METADATA_PATH.exists():
        state["metadata"] = json.loads(METADATA_PATH.read_text(encoding="utf-8"))

    if OUTLINE_PATH.exists():
        state["outline"] = json.loads(OUTLINE_PATH.read_text(encoding="utf-8"))

    for chapter_file in sorted(CHAPTERS_DIR.glob("*.md")):
        state["chapters"].append(
            {
                "filename": chapter_file.name,
                "path": str(chapter_file),
                "size_bytes": chapter_file.stat().st_size,
            }
        )

    return state
