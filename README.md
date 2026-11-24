# Supreme Council v0.2 — development

Personal Windows desktop/CLI tool. Python 3.10+. No mandatory paid services.

## Upgrade from v0.1

Save any local code changes first. Keep .env, config.json, usage.sqlite3 and runs/ intact. From the project folder:

    git fetch origin
    git switch development/v0.2
    git pull --ff-only origin development/v0.2
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    .\.venv\Scripts\python.exe -m unittest -v

Double-click START_COUNCIL.bat to launch. Or:

    .\.venv\Scripts\python.exe gui.py

Paste a short brief (max 12,000 UTF-8 bytes), choose mode and 100/250/500 words per AI, and consent to cloud submission. Progress appears in the log. Open report or Copy report after the run. Cancel stops the local process, but cannot guarantee remote inference cancellation. Collected responses remain in runs/.

## CLI

    .\.venv\Scripts\python.exe council.py discover
    .\.venv\Scripts\python.exe council.py run --mode quick --words 250 --prompt "Recommend a simple local database for a personal task app." --synthesize

Quick/Council/Supreme target 3/5/8 models, plus at most two replacement attempts and one optional synthesis call. Local caps may prevent extra requests. The word count is a request to the model, not a guaranteed hard word cap. The larger token allowance reserves space for reasoning. Known context and completion limits are respected using a conservative UTF-8 byte estimate, not an exact tokenizer. Unknown output limits use a conservative 4096-token cap. Large briefs are rejected rather than silently shortened. Model reliability history influences selection; it is not a validated intelligence ranking.

The complete original brief and actual sent prompts are saved locally. Synthesis uses compact response fields, and may skip if no suitable successful judge or the input is too large. It is not independent fact verification.

## Accounts

Create only unfunded, unbilled free-tier accounts. For OpenRouter use https://openrouter.ai/keys . Put keys in .env locally, never commit them. Confirm account status and update checked_on in config.json; confirmation expires after seven days. For Groq and Gemini, verify exact model IDs and free eligibility before adding approved_models. No direct provider billing verification. Actual cost must be checked in provider dashboards. No paid fallback. Free-tier prompts may be retained or used for training; do not send confidential material.

## Rollback

After saving local source changes, use git switch --detach v0.1.0 to return to the original CLI. Use git switch development/v0.2 to return to development. Local ignored data remains in the folder.

## Testing status

Run the unit/mock tests before use. Windows GUI and real provider behavior require local testing. No claim of measured intelligence gains or guaranteed free billing.
