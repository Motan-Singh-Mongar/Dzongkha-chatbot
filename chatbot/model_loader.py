"""Loads the two local models (English chat LLM + English->Dzongkha translator).

Models are loaded ONCE in a background thread so the web page opens immediately.
Everything is loaded from local folders (local_files_only=True): no internet at runtime.
"""
import logging
import threading

import config
from chatbot.language_handler import split_sentences

log = logging.getLogger("dzongkha-chatbot")


def _has_weights(path) -> bool:
    return path.exists() and any(path.glob("*.json")) and (
        any(path.glob("*.safetensors")) or any(path.glob("*.bin"))
    )


class ModelManager:
    def __init__(self):
        self._status = {"llm": "not_loaded", "translator": "not_loaded"}
        self._errors = {}
        self._lock = threading.Lock()      # one inference at a time (CPU friendly)
        self._llm = self._llm_tok = None
        self._mt = self._mt_tok = None
        self._torch = None

    # ---------- status ----------
    def status(self):
        return {**self._status, "errors": dict(self._errors)}

    def is_ready(self, name: str) -> bool:
        return self._status.get(name) == "ready"

    # ---------- loading ----------
    def start_background_load(self):
        threading.Thread(target=self.load_all, daemon=True).start()

    def load_all(self):
        try:
            import torch
            self._torch = torch
        except Exception as exc:  # noqa: BLE001
            for k in ("llm", "translator"):
                self._status[k] = "error"
                self._errors[k] = f"PyTorch is not installed: {exc}"
            return
        self._load_translator()
        self._load_llm()

    def _load_translator(self):
        self._status["translator"] = "loading"
        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            path = config.TRANSLATOR_LOCAL_DIR
            if not _has_weights(path):
                raise FileNotFoundError(
                    f"Translator model not found in {path}. Run: python scripts/download_models.py")
            self._mt_tok = AutoTokenizer.from_pretrained(
                path, src_lang=config.TRANSLATOR_SRC_LANG, local_files_only=True)
            self._mt = AutoModelForSeq2SeqLM.from_pretrained(path, local_files_only=True).eval()
            if self._mt_tok.convert_tokens_to_ids(config.TRANSLATOR_TGT_LANG) == self._mt_tok.unk_token_id:
                raise ValueError(f"Tokenizer does not know language code {config.TRANSLATOR_TGT_LANG}")
            self._status["translator"] = "ready"
            log.info("Translator ready")
        except Exception as exc:  # noqa: BLE001
            self._status["translator"] = "error"
            self._errors["translator"] = str(exc)
            log.exception("Translator failed to load")

    def _load_llm(self):
        self._status["llm"] = "loading"
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            path = config.LLM_LOCAL_DIR
            if not _has_weights(path):
                raise FileNotFoundError(
                    f"LLM not found in {path}. Run: python scripts/download_models.py")
            dtype = getattr(self._torch, config.LLM_DTYPE, self._torch.float32)
            self._llm_tok = AutoTokenizer.from_pretrained(path, local_files_only=True)
            self._llm = AutoModelForCausalLM.from_pretrained(
                path, torch_dtype=dtype, local_files_only=True).eval()
            self._status["llm"] = "ready"
            log.info("LLM ready")
        except Exception as exc:  # noqa: BLE001
            self._status["llm"] = "error"
            self._errors["llm"] = str(exc)
            log.exception("LLM failed to load")

    # ---------- inference ----------
    def generate_english(self, messages) -> str:
        torch = self._torch
        with self._lock, torch.no_grad():
            text = self._llm_tok.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True)
            inputs = self._llm_tok([text], return_tensors="pt")
            out = self._llm.generate(
                **inputs,
                max_new_tokens=config.LLM_MAX_NEW_TOKENS,
                do_sample=True,
                temperature=config.LLM_TEMPERATURE,
                top_p=0.9,
                repetition_penalty=1.1,
            )
            new_tokens = out[0][inputs["input_ids"].shape[1]:]
            return self._llm_tok.decode(new_tokens, skip_special_tokens=True).strip()

    def translate(self, english: str) -> str:
        torch = self._torch
        sentences = split_sentences(english)
        if not sentences:
            return ""
        with self._lock, torch.no_grad():
            batch = self._mt_tok(sentences, return_tensors="pt", padding=True, truncation=True,
                                 max_length=128)
            out = self._mt.generate(
                **batch,
                forced_bos_token_id=self._mt_tok.convert_tokens_to_ids(config.TRANSLATOR_TGT_LANG),
                num_beams=config.TRANSLATOR_NUM_BEAMS,
                max_new_tokens=config.TRANSLATOR_MAX_NEW_TOKENS,
                no_repeat_ngram_size=4,
            )
            parts = self._mt_tok.batch_decode(out, skip_special_tokens=True)
        return " ".join(p.strip() for p in parts if p.strip())
