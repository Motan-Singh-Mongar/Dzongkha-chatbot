"""The chatbot 'brain': decides HOW to answer, then produces Dzongkha.

Pipeline:
  1. validate input
  2. IntentMatcher      -> predefined response (rule-based, NOT AI)
  3. KnowledgeBase      -> verified English facts (keyword retrieval, NOT generative)
  4. Local English LLM  -> generates an answer using conversation history (AI)
  5. NLLB translator    -> English -> Dzongkha (AI, machine translation)
  6. output sanity check (must be Tibetan script, not an echo of the English)
"""
import json
import logging
import re

import config
from chatbot.conversation import build_llm_messages, sanitize_history
from chatbot.errors import ChatbotError
from chatbot.language_handler import (IntentMatcher, clean_english,
                                      is_valid_dzongkha_output, normalize, validate_message)

log = logging.getLogger("dzongkha-chatbot")


class KnowledgeBase:
    """Tiny keyword retriever over data/knowledge_base.json."""

    MAX_WORDS = 12

    def __init__(self, entries):
        self.entries = entries

    @classmethod
    def from_file(cls, path):
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f)["entries"])

    def search(self, normalized: str):
        if len(normalized.split()) > self.MAX_WORDS:
            return None
        padded = f" {normalized} "
        best, best_len = None, 0
        for entry in self.entries:
            for kw in entry["keywords"]:
                if f" {kw} " in padded and len(kw) > best_len:
                    best, best_len = entry, len(kw)
        return best


class ResponseGenerator:
    def __init__(self, models, data_dir=config.DATA_DIR):
        self.models = models
        self.matcher = IntentMatcher.from_file(data_dir / "dzongkha_responses.json")
        self.kb = KnowledgeBase.from_file(data_dir / "knowledge_base.json")

    # ------------------------------------------------------------------
    def generate(self, message, history=None) -> dict:
        message = validate_message(message)
        history = sanitize_history(history)
        norm = normalize(message)

        intent = self.matcher.match(norm)
        if intent:
            return self._from_entry(intent, "library")

        entry = self.kb.search(norm)
        if entry:
            return self._from_entry(entry, "knowledge_base")

        return self._from_llm(message, history)

    # ------------------------------------------------------------------
    def _from_entry(self, entry, source):
        english = entry["english"]
        dz = entry.get("dzongkha")
        machine = False
        if not dz:
            dz = self._translate(english)
            machine = True
        return {
            "dzongkha": dz,
            "english": english,
            "source": source,
            "machine_translated": machine,
            "reviewed": entry.get("status") == "reviewed" and not machine,
        }

    def _from_llm(self, message, history):
        if not self.models.is_ready("llm"):
            raise ChatbotError(
                "model_not_ready",
                "The language model is not loaded yet (or failed to load). "
                "Check the terminal and /api/health.", 503)
        messages = build_llm_messages(config.SYSTEM_PROMPT, history, message)
        try:
            raw = self.models.generate_english(messages)
        except Exception:  # noqa: BLE001
            log.exception("LLM generation failed")
            raise ChatbotError("model_error", "The language model failed while answering.", 500)
        english = clean_english(raw)
        if not english:
            raise ChatbotError("empty_response", "The model returned an empty answer. Please rephrase.", 502)
        return {
            "dzongkha": self._translate(english),
            "english": english,
            "source": "ai",
            "machine_translated": True,
            "reviewed": False,
        }

    def _translate(self, english):
        if not self.models.is_ready("translator"):
            raise ChatbotError(
                "model_not_ready",
                "The Dzongkha translation model is not loaded yet (or failed to load).", 503)
        try:
            dz = self.models.translate(english)
        except Exception:  # noqa: BLE001
            log.exception("Translation failed")
            raise ChatbotError("model_error", "Translation to Dzongkha failed.", 500)
        if not is_valid_dzongkha_output(dz, english):
            raise ChatbotError(
                "translation_failed",
                "The model did not produce valid Dzongkha for this answer. Try rephrasing.", 502)
        return dz
