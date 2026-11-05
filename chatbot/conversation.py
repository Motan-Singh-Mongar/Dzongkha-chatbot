"""Conversation history handling: validate, trim to a budget, build LLM messages."""
import config


def sanitize_history(raw, max_turns=None, max_chars=None):
    """Return a clean list of {'role','content'} dicts that fits the context budget.

    History is kept in ENGLISH (the language the LLM works in).
    """
    max_turns = max_turns or config.MAX_HISTORY_TURNS
    max_chars = max_chars or config.MAX_HISTORY_CHARS
    if not isinstance(raw, list):
        return []
    cleaned = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        role, content = item.get("role"), item.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            cleaned.append({"role": role, "content": content.strip()[:800]})
    cleaned = cleaned[-(max_turns * 2):]
    while cleaned and sum(len(m["content"]) for m in cleaned) > max_chars:
        cleaned.pop(0)
    while cleaned and cleaned[0]["role"] != "user":  # must start with a user turn
        cleaned.pop(0)
    return cleaned


def build_llm_messages(system_prompt, history, user_message):
    return [{"role": "system", "content": system_prompt}, *history,
            {"role": "user", "content": user_message}]
