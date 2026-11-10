# ARGUS — single-file autonomous OSINT & digital-forensics agent

Everything ships in one file: **`vedant_osint.py`**.

```bash
python vedant_osint.py --help        # CLI surface
python vedant_osint.py version       # version, build phase, roadmap
python vedant_osint.py config        # interpreter / dependency / env probes
python vedant_osint.py mission -t example.com -o "map the attack surface"
```

Authorised use only — collect from systems you own or are explicitly permitted to assess.

## Status

| Phase | Scope | State |
|-------|-------|-------|
| 1 | Foundation — CLI skeleton, config probing, version reporting | ✅ done |
| 2 | Contracts — mission/evidence models, case workspace | ⬜ next |
| 3 | Orchestration — LangGraph Master Agent + runtime Subagent factory | ⬜ |
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
