"""Flask backend for the Dzongkha AI Chatbot. Run:  python app.py"""
import logging

from flask import Flask, jsonify, render_template, request

import config
from chatbot.errors import ChatbotError
from chatbot.model_loader import ModelManager
from chatbot.response_generator import ResponseGenerator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("dzongkha-chatbot")


def create_app(generator=None, models=None):
    app = Flask(__name__)
    app.json.ensure_ascii = False                 # keep Dzongkha readable in JSON
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024  # reject huge requests

    if generator is None:
        models = ModelManager()
        models.start_background_load()
        generator = ResponseGenerator(models)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        status = models.status() if models else {"llm": "unknown", "translator": "unknown"}
        return jsonify(status)

    @app.post("/api/chat")
    def chat():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ChatbotError("bad_request", "Request must be JSON.", 400)
        result = generator.generate(data.get("message"), data.get("history"))
        return jsonify(result)

    @app.errorhandler(ChatbotError)
    def handle_chatbot_error(err):
        return jsonify({"error": err.message, "code": err.code}), err.status

    @app.errorhandler(413)
    def too_big(_):
        return jsonify({"error": "Request too large.", "code": "too_large"}), 413

    @app.errorhandler(Exception)
    def unexpected(err):
        if hasattr(err, "code") and isinstance(err.code, int):  # normal HTTP errors (404...)
            return jsonify({"error": getattr(err, "description", "Error"), "code": "http_error"}), err.code
        log.exception("Unhandled error")
        return jsonify({"error": "Unexpected server error.", "code": "server_error"}), 500

    return app


if __name__ == "__main__":
    # use_reloader=False so the models are not loaded twice in debug mode
    create_app().run(host=config.HOST, port=config.PORT, debug=config.DEBUG, use_reloader=False)
