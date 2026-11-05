"""Central configuration. Override any value with an environment variable."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"

# ---- Local English chat model (understands questions, handles follow-ups) ----
# Default: small, Apache-2.0 licensed, fits in ~3 GB RAM (bfloat16).
# Upgrade options (need more RAM): "Qwen/Qwen2.5-3B-Instruct" (~6 GB),
#                                  "Qwen/Qwen2.5-7B-Instruct" (~15 GB, or use a GPU)
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "Qwen/Qwen2.5-1.5B-Instruct")
LLM_LOCAL_DIR = Path(os.getenv("LLM_LOCAL_DIR", MODELS_DIR / "llm"))
LLM_DTYPE = os.getenv("LLM_DTYPE", "bfloat16")  # "float32" if bfloat16 errors/slow on your CPU
LLM_MAX_NEW_TOKENS = int(os.getenv("LLM_MAX_NEW_TOKENS", "150"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.4"))

# ---- Local English -> Dzongkha translation model (NLLB-200, code dzo_Tibt) ----
# LICENCE: CC-BY-NC 4.0 (non-commercial). Fine for a student/learning project.
# Larger option: "facebook/nllb-200-distilled-1.3B" (~5 GB RAM, better quality)
TRANSLATOR_MODEL_NAME = os.getenv("TRANSLATOR_MODEL_NAME", "facebook/nllb-200-distilled-600M")
TRANSLATOR_LOCAL_DIR = Path(os.getenv("TRANSLATOR_LOCAL_DIR", MODELS_DIR / "translator"))
TRANSLATOR_SRC_LANG = "eng_Latn"
TRANSLATOR_TGT_LANG = "dzo_Tibt"
TRANSLATOR_NUM_BEAMS = int(os.getenv("TRANSLATOR_NUM_BEAMS", "4"))
TRANSLATOR_MAX_NEW_TOKENS = 200

# ---- Conversation limits (keep prompts inside the model's context window) ----
MAX_INPUT_CHARS = 500
MAX_HISTORY_TURNS = 6          # last N user+assistant exchanges
MAX_HISTORY_CHARS = 3000       # hard character budget for history
MAX_SENTENCES_TO_TRANSLATE = 6

# Minimum share of Tibetan-script characters a reply must contain to count as Dzongkha
MIN_TIBETAN_RATIO = 0.6

# ---- Server ----
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "5000"))
DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"

SYSTEM_PROMPT = (
    "You are a friendly, helpful assistant. Your reply will be machine-translated "
    "into Dzongkha, so write in plain, simple English: 1 to 3 short sentences, "
    "no slang, no idioms, no markdown, no lists, no emojis. If you do not know "
    "something, say so briefly. Use the earlier conversation to understand follow-up questions."
)
