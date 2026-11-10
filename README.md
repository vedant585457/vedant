# ARGUS — single-file autonomous OSINT & digital-forensics agent

Everything ships in one file: **`vedant_osint.py`**.

```bash
python vedant_osint.py --help        # CLI surface
python vedant_osint.py version       # version, build phase, roadmap
python vedant_osint.py config        # interpreter / dependency / env probes
python vedant_osint.py mission -t example.com -o "map the attack surface"
python vedant_osint.py config --settings     # merged config, secrets masked
python vedant_osint.py mission -t example.com -o "..." --phase settings
```

## Configuration

CLI options override environment variables, which override built-in defaults —
resolved per field. Every orchestration limit is bounds-checked before any model
or browser call; invalid values exit `3` with a Rich error panel naming the
setting, its source, and the accepted range. Credentials are read from the
environment only at the moment of use and are shown as `sk-p…c3f9`; they are
scrubbed from all diagnostics.

| Setting | CLI | Env | Range / default |
|---|---|---|---|
| provider | `--provider` | `ARGUS_LLM_PROVIDER` | openai/anthropic/google/local |
| model | `--model` | `ARGUS_LLM_MODEL` | — |
| output dir | `--output-dir` | `ARGUS_OUTPUT_DIR` | `$ARGUS_HOME/output` |
| subagents | `--max-subagents` | `ARGUS_MAX_SUBAGENTS` | 1–25, 5 |
| workers/subagent | `--max-workers` | `ARGUS_MAX_WORKERS_PER_AGENT` | 1–16, 4 |
| total workers | `--max-total-workers` | `ARGUS_MAX_TOTAL_WORKERS` | 1–64, 16 |
| task retries | `--worker-retries` | `ARGUS_WORKER_RETRIES` | 0–10, 2 |
| review retries | `--review-retries` | `ARGUS_REVIEW_RETRIES` | 0–5, 2 |
| mission budget | `--mission-budget` | `ARGUS_MISSION_BUDGET_SECONDS` | 30–86400, 3600 |
| task budget | `--task-budget` | `ARGUS_TASK_BUDGET_SECONDS` | 5–3600, 300 |
| headless | `--headless/--headed` | `ARGUS_BROWSER_HEADLESS` | true |
| browser concurrency | `--browser-concurrency` | `ARGUS_BROWSER_CONCURRENCY` | 1–8, 2 |
| http concurrency | `--http-concurrency` | `ARGUS_HTTP_CONCURRENCY` | 1–32, 8 |

Authorised use only — collect from systems you own or are explicitly permitted to assess.

## Status

| Phase | Scope | State |
|-------|-------|-------|
| 1 | Foundation — CLI skeleton, config probing, version reporting | ✅ done |
| 2 | Contracts — strict configuration object (CLI > env > default) | ✅ done |
| 3 | Orchestration — LangGraph Master Agent + runtime Subagent factory | ⬜ next |
| 4 | Browser — browser-use / Playwright sessions and capture | ⬜ |
| 5 | Collection — passive OSINT sources, artefact hashing | ⬜ |
| 6 | Synthesis — cross-source correlation and reporting | ⬜ |
| 7 | Operations — resume, budgets, audit trail, hardening | ⬜ |

## Install

```bash
pip install typer rich pydantic langgraph browser-use playwright httpx python-dotenv
python -m playwright install chromium
```

Required environment: `ARGUS_LLM_MODEL` (from Phase 3), plus the API key for the
chosen provider. See the module docstring in `vedant_osint.py` for the full list.
