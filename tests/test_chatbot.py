"""Automated tests. Run from the project root:

    python -m unittest discover -s tests -v      (or: pytest -v)

Most tests use a FAKE model so they run in seconds without downloading anything.
Tests that need the REAL models only run if you set RUN_MODEL_TESTS=1.
"""
import os
import unittest

import config
from app import create_app
from chatbot.conversation import sanitize_history
from chatbot.errors import ChatbotError
from chatbot.language_handler import (is_valid_dzongkha_output, normalize, tibetan_ratio,
                                      validate_message)
from chatbot.response_generator import ResponseGenerator

DZ_SAMPLE = "བཀའ་དྲིན་ཆེ།"


class FakeModels:
    """Stands in for the real models."""
    def __init__(self, llm=True, translator=True, translation=DZ_SAMPLE, llm_answer="Sure. Here is an answer."):
        self._ready = {"llm": llm, "translator": translator}
        self.translation, self.llm_answer = translation, llm_answer
        self.last_messages = None

    def is_ready(self, name): return self._ready[name]
    def status(self): return {**{k: "ready" if v else "error" for k, v in self._ready.items()}, "errors": {}}

    def generate_english(self, messages):
        self.last_messages = messages
        return self.llm_answer

    def translate(self, english): return self.translation


class TestLanguageHelpers(unittest.TestCase):
    def test_tibetan_ratio(self):
        self.assertGreater(tibetan_ratio("ཀུ་ཟུ་ཟང་པོ་ལགས། ང་གིས་ཁྱོད་ལུ་ག་ཅི་འབད་ཚུགས་ནི་སྨོ།"), 0.9)
        self.assertEqual(tibetan_ratio("Hello there"), 0.0)

    def test_dzongkha_unicode_roundtrip(self):
        text = "རྫོང་ཁ"
        self.assertEqual(text.encode("utf-8").decode("utf-8"), text)
        self.assertTrue(is_valid_dzongkha_output(text))

    def test_rejects_english_echo_or_empty(self):
        self.assertFalse(is_valid_dzongkha_output("What is AI?", "What is AI?"))
        self.assertFalse(is_valid_dzongkha_output(""))
        self.assertFalse(is_valid_dzongkha_output("Some English only"))

    def test_validation(self):
        for bad in ["", "   ", None, 123, "x" * (config.MAX_INPUT_CHARS + 1), "རྫོང་ཁ་རྫོང་ཁ"]:
            with self.assertRaises(ChatbotError):
                validate_message(bad)
        self.assertEqual(validate_message("  hi  "), "hi")

    def test_normalize(self):
        self.assertEqual(normalize("Hello, How are YOU?!"), "hello how are you")


class TestHistory(unittest.TestCase):
    def test_trims_turns_and_chars(self):
        raw = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}" * 50} for i in range(40)]
        out = sanitize_history(raw)
        self.assertLessEqual(len(out), config.MAX_HISTORY_TURNS * 2)
        self.assertLessEqual(sum(len(m["content"]) for m in out), config.MAX_HISTORY_CHARS)
        self.assertEqual(out[0]["role"], "user")

    def test_bad_history_ignored(self):
        self.assertEqual(sanitize_history("nonsense"), [])
        self.assertEqual(sanitize_history([{"role": "system", "content": "x"}, 5, None]), [])


