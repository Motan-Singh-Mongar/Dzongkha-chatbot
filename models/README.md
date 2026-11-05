# models/

Model files are NOT stored in Git (they are several GB). Download them with:

    python scripts/download_models.py

This creates:

    models/llm/          English chat model   (default: Qwen/Qwen2.5-1.5B-Instruct, Apache-2.0, ~3 GB)
    models/translator/   English->Dzongkha    (default: facebook/nllb-200-distilled-600M, CC-BY-NC-4.0, ~2.5 GB)

To use different models, change LLM_MODEL_NAME / TRANSLATOR_MODEL_NAME in config.py
(or set them as environment variables) and run the download script again.
Check each model's licence on its Hugging Face page before any commercial use.
