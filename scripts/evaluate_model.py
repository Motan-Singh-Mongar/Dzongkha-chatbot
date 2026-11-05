"""Run the evaluation set through the REAL local models and write a CSV for a Dzongkha speaker.

    python scripts/evaluate_model.py          -> data/eval_results.csv
"""
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from chatbot.errors import ChatbotError  # noqa: E402
from chatbot.language_handler import tibetan_ratio  # noqa: E402
from chatbot.model_loader import ModelManager  # noqa: E402
from chatbot.response_generator import ResponseGenerator  # noqa: E402

models = ModelManager()
models.load_all()
print("Model status:", models.status())
gen = ResponseGenerator(models)
cases = json.loads((config.DATA_DIR / "eval_dataset.json").read_text(encoding="utf-8"))["cases"]

out = config.DATA_DIR / "eval_results.csv"
with open(out, "w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig so Excel shows Tibetan
    w = csv.writer(f)
    w.writerow(["id", "category", "question", "english_answer", "dzongkha_answer", "source",
                "tibetan_ratio", "seconds", "reference_dzongkha", "score_accuracy_1to5",
                "score_fluency_1to5", "score_appropriateness_1to5", "reviewer_notes"])
    for c in cases:
        start = time.time()
        try:
            r = gen.generate(c["question"], c["history"])
            row = [r["english"], r["dzongkha"], r["source"], round(tibetan_ratio(r["dzongkha"]), 2)]
        except ChatbotError as e:
            row = ["", f"ERROR: {e.message}", e.code, 0]
        w.writerow([c["id"], c["category"], c["question"], *row,
                    round(time.time() - start, 1), c["reference_dzongkha"], "", "", "", ""])
        print("done", c["id"])
print("Wrote", out)
