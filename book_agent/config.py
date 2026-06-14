import os
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_REPO_ROOT / ".env")

OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:26b")

ASSISTANT_API_BASE = os.getenv(
    "ASSISTANT_API_BASE", "http://bigsoft.iptime.org:10200/api"
).rstrip("/")
PLATFORM_API_BASE = os.getenv(
    "PLATFORM_API_BASE", "http://bigsoft.iptime.org:9301"
).rstrip("/")

BOOK_OUTPUT_DIR = Path(
    os.getenv("BOOK_OUTPUT_DIR", str(_REPO_ROOT / "output"))
)
BOOK_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTLINE_PATH = BOOK_OUTPUT_DIR / "outline.json"
METADATA_PATH = BOOK_OUTPUT_DIR / "book_metadata.json"
CHAPTERS_DIR = BOOK_OUTPUT_DIR / "chapters"
CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)

HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "30"))