class TestResponseGenerator(unittest.TestCase):
    def test_greeting_uses_library_without_models(self):
        gen = ResponseGenerator(FakeModels(llm=False, translator=False))
        r = gen.generate("Hello")
        self.assertEqual(r["source"], "library")
        self.assertGreater(tibetan_ratio(r["dzongkha"]), 0.9)
        self.assertFalse(r["reviewed"])          # shipped drafts are never marked reviewed

    def test_how_are_you_translated(self):
        r = ResponseGenerator(FakeModels()).generate("Hello, how are you?")
        self.assertEqual(r["source"], "library")
        self.assertTrue(r["machine_translated"])
        self.assertEqual(r["dzongkha"], DZ_SAMPLE)

    def test_thanks(self):
        r = ResponseGenerator(FakeModels()).generate("Thank you for your help.")
        self.assertEqual(r["source"], "library")

    def test_knowledge_base_general_questions(self):
        gen = ResponseGenerator(FakeModels())
        self.assertEqual(gen.generate("What is artificial intelligence?")["source"], "knowledge_base")
        self.assertEqual(gen.generate("How can I learn Python?")["source"], "knowledge_base")

    def test_followup_sends_history_to_llm(self):
        models = FakeModels()
        gen = ResponseGenerator(models)
        history = [{"role": "user", "content": "What is machine learning?"},
                   {"role": "assistant", "content": "Computers learn from data."}]
        r = gen.generate("Give me an example.", history)
        self.assertEqual(r["source"], "ai")
        roles = [m["role"] for m in models.last_messages]
        self.assertEqual(roles, ["system", "user", "assistant", "user"])
        self.assertIn("machine learning", models.last_messages[1]["content"])

    def test_unclear_question_goes_to_llm(self):
        self.assertEqual(ResponseGenerator(FakeModels()).generate("asdf qwerty")["source"], "ai")

    def test_llm_not_ready(self):
        with self.assertRaises(ChatbotError) as ctx:
            ResponseGenerator(FakeModels(llm=False)).generate("Tell me about rivers")
        self.assertEqual(ctx.exception.status, 503)

    def test_translator_not_ready(self):
        with self.assertRaises(ChatbotError) as ctx:
            ResponseGenerator(FakeModels(translator=False)).generate("Tell me about rivers")
        self.assertEqual(ctx.exception.code, "model_not_ready")

    def test_english_echo_is_rejected(self):
        gen = ResponseGenerator(FakeModels(translation="Sure. Here is an answer."))
        with self.assertRaises(ChatbotError) as ctx:
            gen.generate("Tell me about rivers")
        self.assertEqual(ctx.exception.code, "translation_failed")

    def test_empty_llm_answer(self):
        with self.assertRaises(ChatbotError) as ctx:
            ResponseGenerator(FakeModels(llm_answer="   ")).generate("Tell me about rivers")
        self.assertEqual(ctx.exception.code, "empty_response")

    def test_empty_input(self):
        with self.assertRaises(ChatbotError):
            ResponseGenerator(FakeModels()).generate("")


class TestApi(unittest.TestCase):
    def setUp(self):
        models = FakeModels()
        self.client = create_app(generator=ResponseGenerator(models), models=models).test_client()

    def test_index_page(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Dzongkha AI Chatbot", r.get_data(as_text=True))

    def test_chat_returns_unescaped_dzongkha(self):
        r = self.client.post("/api/chat", json={"message": "Hello"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("ཀུ་ཟུ་ཟང་པོ་ལགས།", r.get_data(as_text=True))   # not \u0f40 escapes

    def test_empty_message_400(self):
        r = self.client.post("/api/chat", json={"message": "  "})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json()["code"], "empty_input")

    def test_non_json_400(self):
        self.assertEqual(self.client.post("/api/chat", data="hi").status_code, 400)

    def test_missing_message_400(self):
        self.assertEqual(self.client.post("/api/chat", json={}).status_code, 400)

    def test_unknown_route_json_404(self):
        r = self.client.get("/nope")
        self.assertEqual(r.status_code, 404)
        self.assertIn("error", r.get_json())

    def test_health(self):
        self.assertEqual(self.client.get("/api/health").get_json()["llm"], "ready")


@unittest.skipUnless(os.getenv("RUN_MODEL_TESTS") == "1", "set RUN_MODEL_TESTS=1 to test the real models")
class TestRealModels(unittest.TestCase):
    """Slow tests with the real downloaded models. These check STRUCTURE (is it Dzongkha script,
    is it not just an echo) - they cannot judge whether the Dzongkha is correct or fluent."""

    @classmethod
    def setUpClass(cls):
        from chatbot.model_loader import ModelManager
        cls.models = ModelManager()
        cls.models.load_all()
        cls.gen = ResponseGenerator(cls.models)

    def test_models_loaded(self):
        self.assertEqual(self.models.status()["llm"], "ready", self.models.status())
        self.assertEqual(self.models.status()["translator"], "ready", self.models.status())

    def test_ai_answer_is_tibetan_script(self):
        r = self.gen.generate("What is the capital of Bhutan?")
        self.assertGreaterEqual(tibetan_ratio(r["dzongkha"]), config.MIN_TIBETAN_RATIO)
        self.assertNotEqual(r["dzongkha"].lower(), "what is the capital of bhutan?")

    def test_followup(self):
        h = [{"role": "user", "content": "What is machine learning?"},
             {"role": "assistant", "content": "Computers learn from data."}]
        r = self.gen.generate("Give me an example.", h)
        self.assertTrue(is_valid_dzongkha_output(r["dzongkha"], r["english"]))


if __name__ == "__main__":
    unittest.main()
