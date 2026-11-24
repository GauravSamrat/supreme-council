# Supreme Council v0.3

A Windows desktop app and CLI for gathering responses from eligible free AI models. The local request and estimated-token limits are safety ceilings. Provider limits and account billing status must be checked separately.

## Install or upgrade

From PowerShell in the repository, with the app closed, save existing v0.2 settings before switching branches. If you already have a local override, review and merge provider settings into it locally.

```powershell
if ((Test-Path .\config.json) -and -not (Test-Path .\config.local.json)) {
    Copy-Item -LiteralPath .\config.json -Destination .\config.local.json
}
git switch development/v0.3
if (-not (Test-Path .\.venv\Scripts\python.exe)) { py -3 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .\.env)) { Copy-Item -LiteralPath .\.env.example -Destination .\.env }
.\TEST_COUNCIL.bat
.\START_COUNCIL.bat
```

Double-clicking **START_COUNCIL.bat** also opens the desktop app. Dependencies are HTTPX and python-dotenv. Python 3.10+ and Tkinter are required. Closing the app before an upgrade lets SQLite and the report writer finish normally.

## Configure an eligible account

1. Add the API key to the matching variable in local `.env`. Keep the file outside shared folders and restrict its local access.
2. In the provider console, verify the account or project is currently unbilled and on the free API tier. Confirm that each exact direct-provider model is a free text chat model for this account. Never enable billing to meet an application requirement.
3. In `config.local.json`, add a provider entry like the one below. Provider settings in this file replace the corresponding default provider object. Replace the date with the date of your actual check. Confirmations expire after seven days.

```json
{
  "providers": {
    "openrouter": {
      "confirmed_unbilled_free_account": true,
      "checked_on": "YYYY-MM-DD",
      "daily_cap": 40,
      "allow_free_router": false
    }
  },
  "engine": {
    "daily_requests": 40,
    "daily_estimated_tokens": 300000,
    "deadline_seconds": 360,
    "evaluate": false
  }
}
```

Use an OpenRouter key from the confirmed account. Groq and Gemini also require an `approved_models` array of exact IDs from the discoverable API catalog. Verify free-tier eligibility when refreshing the date. An ID appearing in a catalog establishes availability to the API, while free access comes from account and model confirmation. The app records that actual billing is unverified.

## Run

Paste a brief and choose Auto, Quick, Council or Supreme. Auto targets 1, 3 or 5 complete answers. Quick, Council and Supreme target 3, 5 and 8. The total attempt ceilings are 2, 5 or 8 in Auto, and 5, 8 or 12 in manual modes. Synthesis and evaluation can use spare attempt slots. A provider circuit, local quota or deadline can end a run early.

The app prompts for consent before submitting the brief. Free-tier providers may retain inputs or use them to improve services. Known keys are blocked in prompts. Suspected sensitive text is blocked by default. Confidential mode blocks all inference and catalog requests because no local backend is bundled. Load only briefs you explicitly intend to submit. Reports are plaintext files under `runs\`.

```powershell
.\.venv\Scripts\python.exe council.py discover
.\.venv\Scripts\python.exe council.py run --file .\prompt.txt --mode auto --synthesize
.\.venv\Scripts\python.exe council.py run --prompt "Outline three trade-offs" --difficulty medium --topic planning
```

The prompt is limited to 12,000 UTF-8 bytes. Review and shorten long briefs manually. The CLI accepts `--yes` as explicit consent and `--ack-sensitive` as a separate override for the sensitive-text heuristic. Use `--confidential` to block cloud access. Use **Cancel** in the GUI to cancel an outstanding request and retain answers already written. **History / responses** opens saved Markdown including individual responses, and **Export** saves a copy of the master report.

## How routing and reports work

- Live discovery is required before each run. OpenRouter eligibility requires all advertised prices to be zero, text chat support and a free ID. Requests restrict price to zero and disable provider fallback. The Free Models Router is optional and ranked after named free routes because it selects the underlying model itself.
- A deterministic task classifier explains its keyword and length signals. The CLI can override its topic and difficulty. Routing uses reliability, task fit, evaluation, latency and diversity. Text output budgets are conservative estimates, with room for generation and reasoning where model context permits.
- The scheduler dispatches sequentially and re-ranks after each attempt. SQLite reservations atomically check rolling global and provider caps, estimated tokens and shared cooldowns. Expired cooldowns allow a single leased probe. The v0.2 request ledger stays in place. Relevant legacy JSON health counts become small priors. Interrupted reservations count for their rolling window.
- Optional evaluation runs at most one deterministic check per completed run with available slots and uses at most 10% of the local daily request ceiling. Checks rotate per model. Scores cover narrow synthetic tasks, and answer completeness is tracked separately. No generated code is executed.
- Reports preserve the full brief and attributed answers after redacting configured API keys. AI synthesis takes attributed excerpts and can group exact duplicate answers. Local fallback lists exact shared passages and leaves the underlying claims for human review. Model family overlap can indicate correlation. Provider scopes and family names are heuristics.

## Provider status

| Provider | Classification and integration |
| --- | --- |
| OpenRouter | Live verified model pricing and local account confirmation required. Named free routes supported. [Free models](https://openrouter.ai/collections/free-models/) |
| OpenRouter Free Router | Supported with additional opt-in and the same live pricing gate. [Free Models Router](https://openrouter.ai/openrouter/free) |
| Groq | Supported when the user confirms the Free plan and exact model. [Groq rate limits](https://console.groq.com/docs/rate-limits) |
| Gemini Developer API | Supported when the user confirms an unbilled project and exact free-tier model. [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing) |
| NVIDIA NIM hosted API | Disabled. Hosted trial terms describe trial credits. [NVIDIA trial terms](https://assets.ngc.nvidia.com/products/api-catalog/legal/NVIDIA%20API%20Trial%20Terms%20of%20Service.pdf) |
| Mistral | Disabled. API access requires billing activation under the documented plan policy. [Mistral usage and limits](https://docs.mistral.ai/admin/billing-usage/usage-limits) |
| Cloudflare Workers AI | Disabled. Free allocation exists with plan- and model-dependent eligibility and potential paid overage. [Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/) |
| Hugging Face Inference Providers | Disabled. Recurring credits coexist with paid inference. [Inference Providers pricing](https://huggingface.co/docs/inference-providers/pricing) |
| Ollama | Optional local deployment candidate. A backend that verifies local-only operation is not bundled. [Ollama FAQ](https://docs.ollama.com/faq) |
| Other cloud APIs | Unverified. No automatic enablement. |

## Acceptance checklist

- Run the mock suite. Open the GUI and verify Auto, word count, appearance and report actions.
- With an approved free account and a harmless prompt, discover the catalog. Verify expected routes and confirm account billing independently.
- Submit an Auto run and a Council run with synthesis. Check selection reasons, progress, preserved responses and estimated usage.
- Cancel during a run and open the partial report. Run Confidential and verify cloud work is blocked.
- Review local logs and saved artifacts before sharing. A complete answer and model agreement do not establish accuracy.

## Rollback

Close the app first. Switch to the version you previously used and launch it with the same virtual environment. The migration adds tables and retains the legacy request table, so v0.2 can use the database. v0.2 reads `config.json` and ignores `config.local.json`. Keep the local override for future upgrades.

```powershell
git switch development/v0.2
.\START_COUNCIL.bat
```

For the historical v0.1.0 release, use a separate checkout to keep its local storage independent. No provider inference is required by the automated tests.
