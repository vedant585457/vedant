# ARGUS — single-file autonomous OSINT & digital-forensics agent

Everything ships in one file: **`vedant_osint.py`**.

```bash
python vedant_osint.py --help        # CLI surface
python vedant_osint.py version       # version, build phase, roadmap
python vedant_osint.py config        # interpreter / dependency / env probes
python vedant_osint.py mission -t example.com -o "map the attack surface"
python vedant_osint.py config --settings     # merged config, secrets masked
python vedant_osint.py doctor                # capability health check (CI gate)
python vedant_osint.py mission -t example.com -o "..." --phase settings
```

## Typed models

```bash
python vedant_osint.py models                  # catalogue + 20-check self-test
python vedant_osint.py models -n FinalReport   # fields + JSON schema
```

Evidence is typed by epistemic status — `observation` (requires a source),
`inference` (requires reasoning + its inputs), `allegation` (requires the party
who claimed it). Sources carry URL/path, retrieval time and method, HTTP status,
excerpt and SHA-256, plus chain-of-custody metadata. Missing data is an explicit
`UnknownValue(reason=...)`, and `null` keys survive serialisation, so a missing
key and a null stay distinguishable.

## Run state

`RunStateStore` is the single source of truth for a mission in flight: objective,
normalised scope, dynamic hierarchy, assignments, results, evidence, reviews,
retries, budget, events and final status.

```bash
python vedant_osint.py state --demo --checkpoint case/state.json
python vedant_osint.py state --load case/state.json
python vedant_osint.py state --stress        # parallel-writer self-test
```

Every mutation takes one `RLock`; evidence **merges** by id instead of replacing;
records are revision-guarded (`StaleWriteError` on a stale write); readers get
deep-copied snapshots; results are keyed by `(task_id, attempt)` so a retry keeps
the failure; progress is derived from records, never counted. Checkpoints are
versioned JSON written atomically (temp file + `os.replace`) and re-validated
through the typed models on load.

## Safety & scope

Every mission passes a policy preflight **before** anything is planned.

| Exit | Meaning |
|---|---|
| `0` | objective and scope cleared |
| `2` | a target is out of scope (not covered by `--scope`, or matched by `--exclude`) |
| `7` | refused — unauthorised access, credential theft, evasion, doxxing, harassment, destructive action |
| `8` | paused — guilt assumption or speculative identification needs `--confirm-intent` or `--accept-reframe` |

```bash
# evaluate an objective without planning anything
python vedant_osint.py policy -o "map the public attack surface" --scope example.com

# guilt-assuming wording is paused; adopt evidence-based language to proceed
python vedant_osint.py mission -t example.com -o "find the bad guys" --accept-reframe

# owned forensic artefacts
python vedant_osint.py mission -t ./disk.img -o "examine the image we own" \
        --mode forensic --data-class owned-artifact
```

A reframe always asks for indicators, competing hypotheses (including a benign
one), no attribution to individuals, and explicit uncertainty. Refusals cannot
be overridden by any flag; the safe alternative is always printed.

## Doctor

`doctor` verifies Python, the five required imports (Typer, Rich, LangGraph,
browser-use, Playwright), browser availability (engine **and** a downloaded
build), model configuration, output-directory writability, and optional
forensic utilities.

- **pass** — capability present.
- **warn** — *optional* capability missing; the feature degrades gracefully, exit `0`.
- **fail** — *required* capability missing; prints the install command, exit `3`.

`pip install playwright` alone does not download a browser — when no build is
found the doctor prints:

```bash
python -m playwright install chromium        # download Chromium
python -m playwright install-deps chromium   # install its OS libraries
```

Options: `--json`, `--strict`, `--problems-only`, `--no-hints`,
`--category {python,imports,browser,model,storage,forensics,configuration}`
(repeatable), `--create-dirs`, `--probe-launch`. Credentials are never printed.

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
| 2 | Contracts — settings, `doctor`, preflight, models, run-state store | ✅ done |
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
