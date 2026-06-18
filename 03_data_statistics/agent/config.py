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
LITELLM_TIMEOUT_SEC = int(os.getenv("LITELLM_TIMEOUT_SEC", "1800"))
MODEL_SWITCH_DELAY_SEC = float(os.getenv("MODEL_SWITCH_DELAY_SEC", "20"))
MODEL_RUN_MAX_RETRIES = int(os.getenv("MODEL_RUN_MAX_RETRIES", "2"))
ADK_MAX_ROUNDS = int(os.getenv("ADK_MAX_ROUNDS", "8"))

DATA_DIR = Path(os.getenv("DATA_DIR", str(_PROJECT_DIR / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_DATA_PATH = Path(
    os.getenv("DEFAULT_DATA_PATH", str(DATA_DIR / "sample_sensor.csv"))
)

RESULTS_REPO = Path(os.getenv("RESULTS_REPO", str(_REPO_ROOT)))

OUTPUT_ROOT = Path(os.getenv("OUTPUT_ROOT", str(_PROJECT_DIR / "output")))
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)


def model_slug(model: str) -> str:
    slug = re.sub(r"[^\w]+", "_", model).strip("_")
    return slug or "default"


def output_dir_for_model(model: str) -> Path:
    return OUTPUT_ROOT / model_slug(model)


_active_subdir = os.getenv("STATS_OUTPUT_SUBDIR") or model_slug(OLLAMA_MODEL)

OUTPUT_DIR = Path(
    os.getenv("STATS_OUTPUT_DIR", str(OUTPUT_ROOT / _active_subdir))
)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PROFILE_PATH = OUTPUT_DIR / "profile.json"
STATISTICS_PATH = OUTPUT_DIR / "statistics.json"
REPORT_PATH = OUTPUT_DIR / "report.md"
METADATA_PATH = OUTPUT_DIR / "analysis_metadata.json"
VALIDATION_PATH = OUTPUT_DIR / "validation.json"
CHARTS_DIR = OUTPUT_DIR / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

LOG_PATH = OUTPUT_ROOT / "agent.log"
GPU_CSV_PATH = OUTPUT_ROOT / "gpu_usage.csv"
GPU_SUMMARY_LOG_PATH = OUTPUT_ROOT / "gpu_usage_summary.log"
OUTPUT_README_PATH = OUTPUT_ROOT / "README.md"
COMPARISON_SUMMARY_PATH = OUTPUT_ROOT / "comparison_summary.json"
COMPARE_CHARTS_DIR = OUTPUT_ROOT / "charts"

GPU_MONITOR_ENABLED = os.getenv("GPU_MONITOR_ENABLED", "1") == "1"
GPU_MONITOR_INTERVAL_SEC = float(os.getenv("GPU_MONITOR_INTERVAL_SEC", "5"))

PROJECT_ID = _PROJECT_DIR.name
AUTO_SYNC_RESULTS = os.getenv("AUTO_SYNC_RESULTS", "1") == "1"
AUTO_PUSH_RESULTS = os.getenv("AUTO_PUSH_RESULTS", "1") == "1"
GIT_REMOTE = os.getenv("GIT_REMOTE", "origin")
