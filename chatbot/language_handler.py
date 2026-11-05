"""Text utilities: validation, normalisation, Dzongkha (Tibetan-script) checks, intent matching."""
import json
import re
from pathlib import Path

import config
from chatbot.errors import ChatbotError

_TIBETAN = re.compile(r"[\u0F00-\u0FFF]")


def tibetan_ratio(text: str) -> float:
    """Share of meaningful characters that are in the Tibetan Unicode block (Dzongkha uses it)."""
    chars = [c for c in text if not c.isspace() and not (c.isascii() and not c.isalnum())]
    if not chars:
        return 0.0
    return sum(1 for c in chars if _TIBETAN.match(c)) / len(chars)


def is_valid_dzongkha_output(text: str, english: str = "") -> bool:
    """Cheap sanity check: must be mostly Tibetan script and not the English echoed back."""
    if not text or not text.strip():
        return False
    if english and text.strip().lower() == english.strip().lower():
        return False
    return tibetan_ratio(text) >= config.MIN_TIBETAN_RATIO


def validate_message(message) -> str:
    if not isinstance(message, str):
        raise ChatbotError("invalid_input", "Message must be text.", 400)
    message = message.strip()
    if not message:
        raise ChatbotError("empty_input", "Please type a message first.", 400)
    if len(message) > config.MAX_INPUT_CHARS:
        raise ChatbotError(
            "too_long", f"Message is too long (max {config.MAX_INPUT_CHARS} characters).", 400
        )
    if tibetan_ratio(message) > 0.5:
        raise ChatbotError("not_english", "Please write your message in English.", 400)
    return message


def normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9'\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_english(text: str) -> str:
    """Strip markdown/bullets/emoji noise so the translator gets plain sentences."""
    text = re.sub(r"[*_`#>]+", "", text)
    text = re.sub(r"^\s*(?:[-•]|\d+[.)])\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"[^\x00-\x7F]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def split_sentences(text: str):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    parts = [p.strip() for p in parts if p.strip()]
    return parts[: config.MAX_SENTENCES_TO_TRANSLATE]


class IntentMatcher:
    """Matches short, common messages (greetings, thanks...) to predefined responses.

    This is RULE-BASED, not AI. Dzongkha text in dzongkha_responses.json must be
    reviewed by a fluent speaker before you trust it.
    """

    MAX_WORDS = 6

    def __init__(self, intents: dict):
        self.intents = intents

    @classmethod
    def from_file(cls, path: Path):
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f)["intents"])

    def match(self, normalized: str):
        words = normalized.split()
        if not words or len(words) > self.MAX_WORDS:
            return None
        padded = f" {normalized} "
        for name, intent in self.intents.items():
            for pattern in intent["patterns"]:
                if intent.get("match", "anywhere") == "start":
                    hit = normalized == pattern or normalized.startswith(pattern + " ")
                else:
                    hit = f" {pattern} " in padded
                if hit:
                    return {"intent": name, **intent["responses"][0]}
        return None
