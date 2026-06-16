import os
from pathlib import Path

from dotenv import load_dotenv

_AGENT_DIR = Path(__file__).resolve().parent
_AGENT_ID = _AGENT_DIR.name
_REPO_ROOT = _AGENT_DIR.parents[1]

load_dotenv(_REPO_ROOT / ".env")

OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:26b")

ASSISTANT_API_BASE = os.getenv(
    "ASSISTANT_API_BASE", "http://bigsoft.iptime.org:10200/api"
).rstrip("/")
PLATFORM_API_BASE = os.getenv(
    "PLATFORM_API_BASE", "http://bigsoft.iptime.org:9301"
).rstrip("/")

RESULTS_REPO = Path(os.getenv("RESULTS_REPO", str(_REPO_ROOT)))

BOOK_OUTPUT_DIR = Path(
    os.getenv("BOOK_OUTPUT_DIR", str(_REPO_ROOT / "output" / _AGENT_ID))
)
BOOK_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTLINE_PATH = BOOK_OUTPUT_DIR / "outline.json"
METADATA_PATH = BOOK_OUTPUT_DIR / "book_metadata.json"
CHAPTERS_DIR = BOOK_OUTPUT_DIR / "chapters"
CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = BOOK_OUTPUT_DIR / "agent.log"

AGENT_ID = _AGENT_ID
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "30"))
AUTO_SYNC_RESULTS = os.getenv("AUTO_SYNC_RESULTS", "1") == "1"
AUTO_PUSH_RESULTS = os.getenv("AUTO_PUSH_RESULTS", "1") == "1"
GIT_REMOTE = os.getenv("GIT_REMOTE", "origin")
