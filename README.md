# Supreme Council v0.1

Personal Windows CLI; no UI, no hosting. Python 3.10+.

## Setup (PowerShell, from the extracted supreme-council folder)

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
notepad config.json
```

Start with a new, unfunded OpenRouter account/key: https://openrouter.ai/keys . Do not add credits, a payment method, automatic top-ups, BYOK or a billed workspace. Paste the key after `OPENROUTER_API_KEY=` in `.env` locally. Do not share it. After confirming the account is unbilled, change ONLY the openrouter `confirmed_unbilled_free_account` to true and `checked_on` to today's local date (YYYY-MM-DD). The confirmation expires after seven days; recheck account status and renew it. All providers start disabled. No account billing status is automatically verified.

```powershell
.\.venv\Scripts\python.exe -m unittest -v
.\.venv\Scripts\python.exe council.py discover
.\.venv\Scripts\python.exe council.py run --mode quick --prompt "Reply with the word OK."
```

Type SEND after inspecting selected models. No API inference calls occur during `discover`. The live catalog is read before each run. A run exits with code 2 if fewer than two usable responses arrive, but still saves whatever was received.

## Real use

```powershell
.\.venv\Scripts\python.exe council.py run --mode council
```

Paste multiline text, type `/end` on a separate line, then type SEND. Use `--synthesize` for an optional additional AI call that sends the collected answers to one responding model. Use `--file prompt.txt` for long prompts (maximum 48,000 UTF-8 bytes; provider context limits also apply). `--tokens` controls the response budget, 256–8192, default 4096. Quick/Council/Supreme select up to 3/5/8 models respectively, subject to availability and caps. `--yes` explicitly skips the confirmation; use only when deliberately sending non-sensitive content.

For clipboard input (PowerShell):

```powershell
Get-Clipboard -Raw | Set-Content -Encoding UTF8 prompt.txt
.\.venv\Scripts\python.exe council.py run --file prompt.txt --mode council
```

The local `prompt.txt` contains your clipboard content; delete it when no longer needed. Nothing monitors your clipboard. Attach the generated `runs/.../master_report.md` to ChatGPT; it includes the actual response texts, not just links. Each response is also saved separately with metadata. Text is unchanged except redaction of configured API keys if echoed. API caps can truncate responses; these are marked partial. No private reasoning or hidden provider text is recovered.

## Optional additional providers

Groq: https://console.groq.com/keys and https://console.groq.com/docs/rate-limits
Gemini: https://aistudio.google.com/apikey and https://ai.google.dev/gemini-api/docs/pricing

Use only unbilled free-tier accounts/projects. Add keys to `.env`. Confirm the exact free-tier model IDs and your account quota in the official dashboard; fill `approved_models` with those IDs in config.json, then set the confirmation to true and today's date. Lower the local daily cap if your actual quota is smaller. The script requires catalog presence but cannot verify direct provider pricing or your billing status. A missing key, missing confirmation, expired confirmation or failed catalog disables the provider. The conservative rolling request caps apply only to this tool, not other software or provider token quotas. HTTP 429 is logged with no retry. Check actual billing dashboards after the smoke test. No absolute zero-cost guarantee.

## What is implemented

- Live OpenRouter discovery of text models with `:free` and strictly zero catalog pricing; requests carry a zero price ceiling, no model fallback.
- Manually confirmed Groq and Gemini adapters, selected by live catalog plus exact allowlist.
- Developer-family diversity heuristic, not a validated task-specific ranking. No hardcoded OpenRouter model list.
- Parallel calls, bounded concurrency, request ledger, fail-closed configuration, output caps, per-response files as calls finish, complete Markdown report, optional synthesis.
- No automatic execution of model-generated content, no secret logging, no scheduled agent or browser automation.

## Verification and limitations

Seven unit/mock tests pass in the creation environment. No live inference or Windows runtime test performed; user credentials are required for those. Official API docs: https://openrouter.ai/docs/api/api-reference/models/get-models , https://openrouter.ai/docs/guides/routing/provider-selection , https://console.groq.com/docs/openai , https://ai.google.dev/gemini-api/docs/openai .

Free tiers may retain/train on prompts. Do not submit confidential material, private source code, credentials or client data. Free model output may be wrong. Optional synthesis is not independent evidence verification. Discovery refreshes only connected providers when the CLI runs; autonomous web discovery, scheduled runs, task-specific benchmarks, evidence ledger, Ollama and ChatGPT integration are future work.
