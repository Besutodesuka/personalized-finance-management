"""Central config — env vars and paths in one place."""
import os
from pathlib import Path

# DATA_DIR defaults to /app/data (docker). Override for local dev: DATA_DIR=./data
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "expense.db"

VLLM_URL = os.getenv("VLLM_URL", "http://ollama:11434")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5:3b")
# Ask the model to emit its reasoning ("thinking") so the UI can stream it.
# Only thinking-capable models support this; set CHAT_THINK=false otherwise.
CHAT_THINK = os.getenv("CHAT_THINK", "true").lower() in ("1", "true", "yes")
