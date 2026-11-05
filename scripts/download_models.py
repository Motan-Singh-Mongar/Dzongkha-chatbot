"""Download both models into ./models (needs internet ONCE). Run: python scripts/download_models.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from huggingface_hub import snapshot_download  # noqa: E402

IGNORE = ["*.msgpack", "*.h5", "*.ot", "*.onnx", "*.tflite", "original/*", "*.gguf"]


def fetch(name, target):
    print(f"\nDownloading {name} -> {target}")
    snapshot_download(repo_id=name, local_dir=str(target), ignore_patterns=IGNORE)
    print("Done.")


if __name__ == "__main__":
    fetch(config.TRANSLATOR_MODEL_NAME, config.TRANSLATOR_LOCAL_DIR)
    fetch(config.LLM_MODEL_NAME, config.LLM_LOCAL_DIR)
    print("\nAll models downloaded. You can now run: python app.py (works offline).")
