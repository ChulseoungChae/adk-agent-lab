import os
import re
from pathlib import Path

from dotenv import load_dotenv

_AGENT_DIR = Path(__file__).resolve().parent
_PROJECT_DIR = _AGENT_DIR.parent
_REPO_ROOT = _PROJECT_DIR.parent

load_dotenv(_REPO_ROOT / ".env")

OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")

COMPARE_MODELS = [
    "gemma4:31b",
    "gemma4:26b",
    "qwen3.6:35b",
    "qwen3-vl:32b",
]

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", COMPARE_MODELS[0])

ASSISTANT_API_BASE = os.getenv(
    "ASSISTANT_API_BASE", "http://bigsoft.iptime.org:10200/api"
).rstrip("/")
PLATFORM_API_BASE = os.getenv(
    "PLATFORM_API_BASE", "http://bigsoft.iptime.org:9301"
).rstrip("/")

RESULTS_REPO = Path(os.getenv("RESULTS_REPO", str(_REPO_ROOT)))

OUTPUT_ROOT = Path(os.getenv("OUTPUT_ROOT", str(_PROJECT_DIR / "output")))
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)


def model_slug(model: str) -> str:
    slug = re.sub(r"[^\w]+", "_", model).strip("_")
    return slug or "default"


def output_dir_for_model(model: str) -> Path:
    return OUTPUT_ROOT / model_slug(model)


_active_subdir = os.getenv("BOOK_OUTPUT_SUBDIR") or model_slug(OLLAMA_MODEL)

BOOK_OUTPUT_DIR = Path(
    os.getenv("BOOK_OUTPUT_DIR", str(OUTPUT_ROOT / _active_subdir))
)
BOOK_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTLINE_PATH = BOOK_OUTPUT_DIR / "outline.json"
METADATA_PATH = BOOK_OUTPUT_DIR / "book_metadata.json"
CHAPTERS_DIR = BOOK_OUTPUT_DIR / "chapters"
CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = OUTPUT_ROOT / "agent.log"
GPU_CSV_PATH = OUTPUT_ROOT / "gpu_usage.csv"
GPU_SUMMARY_LOG_PATH = OUTPUT_ROOT / "gpu_usage_summary.log"
GPU_MONITOR_ENABLED = os.getenv("GPU_MONITOR_ENABLED", "1") == "1"
GPU_MONITOR_INTERVAL_SEC = float(os.getenv("GPU_MONITOR_INTERVAL_SEC", "5"))

PROJECT_ID = _PROJECT_DIR.name
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "30"))
AUTO_SYNC_RESULTS = os.getenv("AUTO_SYNC_RESULTS", "1") == "1"
AUTO_PUSH_RESULTS = os.getenv("AUTO_PUSH_RESULTS", "1") == "1"
GIT_REMOTE = os.getenv("GIT_REMOTE", "origin")
