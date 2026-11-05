# Dzongkha AI Chatbot (English in, Dzongkha out)

A fully local chatbot: you type English, it answers in Dzongkha (རྫོང་ཁ). No external APIs, no API keys.

## How it works (and what is / is not AI)

```
English message
   -> 1. Intent matcher      RULE-BASED   greetings, thanks, goodbye (data/dzongkha_responses.json)
   -> 2. Knowledge base      RETRIEVAL    a few verified facts (data/knowledge_base.json)
   -> 3. Local English LLM   AI           Qwen2.5 (default) answers using conversation history
   -> 4. NLLB-200 translator AI           English -> Dzongkha (code dzo_Tibt)
   -> 5. Sanity check        RULE-BASED   must be Tibetan script, not an echo of the English
```

Follow-ups ("Give me an example") work because the English LLM receives the last few turns.

## Honest limitations

- No open model is known to chat natively and fluently in Dzongkha. Dzongkha comes from **machine translation**, which is
  weaker for low-resource languages. Expect mistakes, especially for technical words and longer answers.
- Only ONE Dzongkha string ships pre-written (the greeting "ཀུ་ཟུ་ཟང་པོ་ལགས།"). It is still marked *unreviewed*.
  Everything else is machine-translated. **Have a fluent Dzongkha speaker review it** before trusting or sharing it.
- NLLB-200 is licensed CC-BY-NC 4.0 (non-commercial). Qwen2.5-1.5B is Apache-2.0.
- I could not run the real models while building this, so the real-model path is untested. Test it yourself (Step 6).

## Hardware (defaults assume 8 GB RAM, no GPU)

| Item | Default | Notes |
|---|---|---|
| Downloads | ~6 GB total | ~2.5 GB translator + ~3 GB LLM |
| RAM while running | ~6-7 GB | close other apps on 8 GB machines |
| Speed on CPU | ~10-40 s per AI answer | greetings/knowledge base are faster (translation only) |
| GPU | optional | not required |

More RAM? Edit `config.py`: `Qwen/Qwen2.5-3B-Instruct` (~8 GB RAM) and/or `facebook/nllb-200-distilled-1.3B`.

## Setup on Windows (PowerShell, VS Code terminal)

**1. Open the folder:** VS Code -> File -> Open Folder -> `english-dzongkha-ai-chatbot`. Terminal -> New Terminal.
Requires Python 3.10-3.12 (`python --version`).

**2. Virtual environment**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
If scripts are blocked: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then activate again.
In VS Code press Ctrl+Shift+P -> "Python: Select Interpreter" -> pick the `venv` one.

**3. Install dependencies** (PyTorch CPU build first)
```powershell
pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```
(NVIDIA GPU? Install the CUDA build of torch from pytorch.org instead.)

**4. Download the models once (needs internet, ~6 GB)**
```powershell
python scripts/download_models.py
```

**5. Run**
```powershell
python app.py
```
Open http://127.0.0.1:5000. The yellow banner shows model loading (1-2 minutes). After the download, it works offline.

**6. Test**
```powershell
python -m unittest discover -s tests -v          # fast tests (fake models)
$env:RUN_MODEL_TESTS = "1"; python -m unittest discover -s tests -v   # slow tests with the real models
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `Translator model not found in ...` | Run `python scripts/download_models.py` |
| Banner says `Model problem: ...` | Read the message; also see `/api/health` and the terminal |
| `MemoryError` / PC freezes | Close apps; keep the 1.5B LLM + 600M translator; lower `LLM_MAX_NEW_TOKENS` |
| Very slow replies | Normal on CPU. Try `$env:LLM_DTYPE="float32"` if your CPU lacks bfloat16 speed |
| `Tokenizer does not know language code dzo_Tibt` | Wrong/incomplete translator download; re-download |
| Dzongkha shows as boxes | Install **Noto Serif Tibetan** or **Jomolhari** (free); Windows also has *Microsoft Himalaya* |
| "did not produce valid Dzongkha" | The model output was not Tibetan script; rephrase or use the larger translator |
| `Activate.ps1 cannot be loaded` | See Step 2 execution-policy fix |

## Improving quality (Step 12)

1. Run `python scripts/evaluate_model.py` -> `data/eval_results.csv` (opens in Excel with Tibetan text).
2. Ask a fluent speaker to fill reference answers and score Accuracy / Fluency / Appropriateness (1-5).
3. Move good Dzongkha into `data/dzongkha_responses.json` / `data/knowledge_base.json` and set `"status": "reviewed"`.
4. Add more knowledge-base entries (short, simple English).
5. Try the 1.3B translator and a 3B LLM if your RAM allows; compare scores.
6. Longer term: collect reviewed English-Dzongkha pairs and fine-tune NLLB (LoRA) on them.

## GitHub

`git init`, then `git add .` -> `git commit`. `.gitignore` already excludes `venv/` and model weights. Mention the
CC-BY-NC licence of NLLB in your repository description.

## Project layout

```
app.py                      Flask server + API (/api/chat, /api/health)
config.py                   all settings
chatbot/model_loader.py     loads local LLM + translator, runs inference
chatbot/response_generator.py   decides how to answer
chatbot/language_handler.py     validation, Dzongkha checks, intent matching
chatbot/conversation.py     history trimming
data/                       responses, knowledge base, evaluation set
scripts/                    download_models.py, evaluate_model.py
templates/ static/          frontend
tests/test_chatbot.py       automated tests
```
