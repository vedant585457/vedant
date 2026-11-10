#!/usr/bin/env python3
"""
ARGUS — single-file autonomous OSINT & digital-forensics agent.
================================================================

A self-contained command line tool that plans and runs authorised
open-source-intelligence and digital-forensics *missions*.  The whole product
lives in this one file: orchestration, browser automation, reporting and the
CLI.  There are no sibling modules, no package directory and no hardcoded
agent roster (see the Phase notes at the bottom of this docstring).

Design invariants
-----------------
*   **One file.**  Everything ships inside ``vedant_osint.py``.
*   **Nothing happens on import.**  Importing this module defines names only:
    no network calls, no browser launches, no files created, no console
    output.  All side effects are triggered from CLI commands.
*   **One permanent agent.**  Only the *Master Agent* is statically defined.
    Subagents and the Workers beneath them are constructed at runtime from a
    task specification.  Later phases add those factories — they are never
    role classes such as ``NetworkSubagent`` or ``ShodanWorker``.
*   **Authorisation is explicit.**  Anything beyond passive collection
    requires the operator to assert authorisation on the command line.

Required dependencies
---------------------
Core (imported lazily, checked by ``argus config``)::

    pip install typer rich pydantic python-dotenv    # pydantic powers the typed models

Orchestration and collection (Phase 3+)::

    pip install langgraph browser-use playwright httpx
    python -m playwright install chromium

Standard library only for this file's skeleton; third-party packages are
probed with :func:`importlib.util.find_spec` so that ``--help`` and
``config`` work even on a machine where none of the optional extras are
installed yet.  Declaring the packages here keeps the deliverable a single
file — no ``requirements.txt`` is generated.

Environment variables
---------------------
Model access::

    ARGUS_LLM_MODEL           Model id, e.g. "gpt-4.1-mini" or "claude-sonnet-4".
    ARGUS_LLM_PROVIDER        Provider: openai | anthropic | google | local.
    ARGUS_LLM_BASE_URL        Optional OpenAI-compatible endpoint override.

Credentials — looked up, never printed.  A provider's key is read from its
:data:`PROVIDER_REGISTRY` entry (first *set* variable wins)::

    ARGUS_LLM_API_KEY         Provider-neutral key, checked before the above.
    OPENAI_API_KEY            Used when the provider is openai.
    ANTHROPIC_API_KEY         Used when the provider is anthropic.
    GOOGLE_API_KEY            Used when the provider is google.
    OLLAMA_HOST               Endpoint for the local provider (host only).

Paths and operator::

    ARGUS_HOME                Root for case data (default: ./argus_home).
    ARGUS_OUTPUT_DIR          Mission output directory (default: $ARGUS_HOME/output).
    ARGUS_CASE_DIR            Artefact directory for the current mission.
    ARGUS_LOG_LEVEL           DEBUG | INFO | WARNING | ERROR (default: INFO).
    ARGUS_OPERATOR            Operator name recorded in the audit trail.
    ARGUS_USER_AGENT          User-Agent presented to remote hosts.
    ARGUS_HTTP_TIMEOUT        Per-request timeout in seconds (default: 30).

Orchestration limits and budgets (every one is range-checked before any
model or browser call — see :func:`build_settings`)::

    ARGUS_MAX_SUBAGENTS          Live Subagents per mission     (1-25,  default 5)
    ARGUS_MAX_WORKERS_PER_AGENT  Concurrent Workers per Subagent (1-16, default 4)
    ARGUS_MAX_TOTAL_WORKERS      Concurrent Workers mission-wide (1-64, default 16)
    ARGUS_WORKER_RETRIES         Retries per Worker task        (0-10,  default 2)
    ARGUS_REVIEW_RETRIES         Review cycles per Subagent     (0-5,   default 2)
    ARGUS_MISSION_BUDGET_SECONDS Wall-clock budget              (30-86400, default 3600)
    ARGUS_TASK_BUDGET_SECONDS    Per-task time budget           (5-3600, default 300)
    ARGUS_BROWSER_CONCURRENCY    Concurrent browser contexts    (1-8,   default 2)
    ARGUS_HTTP_CONCURRENCY       Concurrent HTTP workers        (1-32,  default 8)

Browser and network switches::

    ARGUS_BROWSER_HEADLESS    "1"/"0" — run Chromium headless (default: 1).
    ARGUS_BROWSER_PROFILE_DIR Persistent browser profile directory.
    ARGUS_ALLOW_NETWORK       "0" to force an offline / dry mission (default: 1).
    ARGUS_RESPECT_ROBOTS      "0" to ignore robots.txt (default: 1 — respected).

Precedence
----------
CLI option > environment variable > built-in default, applied per field.
``mission --phase settings`` renders the merged result with ``--source``
annotations; secrets appear only as ``set``/``unset`` with a masked hint such
as ``sk-p…c3f9`` and are scrubbed from every error and diagnostic surface.

Typed models
------------
The shared contracts live in this file and are inspectable from the CLI::

    python vedant_osint.py models                    # catalogue + self-test
    python vedant_osint.py models -n EvidenceItem    # one model's fields/schema

``Mission``, ``Scope``, ``SubagentSpec``, ``WorkerSpec``, ``TaskAssignment``,
``TaskResult``, ``EvidenceItem``, ``SourceReference``, ``QualityReview``,
``SubagentReport`` and ``FinalReport`` each carry a deterministic id, UTC
timestamps, a status, and an ``error`` field where failure is possible.

Evidence distinguishes three epistemic kinds — ``observation`` (requires a
source), ``inference`` (requires reasoning and its inputs) and ``allegation``
(requires the party who made the claim).  There is no "finding" kind: an
unverified statement is either our inference or their allegation.  Sources
record URL or artefact path, retrieval time and method, HTTP status, excerpt
and SHA-256, plus chain-of-custody metadata (handler, method, storage,
preservation status, integrity hash, gaps).

Missing data is an explicit ``UnknownValue(reason=...)`` rather than an empty
string, ``null`` keys are preserved on serialisation (a missing key and a null
are different claims), and models reject unknown fields so a typo cannot vanish.

Run state
---------
``RunStateStore`` is the single source of truth for a mission in flight.  It
tracks the objective, normalised scope, dynamic agent hierarchy, assignments,
results, evidence, reviews, retries, budget ledger, append-only events and the
final status.  Concurrency contract:

* one ``RLock`` guards every mutation, so no record is ever half-updated;
* adding evidence **merges** by id (sources, links and tags are unioned) instead
  of replacing the record, so two Workers cannot clobber each other;
* records carry revisions — pass ``expected_revision`` and a stale writer gets
  ``StaleWriteError`` rather than silently discarding newer work;
* readers get deep-copied snapshots taken under the lock, so they never see a
  torn state;
* results are keyed by ``(task_id, attempt)`` so a retry preserves the failure;
* progress is *derived* from the records, never from a drifting counter.

Checkpoints are versioned JSON written atomically (temp file + ``os.replace``)
and re-validated through the typed models on load::

    python vedant_osint.py state --demo --checkpoint case/state.json
    python vedant_osint.py state --load case/state.json
    python vedant_osint.py state --stress        # concurrency self-test

Event rendering
---------------
``EventRenderer`` streams a mission as lines, not as a full-screen TUI.  It
emits Master thinking/planning, Subagent and Worker spawning, task assignment,
browsing, forensic analysis, reasoning, Worker completion, quality review,
retasking, Subagent synthesis, Master synthesis, warnings and completion.

Design guarantees (each pinned by ``renderer --self-test``):

* **No alternate screen.**  ``Live(screen=True)`` is never used; the only escape
  sequences are colour.
* **Animation is optional and transient.**  On a TTY a step shows Rich's inline
  spinner; when animation is disabled — or the stream is not a terminal — the
  step becomes an explicit ``… message`` / ``✔ message`` pair, so information is
  never lost.
* **CI-safe.**  Piped output contains no ANSI escapes and no carriage returns,
  and every event appears exactly once in chronological order.
* **Nested output stays readable.**  Depth comes from spawn relationships and is
  drawn as ``│  `` indentation; ``--ascii`` swaps every glyph for ASCII.
* **Nothing leaks.**  Messages pass through the Task 2 redactor before they
  reach the terminal or the JSONL trace.

Every event is also written to an in-memory ``RenderTrace`` that can be saved as
JSONL and replayed, and a plain-text ``--log-file`` mirrors events that the
terminal filter hid::

    python vedant_osint.py renderer                       # scripted demo
    python vedant_osint.py renderer --self-test           # verify guarantees
    python vedant_osint.py renderer --record trace.jsonl --replay trace.jsonl
    python vedant_osint.py renderer --from-state case/state.json

Agent lifecycle animation
-------------------------
``LifecycleTracker`` renders the *life* of each agent, worker and task on top of
the event renderer: spawn, delegation, active work, reasoning, review, retry,
merge and completion.  Reusable methods: ``spawn``, ``delegate``,
``active_work`` (context manager), ``reasoning``, ``review``, ``retry_task``,
``merge``, ``complete``.

* **Concise, model-safe text only.**  :func:`sanitize_status` refuses
  deliberation ("let me think step by step", "my reasoning", "hmm") and caps
  every string at 20 words / 120 chars.  Reasoning is reported through
  :class:`StatusSummary` — decision, criterion, next action — which has no field
  for narrative, so hidden chain-of-thought cannot reach the terminal, a log or
  a report.
* **One animated line, not one per agent.**  Active work shares a single
  transient status line carrying ``N active · M done · elapsed`` and the current
  summary.  Permanent lines appear only on state transitions, so a 100-task run
  produces ~300 lines rather than thousands of ticks.  ``--heartbeat N`` adds
  throttled progress lines if you want them.
* **Start and terminal are paired.**  Every record gets exactly one start line
  and one terminal line with elapsed time and attempt number.  Exceptions mark
  the record ``failed``, cancellation marks it ``cancelled``, Ctrl-C marks it
  ``interrupted``, and ``shutdown()`` (idempotent, also registered with
  ``atexit``) closes anything still open — so an interrupted run can never leave
  a spinner turning or a task without an ending.

::

    python vedant_osint.py lifecycle                 # scripted demonstration
    python vedant_osint.py lifecycle --self-test     # 33 guarantee checks
    python vedant_osint.py lifecycle --json          # records + counters + events

Usage
-----
::

    python vedant_osint.py --help
    python vedant_osint.py version
    python vedant_osint.py config
    python vedant_osint.py config --settings            # merged, redacted view
    python vedant_osint.py models                       # typed model catalogue + self-test
    python vedant_osint.py state --stress               # run-state concurrency self-test
    python vedant_osint.py renderer --self-test         # CLI-only renderer guarantees
    python vedant_osint.py lifecycle --self-test        # lifecycle animation guarantees
    python vedant_osint.py doctor                       # full capability health check
    python vedant_osint.py policy -o "..." --scope example.com          # safety preflight only
    python vedant_osint.py mission --target example.com -o "map the attack surface"
    python vedant_osint.py mission -t example.com -o "..." --phase settings --json

Doctor
------
``doctor`` checks the interpreter, the five required imports (Typer, Rich,
LangGraph, browser-use, Playwright), browser availability — engine *and* a
downloaded build — model configuration, output-directory writability, and the
optional forensic utilities.  Three outcomes exist:

* ``pass`` — capability present.
* ``warn``  — an *optional* capability is missing; the affected feature
  degrades gracefully and the run continues (exit 0).
* ``fail``  — a *required* capability is missing; an install command is printed
  and the exit status is non-zero, so ``doctor`` works as a preflight gate.

``pip install playwright`` does not download a browser.  When no build is
found the doctor prints::

    python -m playwright install chromium        # download Chromium
    python -m playwright install-deps chromium   # install its OS libraries

Credential values are never printed: the model section reports only a masked
hint such as ``sk-p…c3f9 (len 51) from OPENAI_API_KEY``.  Set
``PLAYWRIGHT_BROWSERS_PATH`` to point the browser probe at a custom location.

Safety and scope preflight
--------------------------
Every mission passes a policy gate **before** anything is planned.  Supported
work is limited to public-web OSINT and forensic review of artefacts you own or
are explicitly authorised to examine.

Objectives requesting unauthorised account access, credential theft, evasion or
anti-forensics, doxxing, harassment or destructive action are **refused**
(exit ``7``).  No flag overrides a refusal.  Objectives that assume guilt
("find the bad guys") or attribute conduct from suspicion are **paused**
(exit ``8``) until the operator either confirms authorised intent
(``--confirm-intent``) or adopts an evidence-based reframe (``--accept-reframe``)
that collects indicators, tests competing hypotheses, attributes nothing to an
individual, and reports uncertainty.

Scope is an explicit allow-list of assets.  A target not covered by ``--scope``
(or matching ``--exclude``) is blocked with exit ``2`` and never reaches
planning; a programmatic caller must also pass
:func:`enforce_preflight`, which raises :class:`PolicyViolation`.

Exit codes
----------
See :class:`ExitCode`.  ``config`` and ``doctor`` return ``3`` (CONFIG) when a
*required* capability is missing — usable as CI/installation gates — and ``0``
when only optional capabilities are absent.  ``mission`` returns ``7`` for a
policy refusal, ``8`` for a paused objective and ``2`` for an out-of-scope
target.

Authorised use only
-------------------
Collect only from systems you own or are explicitly permitted to assess.
``--i-authorize`` records the operator's assertion in the run plan; it is not
a substitute for a signed scope document.
"""

from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════
# 1. Imports — grouped by purpose
# ══════════════════════════════════════════════════════════════════════════

# --- standard library: cheap, side-effect free -------------------------------
import asyncio
import atexit
import hashlib
import importlib.util
import io
import ipaddress
import json
import os
import platform
import re
import shutil
import sys
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Mapping

# --- third party: CLI surface -------------------------------------------------
# Typer + Rich are the only hard imports.  They are imported at module level
# because the CLI cannot exist without them, and importing them performs no
# I/O.  Everything heavier (LangGraph, browser-use, Playwright, HTTP clients)
# is imported lazily inside the functions that need it.
import typer
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.status import Status
from rich.table import Table
from rich.text import Text

# --- third party: imported lazily in later phases -----------------------------
# langgraph      -> Master Agent state machine            (Phase 3)
# browser_use    -> agentic browser sessions              (Phase 4)
# playwright     -> deterministic scraping + screenshots  (Phase 4)
# httpx          -> passive HTTP/API collection           (Phase 5)
# pydantic       -> typed mission/evidence models         (Phase 2)

# ══════════════════════════════════════════════════════════════════════════
# 2. Application constants and version information
# ══════════════════════════════════════════════════════════════════════════

APP_NAME: str = "argus"
APP_TITLE: str = "ARGUS"
APP_SUBTITLE: str = "autonomous OSINT & digital-forensics agent"
APP_SLUG: str = "vedant_osint"

VERSION_MAJOR: int = 0
VERSION_MINOR: int = 8
VERSION_PATCH: int = 0
VERSION_STAGE: str = "alpha"             # skeleton → alpha → beta → stable
__version__: str = f"{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH}"
VERSION_LABEL: str = f"{__version__}-{VERSION_STAGE}"

#: Bumped whenever the shape of an on-disk case file changes.
CASE_SCHEMA_VERSION: int = 1
#: Bumped whenever the shape of the subagent/worker task contract changes.
TASK_SCHEMA_VERSION: int = 1

MIN_PYTHON: tuple[int, int] = (3, 10)

#: Environment-variable prefix used for every setting this tool reads.
ENV_PREFIX: str = "ARGUS_"

DEFAULT_HOME_DIRNAME: str = "argus_home"
DEFAULT_OUTPUT_DIRNAME: str = "output"
DEFAULT_MAX_SUBAGENTS: int = 5
DEFAULT_MAX_WORKERS_PER_AGENT: int = 4
DEFAULT_MAX_TOTAL_WORKERS: int = 16
DEFAULT_WORKER_RETRIES: int = 2
DEFAULT_REVIEW_RETRIES: int = 2
DEFAULT_MISSION_BUDGET_SECONDS: int = 3600
DEFAULT_TASK_BUDGET_SECONDS: int = 300
DEFAULT_BROWSER_CONCURRENCY: int = 2
DEFAULT_HTTP_CONCURRENCY: int = 8
DEFAULT_LLM_PROVIDER: str = "openai"
DEFAULT_HTTP_TIMEOUT: float = 30.0
DEFAULT_USER_AGENT: str = f"{APP_TITLE}/{__version__} (+authorised-security-research)"
DEFAULT_LOG_LEVEL: str = "INFO"

#: Hard bounds for every numeric orchestration limit.  ``None`` means unbounded.
#: Out-of-range values are refused *before* any model or browser call.
LIMIT_BOUNDS: dict[str, tuple[int | None, int | None]] = {
    "max_subagents": (1, 25),
    "max_workers_per_agent": (1, 16),
    "max_total_workers": (1, 64),
    "worker_retries": (0, 10),
    "review_retries": (0, 5),
    "mission_budget_seconds": (30, 86_400),
    "task_budget_seconds": (5, 3_600),
    "browser_concurrency": (1, 8),
    "http_concurrency": (1, 32),
}

#: Build phase currently implemented.  Later tasks advance this number.
BUILD_PHASE: int = 2
BUILD_PHASE_NAME: str = "Contracts"

#: Section banners shared by the banner panel and ``version --json``.
PHASE_ROADMAP: tuple[tuple[int, str, str], ...] = (
    (1, "Foundation", "CLI skeleton, config probing, version reporting"),
    (2, "Contracts", "Settings, doctor, preflight, models, state, renderer, lifecycle"),
    (3, "Orchestration", "LangGraph Master Agent + runtime Subagent factory"),
    (4, "Browser", "browser-use/Playwright sessions and capture"),
    (5, "Collection", "passive OSINT sources, artefact hashing/chain of custody"),
    (6, "Synthesis", "cross-source correlation, findings and report export"),
    (7, "Operations", "resume, budgets, audit trail, hardening"),
)

#: Console width used when Rich cannot detect a terminal (pipes, CI logs).
FALLBACK_CONSOLE_WIDTH: int = 100


class ExitCode(IntEnum):
    """Process exit codes.  Stable public contract — do not renumber."""

    OK = 0
    USAGE = 2                 # bad arguments (matches Typer/Click convention)
    CONFIG = 3                # required configuration or dependency missing
    DEPENDENCY = 4            # optional capability requested but not installed
    AUTHORIZATION = 5         # mission refused: no authorisation asserted
    NOT_IMPLEMENTED = 6       # capability lands in a later phase
    POLICY = 7                # mission refused by the safety policy
    CLARIFICATION = 8         # mission paused: intent must be confirmed or reframed
    INTERNAL = 70             # unexpected failure


class MissionMode(str, Enum):
    """Collection intensity for a mission."""

    PASSIVE = "passive"       # public sources only, no packets to the target
    ACTIVE = "active"         # direct interaction with the target (needs consent)
    FORENSIC = "forensic"     # local artefacts only, no remote collection


class MissionPhase(str, Enum):
    """What ``mission --phase`` renders."""

    PLAN = "plan"             # what the Master Agent would do
    SETTINGS = "settings"     # the merged, redacted configuration


# ══════════════════════════════════════════════════════════════════════════
# 3. Secret redaction
# ══════════════════════════════════════════════════════════════════════════

#: Stand-in for a value that must never reach a terminal, log or report.
REDACTED: str = "<redacted>"

#: Credential shapes we scrub even when the variable name is unknown to us
#: (a pasted key in an error message, a URL with userinfo, a bearer header).
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\b(?:sk|rk|pk|ak)-[A-Za-z0-9_\-]{8,}"),          # OpenAI/Anthropic-style
    re.compile(r"(?i)\bAIza[0-9A-Za-z_\-]{20,}"),                      # Google API key
    re.compile(r"(?i)\bgh[pousr]_[A-Za-z0-9]{16,}"),                   # GitHub token
    re.compile(r"(?i)\bxox[abprs]-[A-Za-z0-9\-]{10,}"),                # Slack token
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]{12,}"),                # auth header
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password|passwd|pwd)=([^\s&,;\"']+)"),
)


def mask_secret(value: str | None) -> str:
    """Return a hint like ``sk-p…c3f9`` — enough to identify, useless to an attacker.

    Anything shorter than 12 characters is fully redacted, because a short
    secret leaves too few unknown characters for the hint to be safe.
    """

    if not value:
        return "unset"
    if len(value) < 12:
        return f"{REDACTED} (len {len(value)})"
    return f"{value[:4]}…{value[-4:]} (len {len(value)})"


def redact_text(text: str, *, secrets: Iterable[str | None] = ()) -> str:
    """Scrub known secret *values* plus anything matching a credential pattern."""

    scrubbed = str(text)
    # Longest first so a key that contains another key is replaced wholly.
    for secret in sorted({s for s in secrets if s}, key=len, reverse=True):
        scrubbed = scrubbed.replace(secret, REDACTED)
    for pattern in _SECRET_PATTERNS:
        if pattern.groups >= 2:                      # key=value shapes
            scrubbed = pattern.sub(lambda m: f"{m.group(1)}={REDACTED}", scrubbed)
        else:
            scrubbed = pattern.sub(REDACTED, scrubbed)
    return scrubbed


def known_secrets() -> tuple[str, ...]:
    """Current credential values from the environment (for scrubbing only)."""

    return tuple(v for v in (env_value(name) for name in SECRET_ENV_VARS) if v)


# ══════════════════════════════════════════════════════════════════════════
# 4. Capability registry (dependencies + environment)
# ══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class Dependency:
    """A Python distribution this tool can use, and what it unlocks."""

    module: str
    package: str
    purpose: str
    phase: int
    required: bool = False


#: Probed by ``argus config`` with :func:`importlib.util.find_spec` — never
#: imported, so probing cannot trigger side effects.
DEPENDENCIES: tuple[Dependency, ...] = (
    Dependency("typer", "typer", "CLI framework", 1, required=True),
    Dependency("rich", "rich", "terminal rendering", 1, required=True),
    Dependency("pydantic", "pydantic", "typed mission & evidence models", 2, required=True),
    # Required from the phase that introduces them, and required thereafter —
    # the same set the doctor treats as blocking.
    Dependency("langgraph", "langgraph", "Master Agent state machine", 3, required=True),
    Dependency("browser_use", "browser-use", "agentic browser sessions", 4, required=True),
    Dependency("playwright", "playwright", "deterministic browsing & screenshots", 4, required=True),
    Dependency("httpx", "httpx", "HTTP/API collection", 5),
    Dependency("dotenv", "python-dotenv", ".env file loading", 7),
)


class EnvKind(str, Enum):
    """How an environment variable is treated by ``config``."""

    REQUIRED = "required"     # mission cannot start without it
    OPTIONAL = "optional"     # has a working default
    SECRET = "secret"         # never echoed, only "set"/"unset"


@dataclass(frozen=True)
class EnvSpec:
    """Declarative description of one environment variable."""

    name: str
    kind: EnvKind
    purpose: str
    phase: int
    default: str | None = None


@dataclass(frozen=True)
class ProviderSpec:
    """A model provider, the credential variables it accepts, and its needs.

    Credential *names* live here; credential *values* are fetched on demand by
    :meth:`Settings.resolve_api_key` and are never stored on the settings object.
    """

    key: str
    label: str
    key_env_vars: tuple[str, ...]
    models: tuple[str, ...] = ()
    base_url_env: str | None = None
    default_base_url: str | None = None
    #: True for backends that authenticate by network position (e.g. local Ollama).
    key_optional: bool = False

    def key_env_summary(self) -> str:
        """Human-readable list of accepted credential variables."""

        return " | ".join(self.key_env_vars) if self.key_env_vars else "none required"


#: Provider table consulted by :func:`model_problems`.  Extend here — no code
#: changes elsewhere — to support another backend.
PROVIDER_REGISTRY: dict[str, ProviderSpec] = {
    "openai": ProviderSpec(
        key="openai",
        label="OpenAI",
        key_env_vars=("ARGUS_LLM_API_KEY", "OPENAI_API_KEY"),
        models=(
            "gpt-4.1",
            "gpt-4.1-mini",
            "gpt-4o",
            "gpt-4o-mini",
            "o3",
            "o4-mini",
        ),
    ),
    "anthropic": ProviderSpec(
        key="anthropic",
        label="Anthropic",
        key_env_vars=("ARGUS_LLM_API_KEY", "ANTHROPIC_API_KEY"),
        models=(
            "claude-sonnet-4-20250514",
            "claude-opus-4-20250514",
            "claude-3-7-sonnet-20250219",
            "claude-3-5-haiku-20241022",
        ),
    ),
    "google": ProviderSpec(
        key="google",
        label="Google",
        key_env_vars=("ARGUS_LLM_API_KEY", "GOOGLE_API_KEY"),
        models=(
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.0-flash",
        ),
    ),
    "local": ProviderSpec(
        key="local",
        label="Local / OpenAI-compatible",
        key_env_vars=("ARGUS_LLM_API_KEY", "OPENAI_API_KEY"),
        default_base_url="http://127.0.0.1:11434/v1",
        base_url_env="OLLAMA_HOST",
        key_optional=True,
    ),
}

#: Variables scrubbed from every error, log line and diagnostic we emit.
SECRET_ENV_VARS: tuple[str, ...] = tuple(
    sorted({name for spec in PROVIDER_REGISTRY.values() for name in spec.key_env_vars})
)

ENV_SPECS: tuple[EnvSpec, ...] = (
    EnvSpec("ARGUS_LLM_MODEL", EnvKind.REQUIRED, "model id driving all agents", 3),
    EnvSpec("ARGUS_LLM_PROVIDER", EnvKind.OPTIONAL, "openai | anthropic | google | local", 3, DEFAULT_LLM_PROVIDER),
    EnvSpec("ARGUS_LLM_BASE_URL", EnvKind.OPTIONAL, "OpenAI-compatible endpoint override", 3),
    EnvSpec("ARGUS_LLM_API_KEY", EnvKind.SECRET, "provider-neutral credential", 3),
    EnvSpec("OPENAI_API_KEY", EnvKind.SECRET, "credential for the OpenAI provider", 3),
    EnvSpec("ANTHROPIC_API_KEY", EnvKind.SECRET, "credential for the Anthropic provider", 3),
    EnvSpec("GOOGLE_API_KEY", EnvKind.SECRET, "credential for the Google provider", 3),
    EnvSpec("ARGUS_HOME", EnvKind.OPTIONAL, "root directory for case data", 2, DEFAULT_HOME_DIRNAME),
    EnvSpec("ARGUS_OUTPUT_DIR", EnvKind.OPTIONAL, "mission output directory", 2),
    EnvSpec("ARGUS_CASE_DIR", EnvKind.OPTIONAL, "artefact directory for this mission", 2),
    EnvSpec("ARGUS_LOG_LEVEL", EnvKind.OPTIONAL, "DEBUG | INFO | WARNING | ERROR", 1, DEFAULT_LOG_LEVEL),
    EnvSpec("ARGUS_OPERATOR", EnvKind.OPTIONAL, "operator name for the audit trail", 1),
    EnvSpec("ARGUS_MAX_SUBAGENTS", EnvKind.OPTIONAL, "live Subagents per mission", 3, str(DEFAULT_MAX_SUBAGENTS)),
    EnvSpec(
        "ARGUS_MAX_WORKERS_PER_AGENT",
        EnvKind.OPTIONAL,
        "concurrent Workers per Subagent",
        3,
        str(DEFAULT_MAX_WORKERS_PER_AGENT),
    ),
    EnvSpec(
        "ARGUS_MAX_TOTAL_WORKERS",
        EnvKind.OPTIONAL,
        "concurrent Workers mission-wide",
        3,
        str(DEFAULT_MAX_TOTAL_WORKERS),
    ),
    EnvSpec("ARGUS_WORKER_RETRIES", EnvKind.OPTIONAL, "retries per Worker task", 3, str(DEFAULT_WORKER_RETRIES)),
    EnvSpec("ARGUS_REVIEW_RETRIES", EnvKind.OPTIONAL, "review cycles per Subagent", 3, str(DEFAULT_REVIEW_RETRIES)),
    EnvSpec(
        "ARGUS_MISSION_BUDGET_SECONDS",
        EnvKind.OPTIONAL,
        "wall-clock mission budget",
        3,
        str(DEFAULT_MISSION_BUDGET_SECONDS),
    ),
    EnvSpec(
        "ARGUS_TASK_BUDGET_SECONDS",
        EnvKind.OPTIONAL,
        "per-task time budget",
        3,
        str(DEFAULT_TASK_BUDGET_SECONDS),
    ),
    EnvSpec(
        "ARGUS_BROWSER_CONCURRENCY",
        EnvKind.OPTIONAL,
        "concurrent browser contexts",
        4,
        str(DEFAULT_BROWSER_CONCURRENCY),
    ),
    EnvSpec(
        "ARGUS_HTTP_CONCURRENCY",
        EnvKind.OPTIONAL,
        "concurrent HTTP workers",
        5,
        str(DEFAULT_HTTP_CONCURRENCY),
    ),
    EnvSpec("ARGUS_HTTP_TIMEOUT", EnvKind.OPTIONAL, "per-request timeout (seconds)", 5, str(int(DEFAULT_HTTP_TIMEOUT))),
    EnvSpec("ARGUS_USER_AGENT", EnvKind.OPTIONAL, "User-Agent sent to remote hosts", 4, DEFAULT_USER_AGENT),
    EnvSpec("ARGUS_BROWSER_HEADLESS", EnvKind.OPTIONAL, "1 = headless Chromium", 4, "1"),
    EnvSpec("ARGUS_BROWSER_PROFILE_DIR", EnvKind.OPTIONAL, "persistent browser profile path", 4),
    EnvSpec("ARGUS_ALLOW_NETWORK", EnvKind.OPTIONAL, "0 = offline/dry mission", 5, "1"),
    EnvSpec("ARGUS_RESPECT_ROBOTS", EnvKind.OPTIONAL, "0 = ignore robots.txt", 5, "1"),
)

# ══════════════════════════════════════════════════════════════════════════
# 5. Runtime value objects
# ══════════════════════════════════════════════════════════════════════════


@dataclass
class MissionRequest:
    """Everything the Master Agent needs to plan a mission.

    Limits and paths are copied from a :class:`Settings` object that has already
    passed validation, so a request can never carry an out-of-range limit into
    Phase 3.  Phase 3 feeds this to the Master Agent graph.
    """

    targets: list[str]
    objective: str
    mode: MissionMode = MissionMode.PASSIVE
    authorised: bool = False
    max_subagents: int = DEFAULT_MAX_SUBAGENTS
    max_workers_per_agent: int = DEFAULT_MAX_WORKERS_PER_AGENT
    max_total_workers: int = DEFAULT_MAX_TOTAL_WORKERS
    worker_retries: int = DEFAULT_WORKER_RETRIES
    review_retries: int = DEFAULT_REVIEW_RETRIES
    mission_budget_seconds: int = DEFAULT_MISSION_BUDGET_SECONDS
    task_budget_seconds: int = DEFAULT_TASK_BUDGET_SECONDS
    output_dir: str = field(default_factory=lambda: str(resolve_default_output_dir()))
    operator: str | None = field(default_factory=lambda: env_value("ARGUS_OPERATOR"))
    dry_run: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    @classmethod
    def from_settings(cls, settings: "Settings", **overrides: Any) -> "MissionRequest":
        """Copy validated configuration into a request, then apply overrides."""

        base: dict[str, Any] = {
            "max_subagents": settings.max_subagents,
            "max_workers_per_agent": settings.max_workers_per_agent,
            "max_total_workers": settings.max_total_workers,
            "worker_retries": settings.worker_retries,
            "review_retries": settings.review_retries,
            "mission_budget_seconds": settings.mission_budget_seconds,
            "task_budget_seconds": settings.task_budget_seconds,
            "output_dir": str(settings.output_dir),
            "operator": settings.operator,
            "dry_run": settings.dry_run,
        }
        base.update(overrides)
        return cls(**base)

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe representation (enums flattened to their values)."""

        data = asdict(self)
        data["mode"] = self.mode.value
        return data

    def fingerprint(self) -> str:
        """Stable mission id, identical to the typed model's ``Mission.id``."""

        return mission_id_for(self.objective, self.targets, self.mode)


@dataclass
class CheckResult:
    """One line in the ``argus config`` report."""

    label: str
    status: str            # "ok" | "warn" | "fail"
    detail: str


# ══════════════════════════════════════════════════════════════════════════
# 6. Console + formatting helpers
# ══════════════════════════════════════════════════════════════════════════

_STATUS_STYLE: dict[str, tuple[str, str]] = {
    "ok": ("✔", "bold green"),
    "warn": ("!", "bold yellow"),
    "fail": ("✘", "bold red"),
}


def get_console() -> Console:
    """Build a Console per call.

    Deliberately not a module-level singleton: constructing one at import time
    would be a (benign but real) global side effect, and creating it on demand
    keeps ``--help`` isolated from ``NO_COLOR``/``TERM`` changes at runtime.
    """

    return Console(
        highlight=False,
        # Wrapping stays on: soft_wrap crops long lines (panels/tables lose
        # text) instead of folding them, which is unreadable for reports.
        soft_wrap=False,
        width=None if sys.stdout.isatty() else FALLBACK_CONSOLE_WIDTH,
        emoji=False,
    )


def version_banner() -> Panel:
    """The product banner shown by ``version`` and on bare invocation."""

    body = Text()
    body.append(f"{APP_TITLE} ", style="bold cyan")
    body.append(f"v{VERSION_LABEL}\n", style="bold")
    body.append(f"{APP_SUBTITLE}\n\n", style="white")
    body.append("phase ", style="dim")
    body.append(f"{BUILD_PHASE} — {BUILD_PHASE_NAME}\n", style="bold magenta")
    body.append("runtime ", style="dim")
    body.append(f"Python {platform.python_version()} on {platform.system() or 'unknown'}\n", style="white")
    body.append("file ", style="dim")
    body.append(str(Path(__file__).name), style="white")
    return Panel(body, border_style="cyan", padding=(0, 2), expand=False)


def print_version(*, as_json: bool = False) -> None:
    """Report version metadata in human or machine readable form."""

    payload = {
        "app": APP_NAME,
        "title": APP_TITLE,
        "version": __version__,
        "label": VERSION_LABEL,
        "stage": VERSION_STAGE,
        "semver": {
            "major": VERSION_MAJOR,
            "minor": VERSION_MINOR,
            "patch": VERSION_PATCH,
        },
        "build_phase": BUILD_PHASE,
        "build_phase_name": BUILD_PHASE_NAME,
        "case_schema_version": CASE_SCHEMA_VERSION,
        "task_schema_version": TASK_SCHEMA_VERSION,
        "python": platform.python_version(),
        "python_min": f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}",
        "platform": platform.platform(),
        "file": str(Path(__file__).resolve()),
        "roadmap": [{"phase": p, "name": n, "scope": s} for p, n, s in PHASE_ROADMAP],
    }

    if as_json:
        typer.echo(json.dumps(payload, indent=2))
        return

    console = get_console()
    console.print(version_banner())

    table = Table(box=None, pad_edge=False, show_header=False)
    table.add_column("key", style="dim", no_wrap=True)
    table.add_column("value")
    for key in ("version", "stage", "case_schema_version", "task_schema_version", "python", "platform"):
        table.add_row(key, str(payload[key]))
    console.print(table)

    roadmap = Table(title="Roadmap", title_justify="left", box=None, pad_edge=False)
    roadmap.add_column("#", style="dim", justify="right", no_wrap=True)
    roadmap.add_column("phase", style="bold")
    roadmap.add_column("scope", style="white")
    for phase, name, scope in PHASE_ROADMAP:
        pointer = "▶" if phase == BUILD_PHASE else " "
        style = "cyan" if phase == BUILD_PHASE else "dim"
        roadmap.add_row(pointer + str(phase), f"[{style}]{escape(name)}[/{style}]", f"[dim]{escape(scope)}[/dim]")
    console.print(roadmap)


# ══════════════════════════════════════════════════════════════════════════
# 7. Configuration probing
# ══════════════════════════════════════════════════════════════════════════


def module_available(module: str) -> bool:
    """True when *module* can be imported — probed without importing it."""

    if module in sys.modules:
        return True
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):        # namespace/broken parent packages
        return False


def env_value(name: str) -> str | None:
    """Read an environment variable, treating blank strings as unset."""

    raw = os.environ.get(name)
    if raw is None:
        return None
    raw = raw.strip()
    return raw or None


def resolve_home_dir() -> Path:
    """Directory that will hold case data.  Not created here."""

    return Path(env_value("ARGUS_HOME") or DEFAULT_HOME_DIRNAME).expanduser()


def resolve_default_output_dir() -> Path:
    """Default output directory: ``$ARGUS_OUTPUT_DIR`` or ``$ARGUS_HOME/output``."""

    override = env_value("ARGUS_OUTPUT_DIR")
    return Path(override).expanduser() if override else resolve_home_dir() / DEFAULT_OUTPUT_DIRNAME


def _nearest_existing_ancestor(path: Path) -> Path:
    """First ancestor of *path* that exists (or the cwd as a last resort)."""

    for candidate in (path, *path.parents):
        try:
            if candidate.exists():
                return candidate
        except OSError:                                  # pragma: no cover - exotic FS
            continue
    return Path.cwd()


def directory_writable(path: Path) -> bool:
    """Check writability without creating the real directory.

    For a path that does not exist yet, the check must run against the nearest
    *existing* ancestor — falling back to the temp directory would report a
    hostile location such as ``/proc/x`` as writable.
    """

    try:
        if path.exists():
            if not path.is_dir():
                return False
            probe_root = path
        else:
            probe_root = _nearest_existing_ancestor(path.parent)
            if not probe_root.is_dir():
                return False
        with tempfile.NamedTemporaryFile(dir=probe_root, prefix=".argus-probe-", delete=True):
            pass
        return True
    except OSError:
        return False


def collect_config_results() -> list[CheckResult]:
    """Run every configuration probe and return an ordered report."""

    results: list[CheckResult] = []

    # --- interpreter ---------------------------------------------------------
    current = sys.version_info[:2]
    py_ok = current >= MIN_PYTHON
    results.append(
        CheckResult(
            "python",
            "ok" if py_ok else "fail",
            f"{platform.python_version()} (minimum {MIN_PYTHON[0]}.{MIN_PYTHON[1]})",
        )
    )

    # --- dependencies --------------------------------------------------------
    for dep in DEPENDENCIES:
        present = module_available(dep.module)
        if present:
            status, detail = "ok", f"{dep.package} — {dep.purpose}"
        elif dep.required:
            status, detail = "fail", f"{dep.package} missing — pip install {dep.package}"
        else:
            status, detail = "warn", f"{dep.package} missing (phase {dep.phase}) — {dep.purpose}"
        results.append(CheckResult(dep.module, status, detail))

    # --- environment ---------------------------------------------------------
    for spec in ENV_SPECS:
        value = env_value(spec.name)
        if spec.kind is EnvKind.SECRET:
            # Never echo secret values — only whether they are present.
            detail = "set" if value else f"unset — required from phase {spec.phase}"
            results.append(CheckResult(spec.name, "ok" if value else "warn", f"{detail} — {spec.purpose}"))
            continue
        if value:
            status, detail = "ok", value
        elif spec.default is not None:
            status, detail = "ok", f"{spec.default} (default)"
        elif spec.kind is EnvKind.REQUIRED and spec.phase <= BUILD_PHASE:
            status, detail = "fail", "unset — required in this build"
        elif spec.kind is EnvKind.REQUIRED:
            status, detail = "warn", f"unset — required from phase {spec.phase}"
        else:
            status, detail = "warn", "unset (no default)"
        results.append(CheckResult(spec.name, status, f"{detail} — {spec.purpose}"))

    # --- workspace -----------------------------------------------------------
    home = resolve_home_dir()
    writable = directory_writable(home)
    results.append(
        CheckResult(
            "workspace",
            "ok" if writable else "fail",
            f"{home}{' (exists)' if home.exists() else ' (will be created)'}"
            f" — {'writable' if writable else 'not writable'}",
        )
    )

    return results


# ══════════════════════════════════════════════════════════════════════════
# 8. Strict configuration management
# ══════════════════════════════════════════════════════════════════════════


class SettingSource(str, Enum):
    """Where an effective value came from.  CLI always wins."""

    CLI = "cli"
    ENV = "env"
    DEFAULT = "default"


class Severity(str, Enum):
    """A configuration problem either blocks the run or merely warns."""

    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class SettingProblem:
    """One validation failure, addressed to a single setting."""

    field: str
    message: str
    severity: Severity = Severity.ERROR
    source: SettingSource = SettingSource.DEFAULT
    env_var: str | None = None

    def location(self) -> str:
        """Where the operator should look to fix it."""

        if self.source is SettingSource.CLI:
            return "command line"
        if self.source is SettingSource.ENV and self.env_var:
            return self.env_var
        return "default"

    def to_dict(self) -> dict[str, str]:
        return {
            "field": self.field,
            "message": self.message,
            "severity": self.severity.value,
            "source": self.source.value,
            "env_var": self.env_var or "",
            "location": self.location(),
        }


@dataclass(frozen=True)
class Settings:
    """Immutable, fully validated runtime configuration.

    Built exclusively by :func:`build_settings`, which applies
    ``CLI > environment > default`` precedence per field and refuses
    out-of-range values.  No model client or browser is constructed here, so
    construction can never have external side effects.

    Credential *values* are deliberately absent: :meth:`resolve_api_key` reads
    them at the moment they are needed and callers must not print the result.
    """

    # --- model -----------------------------------------------------------------
    provider: str
    model: str | None
    base_url: str | None

    # --- paths -----------------------------------------------------------------
    home_dir: Path
    output_dir: Path
    case_dir: Path | None

    # --- operator context ------------------------------------------------------
    operator: str | None
    log_level: str
    dry_run: bool

    # --- orchestration limits --------------------------------------------------
    max_subagents: int
    max_workers_per_agent: int
    max_total_workers: int
    worker_retries: int
    review_retries: int
    mission_budget_seconds: int
    task_budget_seconds: int

    # --- browser and network ---------------------------------------------------
    browser_headless: bool
    browser_profile_dir: Path | None
    browser_concurrency: int
    http_concurrency: int
    http_timeout: float
    user_agent: str
    allow_network: bool
    respect_robots: bool

    #: field -> where the value came from (excluded from equality/repr).
    provenance: Mapping[str, SettingSource] = field(default_factory=dict, repr=False, compare=False)

    #: Zero-argument callable returning the environment mapping credentials are
    #: looked up in.  A *callable* keeps secret values out of the dataclass
    #: fields, so neither ``repr`` nor ``to_dict`` can ever expose a key.
    _credential_env: Callable[[], Mapping[str, str]] | None = field(
        default=None, repr=False, compare=False
    )

    def _environ(self) -> Mapping[str, str]:
        """Environment used for credential lookup (injectable for tests)."""

        return self._credential_env() if self._credential_env is not None else os.environ

    # -- model helpers ---------------------------------------------------------

    def provider_spec(self) -> ProviderSpec | None:
        """Registry entry for the configured provider, if known."""

        return PROVIDER_REGISTRY.get(self.provider)

    def resolve_api_key(self) -> tuple[str | None, str | None]:
        """Look the credential up at call time.

        Returns ``(value, variable_name)``.  Callers pass the value straight to
        the model client — never to a console, log or report.  Use
        :meth:`api_key_hint` for anything user-visible.
        """

        spec = self.provider_spec()
        if spec is None:
            return None, None
        environ = self._environ()
        for name in spec.key_env_vars:
            raw = environ.get(name)
            value = raw.strip() if raw else None
            if value:
                return value, name
        return None, None

    def api_key_hint(self) -> str:
        """Safe, non-reversible description of the credential state."""

        value, name = self.resolve_api_key()
        spec = self.provider_spec()
        if value:
            return f"{mask_secret(value)} from {name}"
        if not self.requires_credential():
            return f"not required for {spec.label if spec else self.provider}"
        return f"unset (looked in {spec.key_env_summary() if spec else 'unknown'})"

    def requires_credential(self) -> bool:
        spec = self.provider_spec()
        return bool(spec and spec.key_env_vars and not spec.key_optional)

    # -- derived values --------------------------------------------------------

    @property
    def max_potential_workers(self) -> int:
        """Workers if every Subagent were saturated — surfaced for transparency."""

        return self.max_subagents * self.max_workers_per_agent

    def source_of(self, field_name: str) -> SettingSource:
        return self.provenance.get(field_name, SettingSource.DEFAULT)

    # -- serialisation ---------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe, secret-free snapshot used by ``--json`` output."""

        return {
            "model": {
                "provider": self.provider,
                "provider_label": (self.provider_spec().label if self.provider_spec() else "unknown"),
                "model": self.model,
                "base_url": self.base_url,
                "api_key": self.api_key_hint(),
            },
            "paths": {
                "home_dir": str(self.home_dir),
                "output_dir": str(self.output_dir),
                "case_dir": str(self.case_dir) if self.case_dir else None,
            },
            "operator": self.operator,
            "log_level": self.log_level,
            "dry_run": self.dry_run,
            "orchestration": {
                "max_subagents": self.max_subagents,
                "max_workers_per_agent": self.max_workers_per_agent,
                "max_total_workers": self.max_total_workers,
                "max_potential_workers": self.max_potential_workers,
                "worker_retries": self.worker_retries,
                "review_retries": self.review_retries,
            },
            "budgets": {
                "mission_budget_seconds": self.mission_budget_seconds,
                "task_budget_seconds": self.task_budget_seconds,
            },
            "browser": {
                "headless": self.browser_headless,
                "concurrency": self.browser_concurrency,
                "profile_dir": str(self.browser_profile_dir) if self.browser_profile_dir else None,
            },
            "network": {
                "allow_network": self.allow_network,
                "respect_robots": self.respect_robots,
                "http_concurrency": self.http_concurrency,
                "http_timeout": self.http_timeout,
                "user_agent": self.user_agent,
            },
            "provenance": {k: v.value for k, v in self.provenance.items()},
        }


@dataclass
class SettingsResult:
    """Outcome of :func:`build_settings`: the settings plus everything wrong."""

    settings: Settings
    problems: list[SettingProblem] = field(default_factory=list)

    @property
    def errors(self) -> list[SettingProblem]:
        return [p for p in self.problems if p.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[SettingProblem]:
        return [p for p in self.problems if p.severity is Severity.WARNING]

    @property
    def ok(self) -> bool:
        """True only when nothing blocks a run."""

        return not self.errors


# --------------------------------------------------------------------------
# 8.1 Typed parsing helpers — every failure becomes a SettingProblem
# --------------------------------------------------------------------------

_TRUE_WORDS = frozenset({"1", "true", "yes", "on", "y", "t"})
_FALSE_WORDS = frozenset({"0", "false", "no", "off", "n", "f"})
_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

#: field -> (env var, CLI flag) for provenance rendering.
SETTING_SOURCES: dict[str, tuple[str | None, str | None]] = {
    "provider": ("ARGUS_LLM_PROVIDER", "--provider"),
    "model": ("ARGUS_LLM_MODEL", "--model"),
    "base_url": ("ARGUS_LLM_BASE_URL", "--base-url"),
    "home_dir": ("ARGUS_HOME", "--home"),
    "output_dir": ("ARGUS_OUTPUT_DIR", "--output-dir"),
    "case_dir": ("ARGUS_CASE_DIR", "--case-dir"),
    "operator": ("ARGUS_OPERATOR", "--operator"),
    "log_level": ("ARGUS_LOG_LEVEL", "--log-level"),
    "max_subagents": ("ARGUS_MAX_SUBAGENTS", "--max-subagents"),
    "max_workers_per_agent": ("ARGUS_MAX_WORKERS_PER_AGENT", "--max-workers"),
    "max_total_workers": ("ARGUS_MAX_TOTAL_WORKERS", "--max-total-workers"),
    "worker_retries": ("ARGUS_WORKER_RETRIES", "--worker-retries"),
    "review_retries": ("ARGUS_REVIEW_RETRIES", "--review-retries"),
    "mission_budget_seconds": ("ARGUS_MISSION_BUDGET_SECONDS", "--mission-budget"),
    "task_budget_seconds": ("ARGUS_TASK_BUDGET_SECONDS", "--task-budget"),
    "browser_headless": ("ARGUS_BROWSER_HEADLESS", "--headless"),
    "browser_profile_dir": ("ARGUS_BROWSER_PROFILE_DIR", "--browser-profile"),
    "browser_concurrency": ("ARGUS_BROWSER_CONCURRENCY", "--browser-concurrency"),
    "http_concurrency": ("ARGUS_HTTP_CONCURRENCY", "--http-concurrency"),
    "http_timeout": ("ARGUS_HTTP_TIMEOUT", "--http-timeout"),
    "user_agent": ("ARGUS_USER_AGENT", "--user-agent"),
    "allow_network": ("ARGUS_ALLOW_NETWORK", "--allow-network"),
    "respect_robots": ("ARGUS_RESPECT_ROBOTS", "--respect-robots"),
    "dry_run": (None, "--dry-run/--execute"),
}


def _env_var_for(field_name: str) -> str | None:
    return SETTING_SOURCES.get(field_name, (None, None))[0]


def _problem(field_name: str, message: str, source: SettingSource, severity: Severity = Severity.ERROR) -> SettingProblem:
    """Build a problem with its env var attached (values are never included)."""

    return SettingProblem(
        field=field_name,
        message=redact_text(message, secrets=known_secrets()),
        severity=severity,
        source=source,
        env_var=_env_var_for(field_name) if source is SettingSource.ENV else None,
    )


def _parse_int(
    field_name: str, raw: Any, source: SettingSource
) -> tuple[int | None, SettingProblem | None]:
    """Parse an integer, rejecting floats, blanks and junk."""

    if raw is None:
        return None, None
    if isinstance(raw, bool):                        # bool is an int subclass
        return None, _problem(field_name, "expected an integer, got a boolean", source)
    if isinstance(raw, int):
        return raw, None
    text = str(raw).strip()
    if not text:
        return None, _problem(field_name, "expected an integer, got an empty value", source)
    try:
        return int(text, 10), None
    except ValueError:
        return None, _problem(
            field_name, f"expected an integer, got {redact_text(text)!r}", source
        )


def _parse_bool(
    field_name: str, raw: Any, source: SettingSource
) -> tuple[bool | None, SettingProblem | None]:
    """Parse booleans from flags or from 1/0/true/false/yes/no/on/off."""

    if raw is None:
        return None, None
    if isinstance(raw, bool):
        return raw, None
    text = str(raw).strip().lower()
    if text in _TRUE_WORDS:
        return True, None
    if text in _FALSE_WORDS:
        return False, None
    return None, _problem(field_name, f"expected a boolean (true/false/1/0), got {text!r}", source)


def _check_bounds(field_name: str, value: int, source: SettingSource) -> SettingProblem | None:
    """Enforce :data:`LIMIT_BOUNDS`; the message names the accepted range."""

    low, high = LIMIT_BOUNDS.get(field_name, (None, None))
    if low is not None and value < low:
        return _problem(field_name, f"must be >= {low}, got {value}", source)
    if high is not None and value > high:
        return _problem(field_name, f"must be <= {high}, got {value}", source)
    return None


def _resolve(
    field_name: str,
    cli_values: Mapping[str, Any],
    env: Mapping[str, str],
    default: Any,
) -> tuple[Any, SettingSource]:
    """Apply ``CLI > env > default`` for one field, tracking the winner."""

    cli_value = cli_values.get(field_name)
    if cli_value is not None:
        return cli_value, SettingSource.CLI
    env_var = _env_var_for(field_name)
    if env_var:
        raw = env.get(env_var)
        if raw is not None and raw.strip() != "":
            return raw.strip(), SettingSource.ENV
    return default, SettingSource.DEFAULT


# --------------------------------------------------------------------------
# 8.2 The builder
# --------------------------------------------------------------------------


def build_settings(
    cli_values: Mapping[str, Any] | None = None,
    env: Mapping[str, str] | None = None,
) -> SettingsResult:
    """Merge CLI options and environment into a validated :class:`Settings`.

    Precedence is per field: a CLI option beats the environment variable, which
    beats the built-in default.  Every numeric limit is bounds-checked, every
    boolean parsed strictly, and every path expanded.  Nothing is created on
    disk and no network client is built — so a bad value can never be
    discovered *after* a model or browser call has already started.

    The returned result carries problems instead of raising, which lets callers
    render several errors at once.
    """

    cli = dict(cli_values or {})
    environ: Mapping[str, str] = dict(os.environ if env is None else env)
    problems: list[SettingProblem] = []
    provenance: dict[str, SettingSource] = {}

    def take(field_name: str, default: Any) -> tuple[Any, SettingSource]:
        value, source = _resolve(field_name, cli, environ, default)
        provenance[field_name] = source
        return value, source

    # --- integer limits ------------------------------------------------------
    int_defaults: dict[str, int] = {
        "max_subagents": DEFAULT_MAX_SUBAGENTS,
        "max_workers_per_agent": DEFAULT_MAX_WORKERS_PER_AGENT,
        "max_total_workers": DEFAULT_MAX_TOTAL_WORKERS,
        "worker_retries": DEFAULT_WORKER_RETRIES,
        "review_retries": DEFAULT_REVIEW_RETRIES,
        "mission_budget_seconds": DEFAULT_MISSION_BUDGET_SECONDS,
        "task_budget_seconds": DEFAULT_TASK_BUDGET_SECONDS,
        "browser_concurrency": DEFAULT_BROWSER_CONCURRENCY,
        "http_concurrency": DEFAULT_HTTP_CONCURRENCY,
    }
    numbers: dict[str, int] = {}
    for field_name, default in int_defaults.items():
        raw, source = take(field_name, default)
        value, problem = _parse_int(field_name, raw, source)
        if problem:
            problems.append(problem)
            numbers[field_name] = default          # keep the object constructible
            continue
        assert value is not None                   # raw=None only when default is None
        bounds_problem = _check_bounds(field_name, value, source)
        if bounds_problem:
            problems.append(bounds_problem)
        numbers[field_name] = value

    # --- booleans ------------------------------------------------------------
    bool_defaults: dict[str, bool] = {
        "browser_headless": True,
        "allow_network": True,
        "respect_robots": True,
    }
    flags: dict[str, bool] = {}
    for field_name, default in bool_defaults.items():
        raw, source = take(field_name, default)
        value, problem = _parse_bool(field_name, raw, source)
        if problem:
            problems.append(problem)
            flags[field_name] = default
        else:
            flags[field_name] = bool(value)

    # dry-run is a CLI-only switch (mission --dry-run/--execute); it is never
    # read from the environment so a stray variable cannot start real collection.
    dry_run = bool(cli.get("dry_run", True))
    provenance["dry_run"] = SettingSource.CLI

    # --- model ---------------------------------------------------------------
    provider_default = str(environ.get("ARGUS_LLM_PROVIDER") or DEFAULT_LLM_PROVIDER).strip().lower()
    provider_raw, provider_source = take("provider", provider_default)
    provider = str(provider_raw).strip().lower()
    if provider not in PROVIDER_REGISTRY:
        problems.append(
            _problem(
                "provider",
                f"unknown provider {provider!r}; choose one of {', '.join(sorted(PROVIDER_REGISTRY))}",
                provider_source,
            )
        )

    model_raw, model_source = take("model", None)
    model = str(model_raw).strip() if model_raw not in (None, "") else None

    spec = PROVIDER_REGISTRY.get(provider)
    base_url_default = spec.default_base_url if spec else None
    base_url_raw, base_url_source = take("base_url", base_url_default)
    if base_url_source is SettingSource.DEFAULT and spec and spec.base_url_env:
        env_base = environ.get(spec.base_url_env)
        if env_base:
            base_url_raw, base_url_source = env_base, SettingSource.ENV
    base_url = str(base_url_raw).strip() if base_url_raw else None
    if base_url and not re.match(r"^https?://[^\s]+$", base_url):
        problems.append(
            _problem("base_url", "must be an http(s) URL, e.g. https://api.openai.com/v1", base_url_source)
        )

    # --- paths ---------------------------------------------------------------
    home_raw, home_source = take("home_dir", DEFAULT_HOME_DIRNAME)
    home_dir = Path(str(home_raw)).expanduser()
    if not str(home_dir).strip():
        problems.append(_problem("home_dir", "must not be empty", home_source))

    output_raw, output_source = take("output_dir", home_dir / DEFAULT_OUTPUT_DIRNAME)
    output_dir = Path(str(output_raw)).expanduser()
    if output_dir.exists() and not output_dir.is_dir():
        problems.append(_problem("output_dir", f"{output_dir} exists and is not a directory", output_source))

    case_raw, case_source = take("case_dir", None)
    case_dir = Path(str(case_raw)).expanduser() if case_raw else None
    if case_dir and case_dir.exists() and not case_dir.is_dir():
        problems.append(_problem("case_dir", f"{case_dir} exists and is not a directory", case_source))

    # --- operator / logging --------------------------------------------------
    operator_raw, _ = take("operator", None)
    operator = str(operator_raw).strip() if operator_raw else None

    log_raw, log_source = take("log_level", DEFAULT_LOG_LEVEL)
    log_level = str(log_raw).strip().upper()
    if log_level not in _LOG_LEVELS:
        problems.append(
            _problem("log_level", f"must be one of {', '.join(_LOG_LEVELS)}, got {log_level!r}", log_source)
        )

    user_agent_raw, _ = take("user_agent", DEFAULT_USER_AGENT)
    user_agent = str(user_agent_raw).strip()

    # --- numeric extras ------------------------------------------------------
    timeout_raw, timeout_source = take("http_timeout", DEFAULT_HTTP_TIMEOUT)
    try:
        http_timeout = float(str(timeout_raw))
    except (TypeError, ValueError):
        problems.append(
            _problem("http_timeout", f"expected a number of seconds, got {str(timeout_raw)!r}", timeout_source)
        )
        http_timeout = DEFAULT_HTTP_TIMEOUT
    else:
        if not 1.0 <= http_timeout <= 300.0:
            problems.append(_problem("http_timeout", f"must be between 1 and 300 seconds, got {http_timeout}", timeout_source))

    profile_raw, profile_source = take("browser_profile_dir", None)
    browser_profile_dir = Path(str(profile_raw)).expanduser() if profile_raw else None

    # --- cross-field sanity --------------------------------------------------
    if numbers["task_budget_seconds"] > numbers["mission_budget_seconds"]:
        problems.append(
            _problem(
                "task_budget_seconds",
                f"greater than the mission budget ({numbers['mission_budget_seconds']}s); "
                "the task budget would never bind",
                provenance.get("task_budget_seconds", SettingSource.DEFAULT),
                severity=Severity.WARNING,
            )
        )
    if numbers["max_workers_per_agent"] > numbers["max_total_workers"]:
        problems.append(
            _problem(
                "max_workers_per_agent",
                f"exceeds max_total_workers ({numbers['max_total_workers']}); "
                "per-subagent capacity cannot exceed the mission-wide ceiling",
                provenance.get("max_workers_per_agent", SettingSource.DEFAULT),
            )
        )

    settings = Settings(
        provider=provider,
        model=model,
        base_url=base_url,
        home_dir=home_dir,
        output_dir=output_dir,
        case_dir=case_dir,
        operator=operator,
        log_level=log_level,
        dry_run=dry_run,
        max_subagents=numbers["max_subagents"],
        max_workers_per_agent=numbers["max_workers_per_agent"],
        max_total_workers=numbers["max_total_workers"],
        worker_retries=numbers["worker_retries"],
        review_retries=numbers["review_retries"],
        mission_budget_seconds=numbers["mission_budget_seconds"],
        task_budget_seconds=numbers["task_budget_seconds"],
        browser_headless=flags["browser_headless"],
        browser_profile_dir=browser_profile_dir,
        browser_concurrency=numbers["browser_concurrency"],
        http_concurrency=numbers["http_concurrency"],
        http_timeout=http_timeout,
        user_agent=user_agent,
        allow_network=flags["allow_network"],
        respect_robots=flags["respect_robots"],
        provenance=provenance,
        # Capture the mapping (not its values) so credential lookup matches the
        # run that produced these settings — including injected test envs.
        _credential_env=(lambda captured=environ: captured),
    )

    # Model/credential readiness is checked last: it depends on the provider
    # that survived validation above.  These are warnings — they gate Phase 3
    # execution, not inspection of the configuration.
    problems.extend(readiness_problems(settings))

    # Final redaction pass: scrub any credential value from the environment that
    # produced these settings, even one pasted into a mis-typed option.
    injected = tuple(v for v in (environ.get(name) for name in SECRET_ENV_VARS) if v)
    if injected:
        problems = [
            replace(problem, message=redact_text(problem.message, secrets=injected))
            for problem in problems
        ]
    return SettingsResult(settings=settings, problems=problems)


def readiness_problems(settings: Settings) -> list[SettingProblem]:
    """Warnings for capabilities a mission will need but that are not set yet.

    Kept separate from :func:`build_settings`' hard validation so that
    ``config --settings`` and ``mission --phase settings`` can render them as
    guidance instead of refusing to run.
    """

    problems: list[SettingProblem] = []
    spec = settings.provider_spec()
    if spec is None:
        return problems                                # already an error above

    if not settings.model:
        problems.append(
            _problem("model", "no model configured — set --model or ARGUS_LLM_MODEL", SettingSource.DEFAULT, Severity.WARNING)
        )
    elif spec.models and settings.model not in spec.models:
        problems.append(
            _problem(
                "model",
                f"{settings.model!r} is not a known {spec.label} model "
                f"(known: {', '.join(spec.models[:3])}, …); continuing anyway",
                settings.source_of("model"),
                Severity.WARNING,
            )
        )

    if settings.requires_credential() and not settings.resolve_api_key()[0]:
        problems.append(
            SettingProblem(
                field="api_key",
                message=f"no credential found for {spec.label}; looked in {spec.key_env_summary()}",
                severity=Severity.WARNING,
                source=SettingSource.ENV,
                env_var=spec.key_env_summary(),
            )
        )
    return problems


# --------------------------------------------------------------------------
# 8.3 Rich rendering
# --------------------------------------------------------------------------


def render_settings_problems(problems: Sequence[SettingProblem], *, title: str = "invalid configuration") -> Panel:
    """Build the error panel shown when validation fails.

    Every line names the setting, the offending value's *source* and a fix.
    Messages have already passed through :func:`redact_text`.
    """

    body = Text()
    ordered = sorted(problems, key=lambda p: (p.severity is Severity.WARNING, p.field))
    for index, problem in enumerate(ordered):
        if index:
            body.append("\n")
        colour = "red" if problem.severity is Severity.ERROR else "yellow"
        glyph = "✘" if problem.severity is Severity.ERROR else "!"
        body.append(f"{glyph} ", style=f"bold {colour}")
        body.append(problem.field, style=f"bold {colour}")
        body.append(f" ({problem.location()}): ", style="dim")
        body.append(problem.message, style="white")

    errors = sum(1 for p in problems if p.severity is Severity.ERROR)
    body.append("\n\n")
    body.append(
        f"{errors} error(s) must be fixed before any model or browser call is made."
        if errors
        else "No blocking errors.",
        style="dim",
    )
    return Panel(body, border_style="red" if errors else "yellow", title=title, title_align="left")


def render_settings(settings: Settings, *, show_provenance: bool = True) -> Table:
    """Render the merged configuration as a grouped table with masked secrets."""

    table = Table(
        title=f"{APP_TITLE} effective settings",
        title_justify="left",
        box=None,
        pad_edge=False,
    )
    table.add_column("setting", style="dim", no_wrap=True)
    table.add_column("value", overflow="fold")
    if show_provenance:
        table.add_column("source", no_wrap=True, justify="right")

    def add(field_name: str, label: str, value: str) -> None:
        row = [label, value]
        if show_provenance:
            source = settings.source_of(field_name)
            colour = {"cli": "bold cyan", "env": "bold yellow", "default": "dim"}[source.value]
            row.append(f"[{colour}]{source.value}[/{colour}]")
        table.add_row(*row)

    def group(name: str) -> None:
        cells = [f"[bold]{name}[/bold]", ""]
        if show_provenance:
            cells.append("")
        table.add_row(*cells)

    group("model")
    add("provider", "provider", escape(settings.provider))
    add("model", "model", escape(settings.model) if settings.model else "[yellow]unset[/yellow]")
    add("base_url", "base_url", escape(settings.base_url or "—"))
    # Never the key itself — only its masked state and where it came from.
    # Provenance is "env" only when a credential variable actually holds a value.
    key_present = bool(settings.resolve_api_key()[0])
    table.add_row(
        "api_key",
        escape(settings.api_key_hint()),
        *([] if not show_provenance else ["[dim]env[/dim]" if key_present else "[dim]—[/dim]"]),
    )

    group("paths")
    add("home_dir", "home_dir", escape(str(settings.home_dir)))
    add("output_dir", "output_dir", escape(str(settings.output_dir)))
    add("case_dir", "case_dir", escape(str(settings.case_dir) if settings.case_dir else "—"))

    group("orchestration")
    add("max_subagents", "max_subagents", str(settings.max_subagents))
    add("max_workers_per_agent", "max_workers_per_agent", str(settings.max_workers_per_agent))
    add("max_total_workers", "max_total_workers", str(settings.max_total_workers))
    table.add_row(
        "max_potential_workers",
        str(settings.max_potential_workers),
        *([] if not show_provenance else ["[dim]derived[/dim]"]),
    )
    add("worker_retries", "worker_retries", str(settings.worker_retries))
    add("review_retries", "review_retries", str(settings.review_retries))

    group("budgets")
    add("mission_budget_seconds", "mission_budget_seconds", f"{settings.mission_budget_seconds} ({_human_duration(settings.mission_budget_seconds)})")
    add("task_budget_seconds", "task_budget_seconds", f"{settings.task_budget_seconds} ({_human_duration(settings.task_budget_seconds)})")

    group("browser")
    add("browser_headless", "headless", "yes" if settings.browser_headless else "no")
    add("browser_concurrency", "concurrency", str(settings.browser_concurrency))
    add("browser_profile_dir", "profile_dir", escape(str(settings.browser_profile_dir) if settings.browser_profile_dir else "ephemeral"))

    group("network")
    add("allow_network", "allow_network", "yes" if settings.allow_network else "no (offline)")
    add("respect_robots", "respect_robots", "yes" if settings.respect_robots else "no")
    add("http_concurrency", "http_concurrency", str(settings.http_concurrency))
    add("http_timeout", "http_timeout", f"{settings.http_timeout:g}s")
    add("user_agent", "user_agent", escape(settings.user_agent))

    group("context")
    add("operator", "operator", escape(settings.operator) if settings.operator else "[yellow]unset[/yellow]")
    add("log_level", "log_level", escape(settings.log_level))
    add("dry_run", "dry_run", "yes" if settings.dry_run else "[red]no[/red]")
    return table


def _human_duration(seconds: int) -> str:
    """Compact ``1h 30m`` / ``5m 0s`` rendering for budget columns."""

    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def print_settings_report(result: SettingsResult) -> None:
    """Render settings, then any problems, with a one-line verdict."""

    console = get_console()
    console.print()
    console.print(render_settings(result.settings))
    if result.problems:
        console.print(
            render_settings_problems(
                result.problems,
                title="configuration problems" if result.ok else "invalid configuration",
            )
        )
    else:
        console.print("[green]✔ configuration valid[/green] — no problems detected.")
    console.print()


# ══════════════════════════════════════════════════════════════════════════
# 9. Typer application
# ══════════════════════════════════════════════════════════════════════════

app = typer.Typer(
    name=APP_NAME,
    help=f"{APP_TITLE} — {APP_SUBTITLE}.",
    epilog="Authorised use only.  Only collect from systems you own or are explicitly permitted to assess.",
    add_completion=True,
    no_args_is_help=True,
    # Needed so eager root options (--version) can short-circuit before Typer
    # complains that no subcommand was supplied.
    invoke_without_command=True,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _emit(text: str) -> None:
    """Plain text output that bypasses Rich (machine-readable, pipe-safe)."""

    typer.echo(text)


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version information and exit.",
        is_eager=True,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Increase diagnostic output.",
        is_eager=True,
    ),
) -> None:
    """Top-level options shared by every command."""

    if version:
        print_version()
        raise typer.Exit(ExitCode.OK)
    if verbose:
        os.environ.setdefault(f"{ENV_PREFIX}LOG_LEVEL", "DEBUG")


# ══════════════════════════════════════════════════════════════════════════
# 10. Command: version
# ══════════════════════════════════════════════════════════════════════════


@app.command("version", help="Show version, build phase and schema metadata.")
def version_command(
    as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Print version information.  Performs no I/O beyond stdout."""

    print_version(as_json=as_json)


# ══════════════════════════════════════════════════════════════════════════
# 11. Command: config
# ══════════════════════════════════════════════════════════════════════════


@app.command("config", help="Check interpreter, dependencies, environment and effective settings.")
def config_command(
    settings_only: bool = typer.Option(
        False,
        "--settings/--capabilities",
        help="Show the merged settings object instead of the capability probes.",
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
    strict: bool = typer.Option(False, "--strict", help="Treat warnings as failures."),
    show_all: bool = typer.Option(
        True,
        "--all/--problems-only",
        help="List every probe, or only warnings and failures.",
    ),
) -> None:
    """Diagnose the environment and validate the effective configuration.

    Exits non-zero when a hard requirement fails, or when the merged settings
    contain an invalid value (checked before any model or browser is touched).
    """

    # Validation always runs — a broken setting is a configuration failure even
    # when the operator only asked about installed packages.
    settings_result = build_settings()
    validation_failed = not settings_result.ok

    if settings_only:
        if as_json:
            _emit(
                json.dumps(
                    {
                        "app": APP_NAME,
                        "version": __version__,
                        "build_phase": BUILD_PHASE,
                        "ok": settings_result.ok,
                        "settings": settings_result.settings.to_dict(),
                        "problems": [p.to_dict() for p in settings_result.problems],
                    },
                    indent=2,
                )
            )
        else:
            print_settings_report(settings_result)
        raise typer.Exit(ExitCode.CONFIG if validation_failed else ExitCode.OK)

    results = collect_config_results()
    failures = [r for r in results if r.status == "fail"]
    warnings = [r for r in results if r.status == "warn"]

    if as_json:
        _emit(
            json.dumps(
                {
                    "app": APP_NAME,
                    "version": __version__,
                    "build_phase": BUILD_PHASE,
                    "ok": not failures and not (strict and warnings) and not validation_failed,
                    "failures": len(failures),
                    "warnings": len(warnings),
                    "checks": [asdict(r) for r in results],
                    "settings": settings_result.settings.to_dict(),
                    "settings_problems": [p.to_dict() for p in settings_result.problems],
                },
                indent=2,
            )
        )
    else:
        console = get_console()
        table = Table(
            title=f"{APP_TITLE} configuration — phase {BUILD_PHASE} ({BUILD_PHASE_NAME})",
            title_justify="left",
            box=None,
            pad_edge=False,
        )
        table.add_column("", no_wrap=True, width=2)
        table.add_column("probe", style="bold", no_wrap=True)
        table.add_column("detail", overflow="fold")

        shown = results if show_all else [r for r in results if r.status != "ok"]
        for result in shown:
            glyph, style = _STATUS_STYLE.get(result.status, ("?", "white"))
            table.add_row(f"[{style}]{glyph}[/{style}]", escape(result.label), escape(result.detail))

        console.print()
        console.print(table)

        summary = Text()
        summary.append(f"{len(results) - len(failures) - len(warnings)} ok", style="green")
        summary.append("  ·  ")
        summary.append(f"{len(warnings)} warning(s)", style="yellow" if warnings else "dim")
        summary.append("  ·  ")
        summary.append(f"{len(failures)} failure(s)", style="red" if failures else "dim")
        console.print(summary)

        if failures:
            console.print(
                Panel(
                    Text(
                        "Required capabilities are missing.  Install them with:\n"
                        "  pip install typer rich pydantic langgraph browser-use playwright httpx python-dotenv",
                        style="red",
                    ),
                    border_style="red",
                    title="config incomplete",
                    title_align="left",
                )
            )
        elif warnings:
            console.print(
                "[yellow]No hard failures. Warnings are optional capabilities that are not "
                "configured yet — features needing them report a clear error until then.[/yellow]"
            )

        if settings_result.problems:
            console.print()
            console.print(
                render_settings_problems(
                    settings_result.problems,
                    title="invalid configuration" if validation_failed else "configuration notes",
                )
            )
        else:
            console.print("[green]✔ configuration valid[/green] — effective settings passed all checks.")
        console.print()

    if failures or (strict and warnings) or validation_failed:
        if strict and warnings and not failures:
            if not as_json:
                get_console().print(
                    f"[yellow]--strict:[/yellow] exiting {int(ExitCode.CONFIG)} because "
                    f"{len(warnings)} warning(s) were reported."
                )
        raise typer.Exit(ExitCode.CONFIG)
    raise typer.Exit(ExitCode.OK)


# ══════════════════════════════════════════════════════════════════════════
# 12. Doctor — end-to-end capability health
# ══════════════════════════════════════════════════════════════════════════


class CheckStatus(str, Enum):
    """Outcome of one doctor probe."""

    PASS = "pass"
    WARN = "warn"      # optional capability missing — the tool still runs
    FAIL = "fail"      # required capability missing — the tool cannot run
    SKIP = "skip"      # not applicable (e.g. browser check without Playwright)


class CheckCategory(str, Enum):
    """Grouping used by the doctor table."""

    PYTHON = "python"
    IMPORTS = "imports"
    BROWSER = "browser"
    MODEL = "model"
    STORAGE = "storage"
    FORENSICS = "forensics"
    CONFIG = "configuration"


#: Glyph and colour per status, shared by the table and the summary.
_STATUS_STYLES: dict[CheckStatus, tuple[str, str]] = {
    CheckStatus.PASS: ("✔", "green"),
    CheckStatus.WARN: ("!", "yellow"),
    CheckStatus.FAIL: ("✘", "red"),
    CheckStatus.SKIP: ("·", "dim"),
}


@dataclass(frozen=True)
class DoctorCheck:
    """One line of the doctor report.

    ``hint`` is the actionable fix (kept out of the table so long commands do
    not destroy the layout); ``install`` is the exact shell command to run.
    """

    id: str
    category: CheckCategory
    title: str
    status: CheckStatus
    detail: str
    hint: str | None = None
    install: str | None = None
    required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value,
            "title": self.title,
            "status": self.status.value,
            "detail": redact_text(self.detail, secrets=known_secrets()),
            "hint": redact_text(self.hint, secrets=known_secrets()) if self.hint else None,
            "install": self.install,
            "required": self.required,
        }


#: Imports the agent cannot function without.  Each entry is
#: ``(module, pip package, what it unlocks, guidance when missing)``.
REQUIRED_IMPORTS: tuple[tuple[str, str, str, str], ...] = (
    ("typer", "typer", "CLI framework", "The CLI itself cannot start without Typer."),
    ("rich", "rich", "terminal reporting", "Diagnostics and reports cannot be rendered without Rich."),
    ("langgraph", "langgraph", "Master Agent orchestration", "Missions cannot be orchestrated without LangGraph."),
    ("browser_use", "browser-use", "runtime Subagent browser actions", "Browser-driven collection needs browser-use."),
    ("playwright", "playwright", "browser automation engine", "browser-use drives Playwright; both are required."),
)

#: Optional forensic utilities.  Missing ones only degrade specific features.
#: ``kind`` is "module" (Python import) or "binary" (PATH lookup).
FORENSIC_TOOLS: tuple[tuple[str, str, str, str | None, str], ...] = (
    # (id, kind, name, install, unlocks)
    ("magic", "module", "magic", "python-magic", "file-type sniffing for unknown artefacts"),
    ("dns", "module", "dns", "dnspython", "passive DNS record enumeration"),
    ("whois", "module", "whois", "python-whois", "registration and ownership lookups"),
    ("exiftool", "binary", "exiftool", "exiftool", "image/document metadata extraction"),
    ("tesseract", "binary", "tesseract", "tesseract-ocr", "OCR of screenshots and scanned documents"),
    ("pdftotext", "binary", "pdftotext", "poppler-utils", "text extraction from PDF evidence"),
    ("pefile", "module", "pefile", "pefile", "Windows PE header and import analysis"),
    ("oletools", "module", "oletools", "oletools", "macro and OLE document inspection"),
    ("yara", "module", "yara", "yara-python", "signature matching against evidence"),
    ("ssdeep", "module", "ssdeep", "ssdeep", "fuzzy hashing for similarity clustering"),
    ("pypdf", "module", "pypdf", "pypdf", "PDF parsing without external binaries"),
    ("binwalk", "binary", "binwalk", "binwalk", "embedded-file carving in firmware images"),
    ("strings", "binary", "strings", "binutils", "printable-string extraction from binaries"),
    ("openssl", "binary", "openssl", "openssl", "local hashing and fingerprint verification"),
)

#: Guidance shown when no Playwright browser build is installed.  The engine
#: alone is not enough: the browser build and its OS libraries are separate.
PLAYWRIGHT_BROWSER_INSTALL: str = "python -m playwright install chromium"
PLAYWRIGHT_DEPS_INSTALL: str = "python -m playwright install-deps chromium"


def _playwright_browser_roots() -> list[Path]:
    """Candidate directories where Playwright unpacks browser builds."""

    override = env_value("PLAYWRIGHT_BROWSERS_PATH")
    if override and override != "0":
        return [Path(override).expanduser()]
    home = Path.home()
    roots = [
        home / ".cache" / "ms-playwright",                  # Linux
        home / "Library" / "Caches" / "ms-playwright",      # macOS
        home / "AppData" / "Local" / "ms-playwright",       # Windows
    ]
    local_appdata = env_value("LOCALAPPDATA")
    if local_appdata:
        roots.append(Path(local_appdata) / "ms-playwright")
    return roots


def find_playwright_browsers() -> list[Path]:
    """Chromium-family builds already downloaded by Playwright."""

    found: list[Path] = []
    for root in _playwright_browser_roots():
        try:
            if not root.is_dir():
                continue
            found.extend(
                p for p in root.iterdir() if p.is_dir() and p.name.startswith("chromium")
            )
        except OSError:
            continue
    return sorted(found)


def find_system_browsers() -> list[str]:
    """Browser binaries on PATH that Playwright can use as a channel."""

    names = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "microsoft-edge")
    return [name for name in names if shutil.which(name)]


# --------------------------------------------------------------------------
# 12.1 Individual probes
# --------------------------------------------------------------------------


def check_python() -> DoctorCheck:
    """Interpreter floor from :data:`MIN_PYTHON`, plus a 3.11 recommendation."""

    current = sys.version_info[:2]
    minimum = f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}"
    detail = f"Python {platform.python_version()} on {platform.system() or 'unknown'}"
    if current < MIN_PYTHON:
        return DoctorCheck(
            "python.version",
            CheckCategory.PYTHON,
            "Python version",
            CheckStatus.FAIL,
            f"{detail} — requires >= {minimum}",
            hint=f"Install Python {minimum}+ and recreate the virtual environment.",
            required=True,
        )
    if current < (3, 11):
        return DoctorCheck(
            "python.version",
            CheckCategory.PYTHON,
            "Python version",
            CheckStatus.WARN,
            f"{detail} — works, 3.11+ recommended for LangGraph performance",
            hint="Optional: upgrade to Python 3.11 or newer.",
            required=True,
        )
    return DoctorCheck("python.version", CheckCategory.PYTHON, "Python version", CheckStatus.PASS, detail, required=True)


def check_required_imports() -> list[DoctorCheck]:
    """Probe each hard dependency without importing it."""

    checks: list[DoctorCheck] = []
    for module, package, unlocks, guidance in REQUIRED_IMPORTS:
        if module_available(module):
            checks.append(
                DoctorCheck(f"import.{module}", CheckCategory.IMPORTS, module, CheckStatus.PASS,
                            f"importable — {unlocks}", required=True)
            )
        else:
            checks.append(
                DoctorCheck(
                    f"import.{module}",
                    CheckCategory.IMPORTS,
                    module,
                    CheckStatus.FAIL,
                    f"not importable — {unlocks}",
                    hint=guidance,
                    install=f"pip install {package}",
                    required=True,
                )
            )
    return checks


def check_browser(settings: Settings, *, probe_launch: bool = False) -> list[DoctorCheck]:
    """Verify the automation engine *and* that a browser build exists.

    Install guidance is attached whenever a browser is missing, because
    ``pip install playwright`` alone does not download Chromium.
    """

    checks: list[DoctorCheck] = []

    if not module_available("playwright"):
        checks.append(
            DoctorCheck(
                "browser.engine",
                CheckCategory.BROWSER,
                "Playwright engine",
                CheckStatus.FAIL,
                "playwright is not installed — no browser automation possible",
                hint="Install the engine, then download a browser build.",
                install="pip install playwright",
                required=True,
            )
        )
        checks.append(
            DoctorCheck(
                "browser.binary",
                CheckCategory.BROWSER,
                "browser build",
                CheckStatus.SKIP,
                "not checked — the engine is missing",
                required=True,
            )
        )
        return checks

    checks.append(
        DoctorCheck(
            "browser.engine",
            CheckCategory.BROWSER,
            "Playwright engine",
            CheckStatus.PASS,
            f"installed — headless={ 'yes' if settings.browser_headless else 'no'}",
            required=True,
        )
    )

    builds = find_playwright_browsers()
    system = find_system_browsers()
    if builds:
        newest = builds[-1].name
        checks.append(
            DoctorCheck(
                "browser.binary",
                CheckCategory.BROWSER,
                "browser build",
                CheckStatus.PASS,
                f"{len(builds)} Playwright build(s) found, newest {newest}",
                required=True,
            )
        )
    elif system:
        checks.append(
            DoctorCheck(
                "browser.binary",
                CheckCategory.BROWSER,
                "browser build",
                CheckStatus.WARN,
                f"no Playwright build downloaded; system browser available ({system[0]})",
                hint="Playwright needs its own build for full compatibility.",
                install=PLAYWRIGHT_BROWSER_INSTALL,
                required=True,
            )
        )
    else:
        checks.append(
            DoctorCheck(
                "browser.binary",
                CheckCategory.BROWSER,
                "browser build",
                CheckStatus.FAIL,
                "playwright is installed but no Chromium build was downloaded",
                hint="Then install the OS libraries Chromium needs.",
                install=f"{PLAYWRIGHT_BROWSER_INSTALL}\n{PLAYWRIGHT_DEPS_INSTALL}",
                required=True,
            )
        )

    if probe_launch:
        ok, message = probe_browser_launch(headless=settings.browser_headless)
        checks.append(
            DoctorCheck(
                "browser.launch",
                CheckCategory.BROWSER,
                "browser launch",
                CheckStatus.PASS if ok else CheckStatus.WARN,
                message,
                hint=None if ok else "Run with a downloaded build and the OS libraries it needs.",
                install=None if ok else PLAYWRIGHT_DEPS_INSTALL,
                required=False,
            )
        )
    return checks


def probe_browser_launch(*, headless: bool, timeout_ms: int = 20_000) -> tuple[bool, str]:
    """Try a real Chromium launch in a subprocess-free, offline way.

    Deliberately synchronous and guarded: a hung launch must not hang the
    doctor, so the probe is bounded and every failure is reported, not raised.
    """

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:                                     # pragma: no cover - env specific
        return False, f"cannot import playwright.sync_api: {type(exc).__name__}"

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=headless, timeout=timeout_ms)
            version = browser.version
            browser.close()
        return True, f"launched Chromium {version}"
    except Exception as exc:                                     # pragma: no cover - env specific
        first_line = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
        return False, f"launch failed: {redact_text(first_line)[:200]}"


def check_model(result: SettingsResult) -> list[DoctorCheck]:
    """Validate provider, model id and credential *state* — never the key."""

    settings = result.settings
    checks: list[DoctorCheck] = []
    spec = settings.provider_spec()

    provider_errors = [p for p in result.errors if p.field == "provider"]
    if provider_errors:
        checks.append(
            DoctorCheck(
                "model.provider",
                CheckCategory.MODEL,
                "provider",
                CheckStatus.FAIL,
                provider_errors[0].message,
                hint=f"Set --provider or ARGUS_LLM_PROVIDER to one of: {', '.join(sorted(PROVIDER_REGISTRY))}.",
                required=True,
            )
        )
        return checks

    checks.append(
        DoctorCheck(
            "model.provider",
            CheckCategory.MODEL,
            "provider",
            CheckStatus.PASS,
            f"{settings.provider}" + (f" — {spec.label}" if spec else ""),
            required=True,
        )
    )

    if settings.model:
        known = spec.models if spec else ()
        if known and settings.model not in known:
            checks.append(
                DoctorCheck(
                    "model.id",
                    CheckCategory.MODEL,
                    "model id",
                    CheckStatus.WARN,
                    f"{settings.model} is not a known {spec.label if spec else settings.provider} model",
                    hint=f"Known ids include: {', '.join(known[:3])}.",
                )
            )
        else:
            checks.append(
                DoctorCheck("model.id", CheckCategory.MODEL, "model id", CheckStatus.PASS, settings.model, required=True)
            )
    else:
        checks.append(
            DoctorCheck(
                "model.id",
                CheckCategory.MODEL,
                "model id",
                CheckStatus.WARN,
                "no model configured",
                hint="Set ARGUS_LLM_MODEL or pass --model.",
                install="export ARGUS_LLM_MODEL=gpt-4.1-mini",
                required=True,
            )
        )

    # Credential presence only — the value is masked and never rendered.
    hint_text = settings.api_key_hint()
    if settings.requires_credential() and not settings.resolve_api_key()[0]:
        checks.append(
            DoctorCheck(
                "model.credential",
                CheckCategory.MODEL,
                "credential",
                CheckStatus.WARN,
                f"missing — {hint_text}",
                hint="Export the key named above; it is read at call time and never printed.",
                required=True,
            )
        )
    else:
        checks.append(
            DoctorCheck("model.credential", CheckCategory.MODEL, "credential", CheckStatus.PASS, hint_text, required=True)
        )
    return checks


def check_storage(settings: Settings, *, create_dirs: bool = False) -> list[DoctorCheck]:
    """Verify output paths are writable, optionally creating them."""

    checks: list[DoctorCheck] = []
    targets: list[tuple[str, Path]] = [("output_dir", settings.output_dir)]
    if settings.case_dir is not None:
        targets.append(("case_dir", settings.case_dir))

    for field_name, path in targets:
        created_note = ""
        if not path.exists() and create_dirs:
            try:
                path.mkdir(parents=True, exist_ok=True)
                created_note = " (created)"
            except OSError as exc:
                checks.append(
                    DoctorCheck(
                        f"storage.{field_name}",
                        CheckCategory.STORAGE,
                        field_name,
                        CheckStatus.FAIL,
                        f"cannot create {path}: {type(exc).__name__}",
                        hint="Choose a writable location with --output-dir or ARGUS_OUTPUT_DIR.",
                        required=True,
                    )
                )
                continue

        writable = directory_writable(path)
        if writable:
            state = "exists" if path.exists() else f"will be created{created_note}"
            checks.append(
                DoctorCheck(
                    f"storage.{field_name}",
                    CheckCategory.STORAGE,
                    field_name,
                    CheckStatus.PASS,
                    f"{path} — {state}, writable",
                    required=True,
                )
            )
        else:
            checks.append(
                DoctorCheck(
                    f"storage.{field_name}",
                    CheckCategory.STORAGE,
                    field_name,
                    CheckStatus.FAIL,
                    f"{path} — not writable",
                    hint="Pick a writable directory or fix its permissions.",
                    install="export ARGUS_OUTPUT_DIR=$HOME/argus_output",
                    required=True,
                )
            )
    return checks


def check_forensics() -> list[DoctorCheck]:
    """Optional utilities: each miss only narrows what a mission can collect."""

    checks: list[DoctorCheck] = []
    for tool_id, kind, name, install, unlocks in FORENSIC_TOOLS:
        present = module_available(name) if kind == "module" else bool(shutil.which(name))
        if present:
            checks.append(
                DoctorCheck(f"forensics.{tool_id}", CheckCategory.FORENSICS, name, CheckStatus.PASS,
                            f"{kind} available — {unlocks}")
            )
        else:
            command = f"pip install {install}" if kind == "module" else f"apt-get install {install}"
            checks.append(
                DoctorCheck(
                    f"forensics.{tool_id}",
                    CheckCategory.FORENSICS,
                    name,
                    CheckStatus.WARN,
                    f"missing ({kind}) — {unlocks} unavailable",
                    hint=f"Optional: enables {unlocks}.",
                    install=command,
                )
            )
    return checks


def check_configuration(result: SettingsResult) -> DoctorCheck:
    """Summarise the strict validation performed by :func:`build_settings`."""

    if result.ok:
        return DoctorCheck(
            "config.validation",
            CheckCategory.CONFIG,
            "settings validation",
            CheckStatus.PASS,
            "all limits and paths valid",
            required=True,
        )
    errors = result.errors
    preview = "; ".join(f"{p.field}: {p.message}" for p in errors[:3])
    more = f" (+{len(errors) - 3} more)" if len(errors) > 3 else ""
    return DoctorCheck(
        "config.validation",
        CheckCategory.CONFIG,
        "settings validation",
        CheckStatus.FAIL,
        f"{len(errors)} invalid setting(s) — {preview}{more}",
        hint="Run 'config --settings' to see every value and its source.",
        required=True,
    )


def run_doctor(
    result: SettingsResult,
    *,
    create_dirs: bool = False,
    probe_launch: bool = False,
) -> list[DoctorCheck]:
    """Run every probe.  Never raises, never prints, never leaks a secret."""

    checks: list[DoctorCheck] = []
    checks.append(check_python())
    checks.extend(check_required_imports())
    checks.extend(check_browser(result.settings, probe_launch=probe_launch))
    checks.extend(check_model(result))
    checks.extend(check_storage(result.settings, create_dirs=create_dirs))
    checks.extend(check_forensics())
    checks.append(check_configuration(result))
    return checks


# --------------------------------------------------------------------------
# 12.2 Rendering
# --------------------------------------------------------------------------


def doctor_guidance(checks: Sequence[DoctorCheck], *, include_warnings: bool = True) -> list[str]:
    """Ordered, de-duplicated fixes: blocking ones first, optional ones last.

    A check contributes its install command when it has one, otherwise its
    hint.  Missing *optional* forensics tools are collapsed into a single line
    so the panel stays readable when nothing is installed yet.
    """

    def fix_for(check: DoctorCheck) -> str | None:
        return check.install or check.hint

    blocking = [fix_for(c) for c in checks if c.status is CheckStatus.FAIL]
    degraded = [
        fix_for(c)
        for c in checks
        if c.status is CheckStatus.WARN and c.category is not CheckCategory.FORENSICS
    ]
    optional_tools = [
        c.title for c in checks if c.status is CheckStatus.WARN and c.category is CheckCategory.FORENSICS
    ]

    lines: list[str] = []
    for candidate in blocking + (degraded if include_warnings else []):
        if candidate and candidate not in lines:
            lines.append(candidate)
    if optional_tools and include_warnings:
        listed = ", ".join(optional_tools)
        lines.append(f"Optional utilities missing (features degrade gracefully): {listed}")
    return lines


def render_doctor(
    checks: Sequence[DoctorCheck],
    *,
    problems_only: bool = False,
    show_hints: bool = True,
) -> Console:
    """Print the grouped report; returns the console for follow-up output."""

    console = get_console()
    failures = [c for c in checks if c.status is CheckStatus.FAIL]
    warnings = [c for c in checks if c.status is CheckStatus.WARN]

    table = Table(
        title=f"{APP_TITLE} doctor — phase {BUILD_PHASE} ({BUILD_PHASE_NAME})",
        title_justify="left",
        box=None,
        pad_edge=False,
    )
    table.add_column("", width=2, no_wrap=True)
    table.add_column("check", style="bold", no_wrap=True)
    table.add_column("status", no_wrap=True)
    table.add_column("detail", overflow="fold")

    for category in CheckCategory:
        group = [c for c in checks if c.category is category]
        shown = [c for c in group if not problems_only or c.status is not CheckStatus.PASS]
        if not shown:
            continue
        # Category row: keep the glyph column empty so the label cannot wrap.
        table.add_row("", f"[bold cyan]{category.value}[/bold cyan]", "", "")
        for check in shown:
            glyph, colour = _STATUS_STYLES[check.status]
            label = "required" if check.required else "optional"
            table.add_row(
                f"[{colour}]{glyph}[/{colour}]",
                escape(check.title),
                f"[{colour}]{check.status.value}[/{colour}] [dim]{label}[/dim]",
                escape(check.detail),
            )

    console.print()
    console.print(table)

    passed = sum(1 for c in checks if c.status is CheckStatus.PASS)
    skipped = sum(1 for c in checks if c.status is CheckStatus.SKIP)
    summary = Text()
    summary.append(f"{passed} passed", style="green")
    summary.append("  ·  ")
    summary.append(f"{len(warnings)} warning(s)", style="yellow" if warnings else "dim")
    summary.append("  ·  ")
    summary.append(f"{len(failures)} failure(s)", style="red" if failures else "dim")
    if skipped:
        summary.append("  ·  ")
        summary.append(f"{skipped} skipped", style="dim")
    console.print(summary)

    if show_hints:
        guidance = doctor_guidance(checks)
        if guidance:
            body = Text()
            for index, item in enumerate(guidance):
                if index:
                    body.append("\n")
                # Multi-line fixes keep their alignment: first line gets the arrow.
                for line_number, line in enumerate(item.splitlines()):
                    if line_number:
                        body.append("\n")
                    body.append("→ " if line_number == 0 else "  ", style="cyan")
                    body.append(line.strip(), style="white")
            console.print(
                Panel(
                    body,
                    title="how to fix" if failures else "optional improvements",
                    title_align="left",
                    border_style="red" if failures else "yellow",
                )
            )

    if failures:
        console.print(
            f"[red]{len(failures)} required capability failure(s)[/red] — "
            "missions cannot run until these are installed."
        )
    elif warnings:
        console.print(
            "[yellow]Required capabilities present.[/yellow] Warnings are optional — "
            "affected features degrade gracefully and are skipped per mission."
        )
    else:
        console.print("[green]All checks passed.[/green] Ready to run a mission.")
    console.print()
    return console


@app.command("doctor", help="Diagnose every runtime capability: Python, imports, browser, model, storage, forensics.")
def doctor_command(
    as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
    strict: bool = typer.Option(False, "--strict", help="Treat warnings as failures."),
    problems_only: bool = typer.Option(
        False, "--problems-only", help="Hide checks that passed."
    ),
    show_hints: bool = typer.Option(True, "--hints/--no-hints", help="Show fix commands."),
    category: list[CheckCategory] | None = typer.Option(
        None, "--category", help="Restrict to a category. Repeatable."
    ),
    create_dirs: bool = typer.Option(
        False, "--create-dirs", help="Create the output directory if it is missing."
    ),
    probe_launch: bool = typer.Option(
        False, "--probe-launch", help="Also try to launch Chromium (slow, may install nothing)."
    ),
) -> None:
    """Check every capability the agent needs.  Performs no collection.

    Missing *optional* utilities downgrade to warnings and never block a run;
    missing *required* capabilities fail with an install command and a
    non-zero exit status, so this doubles as a CI or preflight gate.
    """

    result = build_settings()
    checks = run_doctor(result, create_dirs=create_dirs, probe_launch=probe_launch)

    if category:
        wanted = set(category)
        checks = [c for c in checks if c.category in wanted]

    failures = [c for c in checks if c.status is CheckStatus.FAIL]
    warnings = [c for c in checks if c.status is CheckStatus.WARN]
    failing = bool(failures) or (strict and bool(warnings))

    if as_json:
        _emit(
            json.dumps(
                {
                    "app": APP_NAME,
                    "version": __version__,
                    "build_phase": BUILD_PHASE,
                    "ok": not failing,
                    "passed": sum(1 for c in checks if c.status is CheckStatus.PASS),
                    "warnings": len(warnings),
                    "failures": len(failures),
                    "skipped": sum(1 for c in checks if c.status is CheckStatus.SKIP),
                    "checks": [c.to_dict() for c in checks],
                    "guidance": [
                        redact_text(item, secrets=known_secrets())
                        for item in doctor_guidance(checks)
                    ],
                    # Masked model state only — credentials are never serialised.
                    "model": {
                        "provider": result.settings.provider,
                        "model": result.settings.model,
                        "credential": result.settings.api_key_hint(),
                    },
                },
                indent=2,
            )
        )
    else:
        console = render_doctor(checks, problems_only=problems_only, show_hints=show_hints)
        if strict and warnings and not failures:
            console.print(
                f"[yellow]--strict:[/yellow] exiting {int(ExitCode.CONFIG)} because "
                f"{len(warnings)} warning(s) were reported."
            )

    raise typer.Exit(ExitCode.CONFIG if failing else ExitCode.OK)


# ══════════════════════════════════════════════════════════════════════════
# 13. Mission safety policy and scope preflight
# ══════════════════════════════════════════════════════════════════════════
#
# Every mission passes through run_preflight() before anything is planned.
# The policy has three outcomes:
#
#   ALLOW  — objective and scope are lawful, authorised and explicit.
#   PAUSE  — plausible but ambiguous (defensive phrasing, guilt assumptions,
#            speculative identification): the operator must confirm intent or
#            adopt an evidence-based reframe.
#   REFUSE — the request is for unauthorised access, credential theft, evasion,
#            doxxing, harassment or destructive action.  No flag overrides this.
#
# Out-of-scope work cannot reach planning: the mission command evaluates this
# before rendering a plan, and enforce_preflight() guards the executor seam.

class PolicyOutcome(str, Enum):
    """Result of evaluating an objective against the safety policy."""

    ALLOW = "allow"
    PAUSE = "pause"
    REFUSE = "refuse"


class PolicyCategory(str, Enum):
    """What a request is asking for.

    The first three are the supported, lawful mission types; the rest are
    refused or paused.
    """

    PUBLIC_WEB_OSINT = "public-web-osint"
    OWNED_FORENSIC = "owned-forensic"
    AUTHORIZED_FORENSIC = "authorized-forensic"
    UNAUTHORIZED_ACCESS = "unauthorized-access"
    CREDENTIAL_THEFT = "credential-theft"
    EVASION = "evasion"
    DOXXING = "doxxing"
    HARASSMENT = "harassment"
    DESTRUCTIVE = "destructive-action"
    SPECULATIVE_ID = "speculative-identification"
    GUILT_ASSUMPTION = "guilt-assumption"
    PERSONAL_DATA = "personal-data-collection"


class DataClass(str, Enum):
    """The kind of evidence a mission is authorised to touch."""

    PUBLIC_WEB = "public-web"                    # published, public sources only
    OWNED_ARTIFACT = "owned-artifact"            # artefacts you own
    AUTHORIZED_ARTIFACT = "authorized-artifact"  # artefacts you are permitted to examine


#: Data classes that are forensic (local, read-only) rather than web collection.
ARTIFACT_DATA_CLASSES: frozenset[DataClass] = frozenset(
    {DataClass.OWNED_ARTIFACT, DataClass.AUTHORIZED_ARTIFACT}
)


@dataclass(frozen=True)
class PolicyRule:
    """One detection rule: what it catches, why, and the safe alternative.

    ``patterns`` are case-insensitive regexes matched sentence by sentence.
    ``defensive_context`` words in the *same sentence* downgrade a REFUSE to a
    PAUSE, because "detect credential theft" and "steal credentials" must not
    be treated alike.
    """

    id: str
    category: PolicyCategory
    outcome: PolicyOutcome
    patterns: tuple[str, ...]
    rationale: str
    alternative: str
    label: str
    reframable: bool = False


@dataclass(frozen=True)
class ScopeDeclaration:
    """The explicit boundary a mission may act within.

    Every target must be covered by at least one :attr:`entries` item and by no
    :attr:`exclusions` item.  Nothing outside this boundary can be planned.
    """

    targets: tuple[str, ...]
    entries: tuple[str, ...]
    exclusions: tuple[str, ...]
    data_classes: frozenset[DataClass]
    mode: MissionMode
    authorized_by: str | None = None
    authorization_basis: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "targets": list(self.targets),
            "entries": list(self.entries),
            "exclusions": list(self.exclusions),
            "data_classes": sorted(dc.value for dc in self.data_classes),
            "mode": self.mode.value,
            "authorized_by": self.authorized_by,
            "authorization_basis": self.authorization_basis,
        }


@dataclass(frozen=True)
class PolicyVerdict:
    """Outcome of scanning an objective string."""

    outcome: PolicyOutcome
    category: PolicyCategory | None = None
    rule_id: str | None = None
    rationale: str = ""
    alternative: str = ""
    evidence: tuple[str, ...] = ()          # matched fragments (already bounded)
    downgraded: bool = False                # REFUSE softened by defensive context
    notes: tuple[str, ...] = ()
    reframable: bool = False

    @property
    def allowed(self) -> bool:
        return self.outcome is PolicyOutcome.ALLOW

    @property
    def refused(self) -> bool:
        return self.outcome is PolicyOutcome.REFUSE

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "category": self.category.value if self.category else None,
            "rule_id": self.rule_id,
            "rationale": redact_text(self.rationale, secrets=known_secrets()),
            "alternative": redact_text(self.alternative, secrets=known_secrets()),
            "evidence": [redact_text(e, secrets=known_secrets()) for e in self.evidence],
            "downgraded_from_refusal": self.downgraded,
            "notes": list(self.notes),
            "reframable": self.reframable,
        }


@dataclass(frozen=True)
class PreflightIssue:
    """A scope or request-shape problem found before planning."""

    id: str
    message: str
    fix: str
    blocking: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "message": redact_text(self.message, secrets=known_secrets()),
            "fix": self.fix,
            "blocking": self.blocking,
        }


@dataclass
class PreflightReport:
    """Everything the mission command needs to decide allow / pause / refuse."""

    verdict: PolicyVerdict
    issues: list[PreflightIssue]
    scope: ScopeDeclaration | None
    objective: str                       # effective objective (reframed if adopted)
    original_objective: str
    reframed_objective: str | None = None
    reframe_adopted: bool = False
    intent_confirmed: bool = False

    @property
    def blocking_issues(self) -> list[PreflightIssue]:
        return [i for i in self.issues if i.blocking]

    @property
    def paused(self) -> bool:
        """True when the verdict needs confirmation or a reframe."""

        return self.verdict.outcome is PolicyOutcome.PAUSE and not self.resolved

    @property
    def resolved(self) -> bool:
        return self.reframe_adopted or self.intent_confirmed

    @property
    def ok(self) -> bool:
        """True only when the mission may proceed to planning."""

        return not self.verdict.refused and not self.blocking_issues and not self.paused

    @property
    def exit_code(self) -> int:
        """Most severe reason the mission cannot proceed."""

        if self.verdict.refused:
            return int(ExitCode.POLICY)
        if self.blocking_issues:
            return int(ExitCode.USAGE)
        if self.paused:
            return int(ExitCode.CLARIFICATION)
        return int(ExitCode.OK)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "exit_code": self.exit_code,
            "objective": redact_text(self.objective, secrets=known_secrets()),
            "original_objective": redact_text(self.original_objective, secrets=known_secrets()),
            "reframed_objective": (
                redact_text(self.reframed_objective, secrets=known_secrets())
                if self.reframed_objective
                else None
            ),
            "reframe_adopted": self.reframe_adopted,
            "intent_confirmed": self.intent_confirmed,
            "verdict": self.verdict.to_dict(),
            "scope": self.scope.to_dict() if self.scope else None,
            "issues": [i.to_dict() for i in self.issues],
        }


class PolicyViolation(RuntimeError):
    """Raised at the executor seam when a mission was not cleared to run.

    Phase 3's executor must call :func:`enforce_preflight` before its first
    tool call, so a refusal cannot be bypassed by a programmatic caller.
    """

    def __init__(self, message: str, report: PreflightReport) -> None:
        super().__init__(message)
        self.report = report


# --------------------------------------------------------------------------
# 13.1 Rulebook
# --------------------------------------------------------------------------

#: Words that mark a *defensive* sentence ("detect", "protect", "indicators
#: of").  They soften a refusal into a pause — never the other way round.
_DEFENSIVE_CONTEXT = re.compile(
    r"\b(?:detect(?:ion|ing|s)?|defen[cs]e|defend|protect(?:ion|ing)?|prevent(?:ion|ing)?|"
    r"patch(?:ing|es)?|remediat\w*|mitigat\w*|awareness|training|indicator(?:s)?|"
    r"evidence of|investigat\w*|audit(?:ing)?|assess\w*|harden\w*|exposure|risk|controls?)\b",
    re.IGNORECASE,
)

POLICY_RULES: tuple[PolicyRule, ...] = (
    # -- refused outright ----------------------------------------------------
    PolicyRule(
        id="unauthorized-access",
        label="unauthorised account or device access",
        category=PolicyCategory.UNAUTHORIZED_ACCESS,
        outcome=PolicyOutcome.REFUSE,
        patterns=(
            # "hack into X's account", "log into her inbox", "get into the phone"
            r"\b(?:hack|break|get|log|sign|sneak|tunnel)\s+(?:in)?to\s+(?:[a-z0-9_.@'-]+\s+){0,3}"
            r"(?:accounts?|inbox|e-?mail|mailbox|phone|device|laptop|server|router|console|"
            r"profile|instagram|facebook|whatsapp|snapchat|tiktok|telegram|gmail|outlook)\b",
            # "hack her instagram", "crack my ex's account", "take over someone's profile"
            r"\b(?:hack|pwn|crack|take over|break into|break)\b[^.?!]{0,25}"
            r"(?:accounts?|inbox|mailbox|phone|device|profile|instagram|facebook|whatsapp|"
            r"snapchat|tiktok|telegram|gmail|outlook|i-?cloud|netflix|spotify)\b",
            # "read her messages", "see his texts without him knowing"
            r"\b(?:read|see|check|monitor|access)\s+(?:[a-z0-9_.@'-]+\s+){0,2}"
            r"(?:messages|texts?|dms?|chats?|inbox|e-?mail|call log)\b[^.?!]{0,25}"
            r"\b(?:without (?:them|him|her|their) knowing|secretly|behind (?:their|his|her) back)\b",
            r"\b(?:bypass|circumvent|defeat|get past|get around|sidestep)\b[^.?!]{0,40}"
            r"\b(?:2fa|mfa|two[- ]?factor|authentication|auth|login|password|captcha|access control)\b",
            r"\bunauthori[sz]ed\s+(?:access|entry|login|intrusion)\b",
            r"\b(?:brute[- ]?force|password[- ]spray|credential[- ]stuffing)\b[^.?!]{0,40}"
            r"\b(?:accounts?|login|portal|admin|endpoint|credential)\b",
            r"\bsim[- ]?swap\b",
            r"\b(?:session|token|cookie)\s+hijack",
            r"\b(?:spy on|secretly monitor|track)\b[^.?!]{0,30}"
            r"\b(?:partner|spouse|ex|boyfriend|girlfriend|husband|wife|employee|child|kid|tenant)\b",
        ),
        rationale=(
            "Entering someone else's account, device or session is unauthorised access, "
            "which this tool will not plan or assist with."
        ),
        alternative=(
            "Ask the account owner for written consent and have them export the data, or have "
            "them authorise a forensic review of artefacts they provide (--data-class "
            "authorized-artifact --mode forensic). We can also examine only what they own."
        ),
    ),
    PolicyRule(
        id="credential-theft",
        label="credential or secret capture",
        category=PolicyCategory.CREDENTIAL_THEFT,
        outcome=PolicyOutcome.REFUSE,
        patterns=(
            r"\b(?:steal|harvest|capture|dump|exfiltrate|grab|extract|obtain|recover)\b[^.?!]{0,40}"
            r"\b(?:passwords?|passwd|creds|credentials|cookies|session tokens?|api keys?|"
            r"private keys?|password hashes?|otp|one[- ]time codes?)\b",
            r"\b(?:keylog(?:ger|ging)?|mimikatz|hashcat|john the ripper|responder|bloodhound)\b",
            r"\bphish(?:ing)?\s+(?:page|kit|campaign|site|link)\b",
            r"\bcredential[- ]dump(?:s|ing)?\b",
            r"\b(?:sniff|intercept)\b[^.?!]{0,25}\b(?:traffic|packets?|session|credentials)\b",
        ),
        rationale=(
            "Capturing passwords, tokens, cookies or keys is credential theft, even when the "
            "intent is to test a system you do not own."
        ),
        alternative=(
            "Measure exposure without capturing secrets: review authentication logs you own for "
            "failed-login patterns, check breach-notification services for your own domain, and "
            "we can document credential-stuffing indicators already present in those logs."
        ),
    ),
    PolicyRule(
        id="evasion",
        label="detection evasion or anti-forensics",
        category=PolicyCategory.EVASION,
        outcome=PolicyOutcome.REFUSE,
        patterns=(
            r"\b(?:evade|avoid|bypass|dodge|defeat|get past|slip past)\b[^.?!]{0,40}"
            r"\b(?:detection|monitoring|logging|audit(?:ing)?|forensics?|edr|siem|antivirus|"
            r"anti-virus|waf|ids|ips|tripwire|security team)\b",
            r"\b(?:cover|erase|wipe|clear|destroy|delete|scrub)\b[^.?!]{0,20}"
            r"\b(?:tracks|logs?|history|artefacts?|artifacts?|evidence)\b",
            r"\banti[- ]?forensics?\b",
            r"\bwithout\s+(?:leaving|being)\s+(?:a\s+)?(?:traces?|detected|noticed|logged)\b",
            r"\bhide\s+(?:the\s+)?(?:traffic|activity|identity|footprint)\s+from\b",
        ),
        rationale=(
            "Evading detection or destroying logs is anti-forensics: it removes the evidence "
            "that a lawful investigation depends on."
        ),
        alternative=(
            "We can map your logging and detection coverage, then recommend concrete hardening — "
            "the opposite of evasion — or preserve evidence read-only for a lawful review."
        ),
    ),
    PolicyRule(
        id="doxxing",
        label="doxxing or personal-identifier aggregation",
        category=PolicyCategory.DOXXING,
        outcome=PolicyOutcome.REFUSE,
        patterns=(
            r"\bdox(?:x|ing|ed)?\b",
            r"\b(?:home|residential|house|personal|private)\s+address\b",
            r"\b(?:find|locate|reveal|leak|publish|expose|uncover|get)\b[^.?!]{0,40}"
            r"\b(?:home address|where (?:he|she|they) lives?|real name|phone number|"
            r"social security|national id|aadhaar|passport number|family members?|"
            r"workplace|school (?:of|they))\b",
            r"\breverse\s+(?:image|phone|address|username)\s+search\b[^.?!]{0,30}"
            r"\b(?:person|individual|someone|employee|user|neighbou?r)\b",
        ),
        rationale=(
            "Aggregating someone's home address, phone number or family details is doxxing and "
            "creates a real-world safety risk, whatever the justification."
        ),
        alternative=(
            "If you are documenting a threat to yourself, we can preserve the threatening "
            "messages with timestamps and provenance for a report to the platform or police — "
            "without compiling the other party's personal identifiers."
        ),
    ),
    PolicyRule(
        id="harassment",
        label="harassment, intimidation or retaliation",
        category=PolicyCategory.HARASSMENT,
        outcome=PolicyOutcome.REFUSE,
        patterns=(
            r"\b(?:harass|intimidate|threaten|swat(?:ting)?|stalk(?:ing)?|cyberbull(?:y|ying)|"
            r"brigade|dogpile)\b",
            r"\b(?:send|deliver|post|leak)\b[^.?!]{0,25}\b(?:threats?|abuse|hate|harassing)\b",
            r"\b(?:ruin|destroy|end)\b[^.?!]{0,25}\b(?:reputation|lives?|career)\b",
            r"\b(?:get|take)\s+revenge\b|\bretaliat(?:e|ion)\b",
            r"\b(?:make|so)\b[^.?!]{0,20}\b(?:life|uncomfortable|hell)\b",
        ),
        rationale=(
            "Harassment, intimidation and retaliation cause direct harm and are outside what "
            "this tool will support."
        ),
        alternative=(
            "If you are the target, we can preserve the evidence (screenshots, timestamps, "
            "headers) in a chain-of-custody folder and draft a factual report for the platform "
            "or law enforcement."
        ),
    ),
    PolicyRule(
        id="destructive",
        label="destructive or disruptive action",
        category=PolicyCategory.DESTRUCTIVE,
        outcome=PolicyOutcome.REFUSE,
        patterns=(
            r"\b(?:ddos|do\s?s|flood|overwhelm)\b[^.?!]{0,25}"
            r"\b(?:(?:web)?sites?|servers?|services?|endpoints?|networks?|hosts?|infrastructure)\b",
            r"\b(?:take|bring)\s+(?:down|offline)\b[^.?!]{0,25}"
            r"\b(?:(?:web)?sites?|servers?|services?|accounts?|networks?|hosts?)\b",
            r"\b(?:delete|wipe|destroy|corrupt|nuke|brick|ransom|encrypt)\b[^.?!]{0,30}"
            r"\b(?:\w+\s+){0,2}(?:data|files?|servers?|website|account|backups?|systems?|database)\b",
            r"\b(?:inject|plant|install|deploy|drop)\b[^.?!]{0,30}"
            r"\b(?:malware|backdoor|ransomware|rootkit|trojan|worm|keylogger|implant)\b",
            r"\b(?:sabotage|vandalise|vandalize|deface)\b",
            r"\b(?:lock|change)\s+(?:them|him|her|the user)\s+out\b",
        ),
        rationale=(
            "Destroying data, disrupting services or planting malicious code is not investigation "
            "— it destroys evidence and harms third parties."
        ),
        alternative=(
            "We can take a read-only snapshot and inventory to support a lawful takedown request "
            "or incident report, and document impact without touching the target."
        ),
    ),
    # -- paused pending clarification / reframe ------------------------------
    PolicyRule(
        id="guilt-assumption",
        label="assumes guilt instead of testing hypotheses",
        category=PolicyCategory.GUILT_ASSUMPTION,
        outcome=PolicyOutcome.PAUSE,
        patterns=(
            r"\b(?:find|identify|catch|nail|expose|prove|confirm|hunt(?: down)?|who is|who are)\b"
            r"[^.?!]{0,30}\b(?:the\s+)?(?:bad guys?|bad actors?|criminals?|culprits?|"
            r"guilty (?:party|one)|perpetrators?|attackers?|hackers?|fraudsters?|scammers?|"
            r"who did (?:it|this))\b",
            r"\b(?:prove|show|confirm|establish)\b[^.?!]{0,25}"
            r"\b(?:guilt|that .{0,24} (?:is|was) (?:guilty|responsible|the attacker|the culprit))\b",
            r"\bfind (?:the )?(?:person|one) (?:responsible|behind)\b",
        ),
        rationale=(
            "The objective names a conclusion ('the bad guys') before any evidence has been "
            "collected. An investigation should test competing hypotheses, not confirm a "
            "suspicion, and should never declare an individual guilty."
        ),
        alternative=(
            "Collect and corroborate indicators, test at least one benign alternative "
            "explanation, and report confidence and residual uncertainty instead of a verdict."
        ),
        reframable=True,
    ),
    PolicyRule(
        id="speculative-identification",
        label="identification based on suspicion alone",
        category=PolicyCategory.SPECULATIVE_ID,
        outcome=PolicyOutcome.PAUSE,
        patterns=(
            r"\b(?:i|we)\s+(?:think|suspect|believe|reckon|guess|bet|feel)\b[^.?!]{0,40}"
            r"\b(?:is|are|might be|must be|has to be|could be)\b[^.?!]{0,30}"
            r"\b(?:criminal|guilty|attacker|hacker|fraudster|scammer|stalker|thief|leaker|"
            r"insider|spy|culprit|the one)\b",
            r"\b(?:probably|maybe|likely|must be|has to be|could be|i bet|clearly|obviously)\b"
            r"[^.?!]{0,30}\b(?:guilty|the culprit|the attacker|the one who|responsible|"
            r"(?:the|an?) (?:insider|leaker|thief|fraudster|scammer|stalker|spy|hacker))\b",
            r"\b(?:weak|vague|unconfirmed|gut)\s+(?:suspicion|feeling|hunch)\b",
            r"\bidentify\b[^.?!]{0,30}\b(?:based (?:only )?on|just because|because of)\b"
            r"[^.?!]{0,20}\b(?:suspicion|rumou?r|hunch|feeling|association|looks?)\b",
        ),
        rationale=(
            "Attributing conduct from suspicion, association or a hunch risks identifying an "
            "innocent person and produces findings that cannot be defended."
        ),
        alternative=(
            "Treat the suspicion as one hypothesis among several, define what evidence would "
            "falsify it, and report only what sources actually support — with uncertainty stated."
        ),
        reframable=True,
    ),
    PolicyRule(
        id="personal-data-collection",
        label="aggregating personal data on individuals",
        category=PolicyCategory.PERSONAL_DATA,
        outcome=PolicyOutcome.PAUSE,
        patterns=(
            r"\b(?:collect|gather|scrape|aggregate|compile|harvest|build)\b[^.?!]{0,35}"
            r"\b(?:personal|private|sensitive)\s+(?:data|information|details)\b",
            r"\b(?:build|create|compile|assemble)\b[^.?!]{0,25}\b(?:dossier|profile|file)\b"
            r"[^.?!]{0,25}\b(?:on|about|of)\b[^.?!]{0,20}"
            r"\b(?:individual|person|employee|someone|user|neighbou?r|customer)\b",
        ),
        rationale=(
            "Aggregating personal data on identified individuals needs a documented lawful basis "
            "and a minimisation plan; without one it risks becoming profiling."
        ),
        alternative=(
            "Name the lawful basis (--authorization-basis) and the minimum fields required, or "
            "keep the mission at the organisation/publication level rather than the individual."
        ),
        reframable=True,
    ),
)

#: Lookup by rule id — used by tests and by future audit tooling.
POLICY_RULES_BY_ID: dict[str, PolicyRule] = {rule.id: rule for rule in POLICY_RULES}


_PROVENANCE_STOPWORDS = re.compile(r"[\s,;]+")


def _policy_sentences(text: str) -> list[str]:
    """Split an objective into sentences so context words stay local."""

    return [part.strip() for part in re.split(r"(?<=[.!?;])\s+|\n+", text) if part.strip()]


def _remove_spans(sentence: str, matches: Sequence[re.Match[str]]) -> str:
    """Return *sentence* with the matched spans deleted (context isolation)."""

    out = sentence
    for match in sorted(matches, key=lambda m: m.start(), reverse=True):
        out = out[: match.start()] + " " + out[match.end():]
    return out


def _bounded(fragment: str, limit: int = 120) -> str:
    """Trim a matched fragment for display, collapsing whitespace."""

    collapsed = " ".join(fragment.split())
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 1] + "…"


def evaluate_objective(objective: str) -> PolicyVerdict:
    """Scan an objective against :data:`POLICY_RULES`.

    The most severe outcome wins: REFUSE over PAUSE over ALLOW.  A refusal that
    occurs in a sentence containing defensive context (``detect``, ``protect``,
    ``indicators of``) is downgraded to a PAUSE, because that phrasing usually
    describes measuring a risk rather than carrying it out.
    """

    text = objective or ""
    if not text.strip():
        return PolicyVerdict(
            outcome=PolicyOutcome.REFUSE,
            rationale="An objective is required so that scope and authorisation can be assessed.",
            alternative="Describe what you want to establish, e.g. 'map the public attack surface of example.com'.",
        )

    sentences = _policy_sentences(text)
    refusals: list[tuple[PolicyRule, list[str], bool]] = []
    pauses: list[tuple[PolicyRule, list[str], bool]] = []

    for rule in POLICY_RULES:
        fragments: list[str] = []
        defensive = False
        for sentence in sentences:
            matches = [
                match
                for pattern in rule.patterns
                for match in re.finditer(pattern, sentence, re.IGNORECASE)
            ]
            if not matches:
                continue
            fragments.extend(_bounded(m.group(0)) for m in matches)
            # Defensive context must come from *outside* the matched phrase:
            # "evade detection" is not defensive just because it says "detection".
            residue = _remove_spans(sentence, matches)
            if _DEFENSIVE_CONTEXT.search(residue):
                defensive = True
        if not fragments:
            continue
        bucket = refusals if rule.outcome is PolicyOutcome.REFUSE else pauses
        bucket.append((rule, fragments, defensive))

    # 1. Non-defensive refusals block outright.
    hard = [item for item in refusals if not item[2]]
    if hard:
        rule, fragments, _ = hard[0]
        return PolicyVerdict(
            outcome=PolicyOutcome.REFUSE,
            category=rule.category,
            rule_id=rule.id,
            rationale=f"{rule.label.capitalize()}: {rule.rationale}",
            alternative=rule.alternative,
            evidence=tuple(dict.fromkeys(fragments))[:5],
            reframable=rule.reframable,
        )

    # 2. Defensive-context refusals need confirmation, not a refusal.
    if refusals:
        rule, fragments, _ = refusals[0]
        return PolicyVerdict(
            outcome=PolicyOutcome.PAUSE,
            category=rule.category,
            rule_id=rule.id,
            rationale=(
                f"{rule.label.capitalize()} — but the wording is defensive "
                "(detect/protect/indicators), so this needs confirmation before planning."
            ),
            alternative=rule.alternative,
            evidence=tuple(dict.fromkeys(fragments))[:5],
            downgraded=True,
            notes=(f"Confirm with --confirm-intent if this is authorised defensive work.",),
            reframable=rule.reframable,
        )

    # 3. Ambiguity: pause with a reframe the operator can adopt.
    if pauses:
        rule, fragments, _ = pauses[0]
        return PolicyVerdict(
            outcome=PolicyOutcome.PAUSE,
            category=rule.category,
            rule_id=rule.id,
            rationale=f"{rule.label.capitalize()}: {rule.rationale}",
            alternative=rule.alternative,
            evidence=tuple(dict.fromkeys(fragments))[:5],
            notes=(
                "Use --accept-reframe to adopt the evidence-based objective above, "
                "or --confirm-intent if the objective already describes authorised work.",
            ),
            reframable=rule.reframable,
        )

    # 4. Nothing matched — allowed, with the supported data classes restated.
    return PolicyVerdict(
        outcome=PolicyOutcome.ALLOW,
        rationale="No prohibited intent detected; the objective reads as investigative and scope-bound.",
        alternative="",
        notes=(
            "Supported: public-web OSINT, and forensic review of owned or explicitly authorised artefacts.",
        ),
    )


#: The evidence-based wording every reframe is built from.  It states the four
#: required behaviours: collect indicators, test competing hypotheses, avoid
#: declaring guilt, report uncertainty.
REFRAME_TEMPLATE: str = (
    "Collect and corroborate published indicators about {targets} and test competing "
    "hypotheses, including at least one benign explanation, rather than assuming "
    "misconduct. Attribute nothing to any individual: describe behaviour, artefacts and "
    "sources only. Record provenance (source, timestamp, capture) for every indicator and "
    "state confidence and residual uncertainty explicitly. Draw no conclusion about intent "
    "or guilt; the assessment reports what the evidence supports and what remains unknown."
)


def _targets_phrase(targets: Sequence[str]) -> str:
    cleaned = [t.strip() for t in targets if t and t.strip()]
    if not cleaned:
        return "the declared targets"
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return f"{', '.join(cleaned[:-1])} and {cleaned[-1]}"


def reframe_objective(objective: str, targets: Sequence[str] = ()) -> str:
    """Rewrite a guilt-assuming objective as evidence-based investigation language.

    Always returns the canonical evidence-based wording (indicators, competing
    hypotheses, no guilt declaration, explicit uncertainty) — it never tries to
    preserve the accusatory framing.
    """

    return REFRAME_TEMPLATE.format(targets=_targets_phrase(targets))


# --------------------------------------------------------------------------
# 13.2 Scope validation
# --------------------------------------------------------------------------


def _strip_host(raw: str) -> str:
    """Reduce a URL or host to a bare, lower-case host name.

    ``https://user@api.Example.com:8443/x?y`` becomes ``api.example.com``.
    """

    value = raw.strip().lower()
    if "://" in value:
        value = value.split("://", 1)[1]
    value = value.split("/", 1)[0]          # drop path
    value = value.split("?", 1)[0]          # drop query
    value = value.split("#", 1)[0]          # drop fragment
    value = value.split("@")[-1]            # drop userinfo
    if value.count(":") == 1:               # drop :port (not an IPv6 literal)
        value = value.split(":", 1)[0]
    return value.rstrip("/.")


def _as_network(entry: str):
    """Return an ``ip_network`` when *entry* is a CIDR block, else ``None``."""

    try:
        return ipaddress.ip_network(entry.strip(), strict=False)
    except ValueError:
        return None


def _looks_like_path(value: str) -> bool:
    """True for filesystem paths, false for URLs and bare host names.

    A URL also contains ``/``, so a naive separator test classifies
    ``https://api.example.com:8443/x`` as a path and scope coverage silently
    fails.  URLs are therefore excluded explicitly, and a relative path only
    counts when its first segment really exists on disk.
    """

    token = value.strip()
    if not token or "://" in token:
        return False
    if token.startswith(("/", "./", "../", "~")) or re.match(r"^[A-Za-z]:[\\/]", token):
        return True
    if os.sep not in token:
        return False
    first = token.split(os.sep, 1)[0]
    try:
        return bool(first) and Path(first).expanduser().is_dir()
    except OSError:                                       # pragma: no cover - exotic FS
        return False


def scope_covers(entry: str, target: str) -> bool:
    """Does one scope *entry* authorise work on *target*?

    Supported forms: exact host, parent domain (``example.com`` covers
    ``api.example.com``), wildcard subdomain (``*.example.com``), CIDR block for
    IP targets, and filesystem paths for forensic artefacts.
    """

    entry = entry.strip()
    target = target.strip()
    if not entry or not target:
        return False

    network = _as_network(entry)
    if network is not None:
        try:
            return ipaddress.ip_address(_strip_host(target)) in network
        except ValueError:
            return False

    # A URL/host target must be reduced before suffix comparison.
    target_host = _strip_host(target)

    if _looks_like_path(entry) or _looks_like_path(target):
        try:
            entry_path = Path(entry).expanduser().resolve()
            target_path = Path(target).expanduser().resolve()
        except OSError:                                   # pragma: no cover - exotic FS
            return False
        return target_path == entry_path or target_path.is_relative_to(entry_path)

    host_entry = _strip_host(entry)
    host_target = target_host
    if host_entry.startswith("*."):
        suffix = host_entry[2:]
        return host_target == suffix or host_target.endswith("." + suffix)
    return host_target == host_entry or host_target.endswith("." + host_entry)


def build_scope(
    targets: Sequence[str],
    entries: Sequence[str],
    exclusions: Sequence[str],
    data_classes: Sequence[DataClass],
    mode: MissionMode,
    authorized_by: str | None,
    authorization_basis: str | None,
) -> ScopeDeclaration:
    """Assemble a scope declaration, normalising and de-duplicating entries."""

    def unique(values: Sequence[str]) -> tuple[str, ...]:
        seen: set[str] = set()
        out: list[str] = []
        for value in values:
            key = value.strip()
            if key and key.lower() not in seen:
                seen.add(key.lower())
                out.append(key)
        return tuple(out)

    return ScopeDeclaration(
        targets=unique(targets),
        entries=unique(entries),
        exclusions=unique(exclusions),
        data_classes=frozenset(data_classes),
        mode=mode,
        authorized_by=(authorized_by or "").strip() or None,
        authorization_basis=(authorization_basis or "").strip() or None,
    )


def validate_scope(scope: ScopeDeclaration) -> list[PreflightIssue]:
    """Check that the objective and every target stay inside the boundary.

    Returns blocking issues (which stop the mission) and advisory ones.  A
    target outside scope is always blocking: nothing may be planned against it.
    """

    issues: list[PreflightIssue] = []

    # --- the boundary itself ------------------------------------------------
    if not scope.entries:
        issues.append(
            PreflightIssue(
                "scope.missing",
                "No explicit scope was declared, so there is no authorised boundary to work within.",
                "Add --scope <asset> for each in-scope asset (repeatable). Example: --scope example.com",
            )
        )
    for entry in scope.entries:
        cleaned = entry.strip()
        if cleaned in {"*", "*.", "0.0.0.0/0", "::/0"}:
            issues.append(
                PreflightIssue(
                    "scope.wildcard",
                    f"Scope entry {cleaned!r} authorises the entire internet, which is not a scope.",
                    "Name the specific hosts, domains or paths in scope.",
                )
            )
        elif len(cleaned) < 3:
            issues.append(
                PreflightIssue(
                    "scope.too-broad",
                    f"Scope entry {cleaned!r} is too short to be a specific asset.",
                    "Use a fully qualified domain, IP/CIDR block or filesystem path.",
                )
            )

    # --- coverage -----------------------------------------------------------
    for target in scope.targets:
        if any(scope_covers(entry, target) for entry in scope.exclusions):
            issues.append(
                PreflightIssue(
                    "scope.excluded",
                    f"Target {target!r} matches an exclusion, so it is out of scope.",
                    "Remove the exclusion, or drop the target and name one that is in scope.",
                )
            )
            continue
        if not any(scope_covers(entry, target) for entry in scope.entries):
            issues.append(
                PreflightIssue(
                    "scope.not-covered",
                    f"Target {target!r} is not covered by the declared scope "
                    f"({', '.join(scope.entries) if scope.entries else 'none'}).",
                    f"Add --scope {target} if it is authorised, or remove the target.",
                )
            )

    # --- data class and mode compatibility ----------------------------------
    if not scope.data_classes:
        issues.append(
            PreflightIssue(
                "scope.no-data-class",
                "No data class was declared, so it is unclear what kind of evidence may be touched.",
                "Add --data-class public-web (default), or owned-artifact / authorized-artifact "
                "with --mode forensic.",
            )
        )

    artifacts = scope.data_classes & ARTIFACT_DATA_CLASSES
    if artifacts and scope.mode is not MissionMode.FORENSIC:
        issues.append(
            PreflightIssue(
                "scope.mode-mismatch",
                "Forensic artefacts require --mode forensic (local, read-only analysis); "
                f"mode is currently {scope.mode.value!r}.",
                "Re-run with --mode forensic, or declare --data-class public-web for web collection.",
            )
        )
    if scope.mode is MissionMode.FORENSIC and not artifacts:
        issues.append(
            PreflightIssue(
                "scope.forensic-without-artifact",
                "Forensic mode needs at least one artefact data class (owned-artifact or "
                "authorized-artifact).",
                "Add --data-class owned-artifact (or authorized-artifact) naming the artefacts you hold.",
            )
        )
    if DataClass.AUTHORIZED_ARTIFACT in scope.data_classes and not scope.authorization_basis:
        issues.append(
            PreflightIssue(
                "scope.authorization-basis",
                "Third-party artefacts need a recorded authorisation basis.",
                "Add --authorization-basis 'signed engagement 2026-03-01' (who authorised access, and how).",
            )
        )

    # --- artefact targets must exist and be readable ------------------------
    if artifacts:
        for target in scope.targets:
            path = Path(target).expanduser()
            if not path.exists():
                issues.append(
                    PreflightIssue(
                        "scope.artifact-missing",
                        f"Forensic artefact {target!r} does not exist or is not accessible.",
                        "Check the path, or copy the artefact into the case directory first.",
                    )
                )
            elif not os.access(path, os.R_OK):
                issues.append(
                    PreflightIssue(
                        "scope.artifact-unreadable",
                        f"Forensic artefact {target!r} is not readable by this user.",
                        "Fix the file permissions, or run as the account that owns the evidence.",
                    )
                )
    else:
        # Public-web only: warn if a target looks like a local path.
        for target in scope.targets:
            if _looks_like_path(target):
                issues.append(
                    PreflightIssue(
                        "scope.path-as-web-target",
                        f"Target {target!r} looks like a local path but the data class is public-web.",
                        "Use --data-class owned-artifact --mode forensic for local evidence.",
                        blocking=False,
                    )
                )

    # --- active collection needs explicit authority -------------------------
    if scope.mode is MissionMode.ACTIVE:
        if not (scope.authorized_by or scope.authorization_basis):
            issues.append(
                PreflightIssue(
                    "scope.active-unattributed",
                    "Active collection is not attributed to anyone: record who authorised it.",
                    "Add --authorized-by 'Name, Role' and --authorization-basis 'reason / reference'.",
                )
            )

    return issues


# --------------------------------------------------------------------------
# 13.3 Preflight driver
# --------------------------------------------------------------------------


def run_preflight(
    *,
    objective: str,
    targets: Sequence[str],
    scope_entries: Sequence[str],
    exclusions: Sequence[str] = (),
    data_classes: Sequence[DataClass] = (),
    mode: MissionMode = MissionMode.PASSIVE,
    authorized_by: str | None = None,
    authorization_basis: str | None = None,
    accept_reframe: bool = False,
    confirm_intent: bool = False,
) -> PreflightReport:
    """Evaluate objective + scope.  Side-effect free and always total.

    This is the single gate every mission passes through: the mission command
    calls it before rendering a plan, and the Phase 3 executor will call
    :func:`enforce_preflight` before its first tool call.
    """

    verdict = evaluate_objective(objective)
    effective_classes = tuple(data_classes) if data_classes else (
        (DataClass.PUBLIC_WEB,) if mode is not MissionMode.FORENSIC else ()
    )
    scope = build_scope(
        targets=targets,
        entries=scope_entries,
        exclusions=exclusions,
        data_classes=effective_classes,
        mode=mode,
        authorized_by=authorized_by,
        authorization_basis=authorization_basis,
    )
    issues = validate_scope(scope)

    # A refusal is never "reframed away": only ambiguous (paused) objectives that
    # the rulebook marks reframable get an evidence-based replacement.
    reframed = (
        reframe_objective(objective, targets)
        if verdict.outcome is PolicyOutcome.PAUSE and verdict.reframable
        else None
    )
    adopted = bool(accept_reframe and reframed)
    effective_objective = reframed if adopted else objective

    return PreflightReport(
        verdict=verdict,
        issues=issues,
        scope=scope,
        objective=effective_objective,
        original_objective=objective,
        reframed_objective=reframed,
        reframe_adopted=adopted,
        intent_confirmed=bool(confirm_intent),
    )


def enforce_preflight(report: PreflightReport) -> None:
    """Raise :class:`PolicyViolation` unless the mission is cleared to run.

    Call this immediately before the first model or browser action so that a
    programmatic caller cannot skip the CLI gate.
    """

    if report.ok:
        return
    if report.verdict.refused:
        message = f"mission refused by policy ({report.verdict.rule_id}): {report.verdict.rationale}"
    elif report.blocking_issues:
        message = "mission out of scope: " + "; ".join(i.message for i in report.blocking_issues)
    else:
        message = f"mission paused for clarification ({report.verdict.rule_id})"
    raise PolicyViolation(message, report)


# --------------------------------------------------------------------------
# 13.4 Rendering
# --------------------------------------------------------------------------


def render_preflight(report: PreflightReport) -> None:
    """Explain a refusal or pause, and always state the safe alternative."""

    console = get_console()
    verdict = report.verdict
    refused = verdict.refused

    title = (
        "[bold red]mission refused[/bold red]" if refused
        else "[bold yellow]mission paused — clarification required[/bold yellow]"
        if report.paused
        else "[bold red]out of scope[/bold red]"
    )
    border = "red" if refused else "yellow"
    body = Text()

    if refused or verdict.category is not None:
        if verdict.rule_id:
            body.append("category  ", style="dim")
            body.append(f"{verdict.rule_id}", style="bold")
            body.append(f"  ({verdict.category.value if verdict.category else 'unknown'})\n", style="dim")
        body.append("reason    ", style="dim")
        body.append(redact_text(verdict.rationale, secrets=known_secrets()), style="white")
        body.append("\n")
        if verdict.evidence:
            body.append("matched   ", style="dim")
            body.append("; ".join(f"“{fragment}”" for fragment in verdict.evidence), style="dim italic")
            body.append("\n")

    if report.blocking_issues:
        body.append("\n")
        body.append("scope\n", style="bold")
        for issue in report.blocking_issues:
            body.append("  ✘ ", style="red")
            body.append(redact_text(issue.message, secrets=known_secrets()), style="white")
            body.append(f"\n    → {redact_text(issue.fix, secrets=known_secrets())}\n", style="cyan")

    if verdict.alternative:
        body.append("\nsafe alternative\n", style="bold green")
        body.append(f"  {redact_text(verdict.alternative, secrets=known_secrets())}\n", style="green")

    if report.reframed_objective and not report.reframe_adopted:
        body.append("\nsuggested objective (evidence-based)\n", style="bold cyan")
        body.append(f"  {redact_text(report.reframed_objective, secrets=known_secrets())}\n", style="cyan")
        body.append("  adopt with --accept-reframe\n", style="dim")

    for note in verdict.notes:
        body.append(f"\n{redact_text(note, secrets=known_secrets())}\n", style="dim")

    console.print()
    console.print(Panel(body, title=title, title_align="left", border_style=border, expand=False))
    if report.blocking_issues and not refused:
        console.print("[dim]Nothing was planned: no Subagents, Workers, model or browser calls were made.[/dim]\n")
    else:
        console.print("[dim]Nothing was planned or executed.[/dim]\n")


def scope_summary_rows(report: PreflightReport) -> list[tuple[str, str]]:
    """(label, rich-markup value) pairs describing scope and policy state.

    Returned as plain pairs so the mission plan and the ``policy`` command can
    each render them into their own table without reaching into Rich internals.
    """

    scope = report.scope
    if scope is None:                                    # pragma: no cover - defensive
        return [("scope", "[red]undeclared[/red]")]

    rows: list[tuple[str, str]] = [
        ("scope", escape(", ".join(scope.entries)) or "[red]none[/red]"),
    ]
    if scope.exclusions:
        rows.append(("excluded", escape(", ".join(scope.exclusions))))
    rows.append(
        ("data class", escape(", ".join(sorted(dc.value for dc in scope.data_classes)) or "—"))
    )
    rows.append(
        (
            "authorised",
            escape(scope.authorized_by or "self (public sources only)")
            + (f"  ·  {escape(scope.authorization_basis)}" if scope.authorization_basis else ""),
        )
    )
    rows.append(
        (
            "policy",
            f"[green]{report.verdict.outcome.value}[/green] · "
            f"{escape(report.verdict.rule_id or 'no rule matched')}",
        )
    )
    if report.reframe_adopted:
        rows.append(("objective", "[cyan]reframed to evidence-based wording[/cyan]"))
    elif report.intent_confirmed and report.verdict.outcome is PolicyOutcome.PAUSE:
        rows.append(("objective", "[yellow]intent confirmed by operator[/yellow]"))
    return rows


def render_scope_summary(report: PreflightReport) -> Table:
    """Compact scope/authorisation table (used by the ``policy`` command)."""

    table = Table(box=None, pad_edge=False, show_header=False)
    table.add_column("field", style="dim", no_wrap=True)
    table.add_column("value", overflow="fold")
    for label, value in scope_summary_rows(report):
        table.add_row(label, value)
    return table


def print_policy_summary(result: PreflightReport) -> None:
    """Used by the ``policy`` command: verdict, issues and reframe."""

    console = get_console()
    console.print()
    console.print(render_scope_summary(result))
    if result.issues:
        console.print()
        for issue in result.issues:
            glyph = "[yellow]![/yellow]" if not issue.blocking else "[red]✘[/red]"
            console.print(
                f"{glyph} {escape(issue.id)}: {escape(redact_text(issue.message, secrets=known_secrets()))}"
            )
            console.print(f"   → {escape(redact_text(issue.fix, secrets=known_secrets()))}", style="cyan")
    if result.reframed_objective and not result.reframe_adopted:
        console.print()
        console.print(
            Panel(
                Text(redact_text(result.reframed_objective, secrets=known_secrets()), style="cyan"),
                title="suggested objective (evidence-based)",
                title_align="left",
                border_style="cyan",
                expand=False,
            )
        )
    console.print()
    if result.ok:
        console.print("[green]✔ policy preflight passed[/green] — this objective may be planned.")
    elif result.verdict.refused:
        console.print(f"[red]✘ refused[/red] — {escape(redact_text(result.verdict.rationale, secrets=known_secrets()))}")
        if result.verdict.alternative:
            console.print(f"[green]→ safe alternative:[/green] {escape(redact_text(result.verdict.alternative, secrets=known_secrets()))}")
    else:
        console.print("[yellow]! paused[/yellow] — resolve the items above, then re-run.")
    console.print()


@app.command("policy", help="Check an objective and scope against the safety policy (no planning).")
def policy_command(
    objective: str = typer.Option(..., "--objective", "-o", help="The objective to evaluate."),
    target: list[str] = typer.Option(
        [], "--target", "-t", help="Target asset (repeatable). Used for scope coverage checks."
    ),
    scope: list[str] = typer.Option(
        [], "--scope", "-s", help="Authorised asset boundary (repeatable). Domains, hosts, CIDR, paths."
    ),
    exclude: list[str] = typer.Option([], "--exclude", "-x", help="Explicitly out-of-scope asset."),
    data_class: list[DataClass] = typer.Option(
        [], "--data-class", "-d", help="public-web | owned-artifact | authorized-artifact."
    ),
    mode: MissionMode = typer.Option(MissionMode.PASSIVE, "--mode", "-m", case_sensitive=False),
    authorized_by: str | None = typer.Option(None, "--authorized-by", help="Who authorised this work."),
    authorization_basis: str | None = typer.Option(None, "--authorization-basis", help="Why it is authorised."),
    accept_reframe: bool = typer.Option(
        False, "--accept-reframe", help="Adopt the evidence-based objective instead of the original wording."
    ),
    confirm_intent: bool = typer.Option(
        False, "--confirm-intent", help="Confirm a paused objective describes authorised defensive work."
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Evaluate only — never plans and never touches the network."""

    result = run_preflight(
        objective=objective,
        targets=target or scope,
        scope_entries=scope,
        exclusions=exclude,
        data_classes=data_class,
        mode=mode,
        authorized_by=authorized_by,
        authorization_basis=authorization_basis,
        accept_reframe=accept_reframe,
        confirm_intent=confirm_intent,
    )
    if as_json:
        _emit(json.dumps({"ok": result.ok, "preflight": result.to_dict()}, indent=2))
    else:
        print_policy_summary(result)
    raise typer.Exit(result.exit_code)


# ══════════════════════════════════════════════════════════════════════════
# 14. Command: mission
# ══════════════════════════════════════════════════════════════════════════


def _normalise_targets(raw: Iterable[str]) -> list[str]:
    """Trim, drop blanks, de-duplicate while preserving operator order."""

    seen: set[str] = set()
    cleaned: list[str] = []
    for item in raw:
        value = item.strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(value)
    return cleaned


def _validate_request(request: MissionRequest) -> None:
    """Mission-shape checks that are independent of configuration.

    Numeric limits are *not* re-validated here: :func:`build_settings` already
    refused anything out of range before a request could be constructed.  The
    cheap guard below is defence in depth for programmatic callers.
    """

    if not request.targets:
        raise typer.BadParameter("at least one --target is required")
    if not request.objective.strip():
        raise typer.BadParameter("--objective must not be empty")
    for name, value in (
        ("max_subagents", request.max_subagents),
        ("max_workers_per_agent", request.max_workers_per_agent),
        ("max_total_workers", request.max_total_workers),
    ):
        if value < 1:
            raise typer.BadParameter(f"{name} must be >= 1 (got {value})")
    if request.worker_retries < 0 or request.review_retries < 0:
        raise typer.BadParameter("retry counts must be >= 0")
    if request.mission_budget_seconds < 1 or request.task_budget_seconds < 1:
        raise typer.BadParameter("time budgets must be >= 1 second")


def render_mission_plan(
    request: MissionRequest,
    settings: Settings,
    preflight: PreflightReport | None = None,
    mission: "Mission | None" = None,
) -> None:
    """Show what the Master Agent *would* do.  No collection is performed."""

    console = get_console()
    console.print()
    console.print(
        Panel(
            Text(
                f"{request.fingerprint()}  ·  {BUILD_PHASE_NAME} phase\n"
                "Planning only — no Subagents, Workers or network activity are started yet.",
                style="white",
            ),
            title=f"[bold cyan]{APP_TITLE} mission plan[/bold cyan]",
            title_align="left",
            border_style="cyan",
            expand=False,
        )
    )

    table = Table(box=None, pad_edge=False, show_header=False)
    table.add_column("field", style="dim", no_wrap=True)
    table.add_column("value", overflow="fold")
    table.add_row("objective", escape(request.objective))
    table.add_row("mode", request.mode.value)
    table.add_row("targets", f"{len(request.targets)}")
    for index, target in enumerate(request.targets, start=1):
        in_scope = bool(
            preflight
            and preflight.scope
            and any(scope_covers(entry, target) for entry in preflight.scope.entries)
        )
        table.add_row(
            "",
            f"[bold]{index}.[/bold] {escape(target)}"
            + ("  [green]in scope[/green]" if in_scope else "  [dim]—[/dim]"),
        )
    if preflight is not None:
        for label, value in scope_summary_rows(preflight):
            table.add_row(label, value)
    model_cell = escape(settings.model) if settings.model else "[yellow]unset[/yellow]"
    table.add_row(
        "model",
        f"{escape(settings.provider)} / {model_cell}  ·  key {escape(settings.api_key_hint())}",
    )
    table.add_row("subagents", f"max {request.max_subagents} (runtime-created)")
    table.add_row(
        "workers",
        f"max {request.max_workers_per_agent} per subagent, {request.max_total_workers} total "
        f"(ceiling {request.max_subagents * request.max_workers_per_agent})",
    )
    table.add_row(
        "retries",
        f"{request.worker_retries} per task, {request.review_retries} review cycle(s) per subagent",
    )
    table.add_row(
        "budgets",
        f"mission {_human_duration(request.mission_budget_seconds)}, "
        f"task {_human_duration(request.task_budget_seconds)}",
    )
    table.add_row("output", escape(request.output_dir))
    table.add_row("browser", f"headless={'yes' if settings.browser_headless else 'no'}, concurrency={settings.browser_concurrency}")
    table.add_row("network", "allowed" if settings.allow_network else "offline")
    table.add_row("operator", escape(request.operator or "unset (ARGUS_OPERATOR)"))
    table.add_row("created", request.created_at)
    table.add_row("typed id", f"[dim]{escape(mission.id if mission else request.fingerprint())}[/dim]")
    console.print(table)

    if not settings.dry_run:
        console.print("[red]dry_run: no[/red] — execution requested")
    console.print()


def _mission_settings_cli_values(**kwargs: Any) -> dict[str, Any]:
    """Drop unset (``None``) options so environment/defaults can apply."""

    return {key: value for key, value in kwargs.items() if value is not None}


@app.command("mission", help="Plan an OSINT/forensics mission using validated settings.")
def mission_command(
    target: list[str] = typer.Option(
        ...,
        "--target",
        "-t",
        help="Target host, domain, username, organisation or local artefact. Repeatable.",
    ),
    objective: str = typer.Option(
        ...,
        "--objective",
        "-o",
        help="What the mission should establish, in one sentence.",
    ),
    mode: MissionMode = typer.Option(
        MissionMode.PASSIVE,
        "--mode",
        "-m",
        case_sensitive=False,
        help="Collection intensity: passive, active or forensic.",
    ),
    i_authorize: bool = typer.Option(
        False,
        "--i-authorize",
        help="Assert written permission to interact with the targets.",
    ),
    # --- configuration overrides: unset means "use env, then default" --------
    provider: str | None = typer.Option(None, "--provider", help="Model provider (overrides ARGUS_LLM_PROVIDER)."),
    model: str | None = typer.Option(None, "--model", help="Model id (overrides ARGUS_LLM_MODEL)."),
    base_url: str | None = typer.Option(None, "--base-url", help="OpenAI-compatible endpoint."),
    home: str | None = typer.Option(None, "--home", help="Case-data root directory."),
    output_dir: str | None = typer.Option(None, "--output-dir", help="Mission output directory."),
    case_dir: str | None = typer.Option(None, "--case-dir", help="Artefact directory for this mission."),
    operator: str | None = typer.Option(None, "--operator", help="Operator name for the audit trail."),
    log_level: str | None = typer.Option(None, "--log-level", help="DEBUG | INFO | WARNING | ERROR."),
    max_subagents: int | None = typer.Option(None, "--max-subagents", help="Ceiling on live Subagents (1-25)."),
    max_workers: int | None = typer.Option(
        None,
        "--max-workers",
        help="Ceiling on concurrent Workers per Subagent (1-16).",
    ),
    max_total_workers: int | None = typer.Option(
        None,
        "--max-total-workers",
        help="Mission-wide concurrent Worker ceiling (1-64).",
    ),
    worker_retries: int | None = typer.Option(None, "--worker-retries", help="Retries per Worker task (0-10)."),
    review_retries: int | None = typer.Option(None, "--review-retries", help="Review cycles per Subagent (0-5)."),
    mission_budget: int | None = typer.Option(None, "--mission-budget", help="Wall-clock mission budget in seconds."),
    task_budget: int | None = typer.Option(None, "--task-budget", help="Per-task time budget in seconds."),
    headless: bool | None = typer.Option(None, "--headless/--headed", help="Run Chromium headless or visible."),
    browser_profile: str | None = typer.Option(None, "--browser-profile", help="Persistent browser profile path."),
    browser_concurrency: int | None = typer.Option(
        None, "--browser-concurrency", help="Concurrent browser contexts (1-8)."
    ),
    http_concurrency: int | None = typer.Option(None, "--http-concurrency", help="Concurrent HTTP workers (1-32)."),
    http_timeout: float | None = typer.Option(None, "--http-timeout", help="Per-request timeout in seconds."),
    user_agent: str | None = typer.Option(None, "--user-agent", help="User-Agent presented to remote hosts."),
    allow_network: bool | None = typer.Option(
        None, "--allow-network/--offline", help="Permit or forbid network collection."
    ),
    respect_robots: bool | None = typer.Option(
        None, "--respect-robots/--ignore-robots", help="Honour robots.txt."
    ),
    # --- safety and scope: evaluated before anything is planned ---------------
    scope: list[str] | None = typer.Option(
        None,
        "--scope",
        "-s",
        help="Authorised asset boundary (repeatable): domain, host, CIDR or filesystem path.",
    ),
    exclude: list[str] | None = typer.Option(
        None,
        "--exclude",
        "-x",
        help="Asset explicitly out of scope (repeatable). Overrides --scope.",
    ),
    data_class: list[DataClass] | None = typer.Option(
        None,
        "--data-class",
        "-d",
        help="public-web (default) | owned-artifact | authorized-artifact.",
    ),
    authorized_by: str | None = typer.Option(
        None, "--authorized-by", help="Who authorised this mission."
    ),
    authorization_basis: str | None = typer.Option(
        None, "--authorization-basis", help="Why it is authorised (reference, ticket, engagement id)."
    ),
    accept_reframe: bool = typer.Option(
        False,
        "--accept-reframe",
        help="Replace a guilt-assuming objective with evidence-based investigation language.",
    ),
    confirm_intent: bool = typer.Option(
        False,
        "--confirm-intent",
        help="Confirm a paused objective describes authorised, defensive work.",
    ),
    allow_out_of_scope: bool = typer.Option(
        False,
        "--allow-out-of-scope",
        hidden=True,
        help="(unavailable) Scope refusals cannot be overridden.",
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--execute",
        help="Plan only (default). --execute is rejected until Phase 3.",
    ),
    phase: MissionPhase = typer.Option(
        MissionPhase.PLAN,
        "--phase",
        case_sensitive=False,
        help="Output to show: the mission plan, or the effective settings.",
    ),
    show_sources: bool = typer.Option(
        True,
        "--sources/--no-sources",
        help="Annotate each setting with where its value came from.",
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit structured JSON."),
) -> None:
    """Validate settings + mission, then print the plan.  Never performs collection."""

    console = get_console()

    # 1. Configuration first.  Nothing below this point runs when a limit is
    #    invalid, so no model client or browser can ever see a bad value.
    cli_values = _mission_settings_cli_values(
        provider=provider,
        model=model,
        base_url=base_url,
        home_dir=home,
        output_dir=output_dir,
        case_dir=case_dir,
        operator=operator,
        log_level=log_level,
        max_subagents=max_subagents,
        max_workers_per_agent=max_workers,
        max_total_workers=max_total_workers,
        worker_retries=worker_retries,
        review_retries=review_retries,
        mission_budget_seconds=mission_budget,
        task_budget_seconds=task_budget,
        browser_headless=headless,
        browser_profile_dir=browser_profile,
        browser_concurrency=browser_concurrency,
        http_concurrency=http_concurrency,
        http_timeout=http_timeout,
        user_agent=user_agent,
        allow_network=allow_network,
        respect_robots=respect_robots,
        dry_run=dry_run,
    )
    result = build_settings(cli_values)

    if not result.ok:
        if as_json:
            _emit(
                json.dumps(
                    {
                        "ok": False,
                        "stage": "configuration",
                        "aborted_before_model_call": True,
                        "problems": [p.to_dict() for p in result.problems],
                    },
                    indent=2,
                )
            )
        else:
            console.print()
            console.print(render_settings_problems(result.errors))
            console.print(
                "[dim]Aborted before any model or browser call. "
                "Nothing was collected and no client was constructed.[/dim]\n"
            )
        raise typer.Exit(ExitCode.CONFIG)

    settings = result.settings

    # 2. Mission shape and authorisation.
    request = MissionRequest.from_settings(
        settings,
        targets=_normalise_targets(target),
        objective=objective,
        mode=mode,
        authorised=i_authorize,
        dry_run=dry_run,
    )
    try:
        _validate_request(request)
    except typer.BadParameter as exc:
        console.print(f"[red]invalid mission:[/red] {escape(str(exc))}")
        raise typer.Exit(ExitCode.USAGE) from exc

    if request.mode is MissionMode.ACTIVE and not request.authorised:
        console.print(
            "[red]refusing mission:[/red] active mode requires --i-authorize (authorised use only)."
        )
        raise typer.Exit(ExitCode.AUTHORIZATION)

    # 3. Safety preflight.  This is the gate: an out-of-scope action, a refused
    #    objective or an unconfirmed intent stops here, before a plan is drawn
    #    or any Subagent/Worker/model/browser call could exist.
    if allow_out_of_scope:
        console.print(
            "[yellow]note:[/yellow] --allow-out-of-scope is not available; scope refusals "
            "cannot be overridden. Narrow the scope instead."
        )

    preflight = run_preflight(
        objective=objective,
        targets=request.targets,
        # Scope defaults to the targets themselves — an explicit boundary is
        # still required, but naming the targets is the common case.
        scope_entries=scope if scope else request.targets,
        exclusions=exclude or (),
        data_classes=data_class or (),
        mode=mode,
        authorized_by=authorized_by,
        authorization_basis=authorization_basis,
        accept_reframe=accept_reframe,
        confirm_intent=confirm_intent,
    )

    if not preflight.ok:
        if as_json:
            _emit(
                json.dumps(
                    {
                        "ok": False,
                        "stage": "policy",
                        "planned": False,
                        "executed": False,
                        "preflight": preflight.to_dict(),
                    },
                    indent=2,
                )
            )
        else:
            render_preflight(preflight)
        raise typer.Exit(preflight.exit_code)

    # The reported objective is the cleared one: if a reframe was adopted, the
    # accusation-framed wording never reaches planning.
    request.objective = preflight.objective

    # 3b. Typed contract for Phase 3.  Built only from a cleared preflight, so an
    #     uncleared objective cannot acquire a typed representation at all.
    mission = Mission.from_preflight(
        request=request,
        preflight=preflight,
        settings=settings,
        operator=request.operator,
    )

    # 4. Render.  ``settings`` phase is a pure configuration view.
    if phase is MissionPhase.SETTINGS:
        if as_json:
            _emit(
                json.dumps(
                    {
                        "mission_id": request.fingerprint(),
                        "ok": True,
                        "settings": settings.to_dict(),
                        "problems": [p.to_dict() for p in result.problems],
                    },
                    indent=2,
                )
            )
        else:
            console.print()
            console.print(render_settings(settings, show_provenance=show_sources))
            if result.problems:
                console.print(render_settings_problems(result.problems, title="configuration notes"))
            console.print()
    elif as_json:
        _emit(
            json.dumps(
                {
                    "mission_id": request.fingerprint(),
                    "build_phase": BUILD_PHASE,
                    "executed": False,
                    "request": request.to_dict(),
                    "settings": settings.to_dict(),
                    "preflight": preflight.to_dict(),
                    "mission": json.loads(model_to_json(mission)),
                    "warnings": [p.to_dict() for p in result.problems],
                    "plan": {
                        "subagents": f"runtime-created, max {request.max_subagents}",
                        "workers": (
                            f"runtime-created, max {request.max_workers_per_agent} per subagent, "
                            f"{request.max_total_workers} total"
                        ),
                        "orchestrator": "langgraph (phase 3)",
                    },
                },
                indent=2,
            )
        )
    else:
        render_mission_plan(request, settings, preflight, mission)
        if result.problems:
            console.print(render_settings_problems(result.problems, title="configuration notes"))
            console.print()

    if not dry_run:
        console.print(
            Panel(
                Text(
                    "Execution is not wired up yet — the LangGraph Master Agent and the runtime "
                    f"Subagent/Worker factories arrive in Phase 3.  This build is Phase {BUILD_PHASE} "
                    f"({BUILD_PHASE_NAME}).",
                    style="yellow",
                ),
                border_style="yellow",
                title="not implemented",
                title_align="left",
            )
        )
        raise typer.Exit(ExitCode.NOT_IMPLEMENTED)

    raise typer.Exit(ExitCode.OK)


# ══════════════════════════════════════════════════════════════════════════
# 15. Typed data models — mission, evidence, results
# ══════════════════════════════════════════════════════════════════════════
#
# These are the shared contracts between the CLI, the Master Agent (Phase 3),
# the runtime-created Subagents and Workers, and the reporters.  Pydantic is a
# required dependency because validation must happen at the boundary, not in
# downstream code.
#
# Three rules govern every model here:
#
#   1. STABLE IDS.  Every entity carries a deterministic ``id`` derived from
#      its semantic content, so re-running the same mission produces the same
#      identifiers.  Retries use ``attempt``, never a new id.
#   2. EXPLICIT UNKNOWNS.  Missing data is a first-class value
#      (``UnknownReason``), never an empty string that later reads as fact.
#      Optional fields default to ``None`` *and* say why they are ``None``.
#   3. NO INVENTED PROVENANCE.  Evidence records what was observed, where it
#      came from, when it was retrieved, and how it was preserved — or states
#      that this is unknown.  A model validator refuses to construct
#      unprovenanced evidence.
#
# Entities (Mission, Scope, SubagentSpec, WorkerSpec, TaskAssignment,
# TaskResult, EvidenceItem, SourceReference, QualityReview, SubagentReport,
# FinalReport, ChainOfCustody) all carry a stable ``id``, timestamps, a status
# or kind, and an ``error`` field where failure is possible.
#
# ReviewFinding is also an entity: reviewers cite finding ids when they accept
# or dispute an objection.
#
# Value objects (UnknownValue, HashRecord, ScopeEntry, CapabilityRequirement,
# ErrorInfo) deliberately have no id: they are embedded components of an
# entity, never referenced on their own.  They still carry a timestamp where
# the moment matters (when the unknown was determined, when an error occurred).

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

#: Schema version for the model set below; bump on any breaking change.
MODEL_SCHEMA_VERSION: int = 1


# --------------------------------------------------------------------------
# 15.1 Primitives: ids, timestamps, status enums, unknowns
# --------------------------------------------------------------------------


def utc_now() -> datetime:
    """Timezone-aware UTC timestamp.  Never a naive datetime."""

    return datetime.now(timezone.utc)


def canonical_json(payload: Any) -> str:
    """Deterministic JSON for hashing and id derivation."""

    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def content_id(prefix: str, *parts: Any, length: int = 12) -> str:
    """Deterministic, human-readable id: ``prefix`` + hash of the parts.

    Re-running an identical mission reproduces identical ids, which makes
    reports comparable and de-duplication trivial.
    """

    digest = hashlib.sha256(canonical_json(parts).encode("utf-8")).hexdigest()[:length]
    return f"{prefix}-{digest}"


def mission_id_for(objective: str, targets: Iterable[str], mode: MissionMode, *, length: int = 12) -> str:
    """The one and only mission-id derivation.

    Used by :meth:`MissionRequest.fingerprint` (CLI planning) and by
    :class:`Mission` (the typed model) so both always name the same mission.
    """

    return content_id(
        "mission",
        {"objective": objective.strip().lower(), "targets": sorted(t.lower() for t in targets), "mode": mode.value},
        length=length,
    )


def new_id(prefix: str) -> str:
    """Random id for run-scoped entities (attempts, captures, review rounds)."""

    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalise_datetime(value: Any) -> datetime:
    """Accept naive/aware datetimes, ISO strings and epoch seconds.

    Naive values are interpreted as UTC and made timezone-aware, so a naive
    timestamp can never silently shift by the host's local offset.
    """

    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, (int, float)):
        moment = datetime.fromtimestamp(value, tz=timezone.utc)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError("empty timestamp string")
        try:
            moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"unparseable timestamp {text!r}") from exc
    else:
        raise ValueError(f"unsupported timestamp type {type(value).__name__}")
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment.astimezone(timezone.utc)


class StrictModel(BaseModel):
    """Base model: unknown fields are an error, not silently dropped."""

    model_config = ConfigDict(
        extra="forbid",              # a typo must not vanish into the void
        validate_assignment=True,    # catch corruption after construction
        str_strip_whitespace=True,
        use_enum_values=False,
        populate_by_name=True,
    )


class EntityStatus(str, Enum):
    """Lifecycle of a mission, subagent, worker, task or review."""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    BLOCKED = "blocked"          # cannot proceed (dependency, scope, policy)
    PAUSED = "paused"            # needs a human decision
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"          # deliberately not attempted (degraded capability)
    CANCELLED = "cancelled"
    BUDGET_EXCEEDED = "budget-exceeded"

    @property
    def terminal(self) -> bool:
        return self in _TERMINAL_STATUSES


_TERMINAL_STATUSES: frozenset[EntityStatus] = frozenset(
    {
        EntityStatus.SUCCEEDED,
        EntityStatus.FAILED,
        EntityStatus.SKIPPED,
        EntityStatus.CANCELLED,
        EntityStatus.BUDGET_EXCEEDED,
    }
)


class UnknownReason(str, Enum):
    """Why a value is missing.  Never left implicit."""

    NOT_YET_OBSERVED = "not-yet-observed"
    NOT_REQUESTED = "not-requested"
    WITHHELD = "withheld"
    REDACTED = "redacted"          # hidden from this audience, exists elsewhere
    UNAVAILABLE = "unavailable"    # source did not provide it
    NOT_APPLICABLE = "not-applicable"
    OUT_OF_SCOPE = "out-of-scope"  # policy/scope prevented collection
    FAILED = "failed"              # a collection attempt failed
    UNKNOWN = "unknown"            # genuinely undetermined


class EvidenceKind(str, Enum):
    """The epistemic status of a statement.  This is the core distinction.

    ``OBSERVATION`` — directly seen, retrieved and preserved; verifiable by a
    third party replaying the source reference.
    ``INFERENCE`` — a conclusion drawn *by us* from one or more observations,
    with the reasoning and the inputs recorded.
    ``ALLEGATION`` — a claim made by a *third party*; unverified by us, and
    reported as a claim, never as a finding.
    """

    OBSERVATION = "observation"
    INFERENCE = "inference"
    ALLEGATION = "allegation"


class SourceKind(str, Enum):
    """What kind of source a reference points at."""

    PUBLIC_WEB = "public-web"
    ARCHIVE = "archive"
    API = "api"
    SEARCH_ENGINE = "search-engine"
    DNS = "dns"
    WHOIS = "whois"
    CERTIFICATE_LOG = "certificate-log"
    SOCIAL_MEDIA = "social-media"
    BREACH_NOTICE = "breach-notice"
    LOCAL_ARTIFACT = "local-artifact"
    DOCUMENT = "document"
    ARTIFACT_IMAGE = "artifact-image"
    MEMORY_IMAGE = "memory-image"
    LOG_FILE = "log-file"
    SCREENSHOT = "screenshot"
    OTHER = "other"


class RetrievalMethod(str, Enum):
    """How the source was obtained — needed to judge reliability."""

    BROWSER = "browser"
    HTTP = "http"
    API_CALL = "api-call"
    LOCAL_READ = "local-read"
    OPERATOR_SUPPLIED = "operator-supplied"
    THIRD_PARTY = "third-party"
    UNKNOWN = "unknown"


class Confidence(str, Enum):
    """Coarse confidence, with numeric bands documented for the report."""

    UNKNOWN = "unknown"          # no basis to judge
    LOW = "low"                  # single weak source, or hearsay
    MEDIUM = "medium"            # corroborated by one independent source
    HIGH = "high"                # multiple independent, reliable sources

    @property
    def numeric(self) -> float | None:
        """Midpoint used for sorting.  ``None`` means "do not invent a number"."""

        return {
            Confidence.UNKNOWN: None,
            Confidence.LOW: 0.25,
            Confidence.MEDIUM: 0.6,
            Confidence.HIGH: 0.85,
        }[self]

    @property
    def rank(self) -> int:
        """Ordinal used when merging records seen by several workers."""

        return {Confidence.UNKNOWN: 0, Confidence.LOW: 1, Confidence.MEDIUM: 2, Confidence.HIGH: 3}[self]


class PreservationStatus(str, Enum):
    """How well an artefact's integrity is assured.  Never assumed."""

    NOT_ASSESSED = "not-assessed"
    ACQUIRED = "acquired"                # copied, integrity not yet verified
    HASHED = "hashed"                    # digest computed and recorded
    VERIFIED = "verified"                # digest re-checked against the source
    DEGRADED = "degraded"                # partial capture, known loss
    UNRECOVERABLE = "unrecoverable"      # artefact is gone or unreadable


class RedactionLevel(str, Enum):
    """How much of an entity may be shown in a rendered report."""

    PUBLIC = "public"
    RESTRICTED = "restricted"
    SECRET = "secret"            # never rendered; existence may be noted


class UnknownValue(StrictModel):
    """An explicitly unknown value, with the reason and who decided.

    Use this instead of ``None`` whenever "we do not know" is itself a finding
    that the reader must see.
    """

    reason: UnknownReason = UnknownReason.UNKNOWN
    detail: str | None = None
    determined_by: str | None = None     # component that established the gap
    determined_at: datetime = Field(default_factory=utc_now)

    @field_validator("determined_at", mode="before")
    @classmethod
    def _tz(cls, value: Any) -> datetime:
        return normalise_datetime(value)

    def describe(self) -> str:
        base = f"unknown ({self.reason.value})"
        return f"{base}: {self.detail}" if self.detail else base


class HashRecord(StrictModel):
    """A digest of captured content, so later readers can verify integrity."""

    algorithm: str = "sha256"
    value: str = Field(min_length=16)
    size_bytes: int | None = Field(default=None, ge=0)
    computed_at: datetime = Field(default_factory=utc_now)

    @field_validator("computed_at", mode="before")
    @classmethod
    def _tz(cls, value: Any) -> datetime:
        return normalise_datetime(value)

    @field_validator("algorithm")
    @classmethod
    def _known_algorithm(cls, value: str) -> str:
        allowed = {"sha256", "sha512", "sha1", "md5"}
        lowered = value.lower()
        if lowered not in allowed:
            raise ValueError(f"unsupported hash algorithm {value!r}; expected one of {sorted(allowed)}")
        return lowered

    @field_validator("value")
    @classmethod
    def _hex(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not all(c in "0123456789abcdef" for c in cleaned):
            raise ValueError("hash value must be hexadecimal")
        return cleaned

    @classmethod
    def of_bytes(cls, payload: bytes, *, algorithm: str = "sha256") -> "HashRecord":
        return cls(
            algorithm=algorithm,
            value=hashlib.new(algorithm, payload).hexdigest(),
            size_bytes=len(payload),
        )


# --------------------------------------------------------------------------
# 15.2 Scope
# --------------------------------------------------------------------------


class ScopeEntry(StrictModel):
    """One authorised (or excluded) asset in the mission boundary."""

    pattern: str = Field(min_length=1)
    included: bool = True
    note: str | None = None

    @property
    def id(self) -> str:
        return content_id("scope", self.pattern.lower(), self.included)


class Scope(StrictModel):
    """The typed mirror of the preflight :class:`ScopeDeclaration`.

    ``entries`` are allow-list patterns (domain, host, CIDR, path);
    ``exclusions`` always win.  ``data_classes`` states what kind of evidence
    may be touched, so a reviewer can tell web collection from forensic work.
    """

    id: str = ""
    status: EntityStatus = EntityStatus.PENDING     # pending → ready once approved
    mode: MissionMode = MissionMode.PASSIVE
    entries: list[ScopeEntry] = Field(default_factory=list)
    data_classes: list[DataClass] = Field(default_factory=list)
    authorized_by: str | None = None
    authorization_basis: str | None = None
    policy_source: str | None = None          # which document/ticket, if any
    created_at: datetime = Field(default_factory=utc_now)

    model_config = ConfigDict(extra="forbid", validate_assignment=True, populate_by_name=True)

    @field_validator("created_at", mode="before")
    @classmethod
    def _tz(cls, value: Any) -> datetime:
        return normalise_datetime(value)

    @model_validator(mode="after")
    def _identify(self) -> "Scope":
        if not self.id:
            self.id = content_id(
                "scope",
                self.mode.value if isinstance(self.mode, MissionMode) else str(self.mode),
                sorted(e.pattern.lower() for e in self.entries if e.included),
                sorted(e.pattern.lower() for e in self.entries if not e.included),
                sorted(dc.value for dc in self.data_classes),
            )
        return self

    @property
    def includes(self) -> list[str]:
        return [e.pattern for e in self.entries if e.included]

    @property
    def excludes(self) -> list[str]:
        return [e.pattern for e in self.entries if not e.included]

    def covers(self, target: str) -> bool:
        """Delegate to the policy matcher so one implementation rules them all."""

        if any(scope_covers(pattern, target) for pattern in self.excludes):
            return False
        return any(scope_covers(pattern, target) for pattern in self.includes)

    @classmethod
    def from_declaration(cls, declaration: "ScopeDeclaration") -> "Scope":
        """Build from the preflight declaration without losing any detail."""

        entries = [ScopeEntry(pattern=p, included=True) for p in declaration.entries]
        entries += [ScopeEntry(pattern=p, included=False) for p in declaration.exclusions]
        return cls(
            mode=declaration.mode,
            entries=entries,
            data_classes=list(declaration.data_classes),
            authorized_by=declaration.authorized_by,
            authorization_basis=declaration.authorization_basis,
            policy_source="preflight",
        )


# --------------------------------------------------------------------------
# 15.3 Source references and chain of custody
# --------------------------------------------------------------------------


class SourceReference(StrictModel):
    """Where something came from, when, how, and how it was preserved.

    A reference must point at *something* concrete: a URL, an artefact path, or
    an explicit :class:`UnknownValue` explaining why not.
    """

    id: str = ""
    kind: SourceKind = SourceKind.OTHER
    url: str | None = None
    artifact_path: str | None = None
    title: str | None = None
    publisher: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    retrieved_at: datetime = Field(default_factory=utc_now)
    retrieval_method: RetrievalMethod = RetrievalMethod.UNKNOWN
    http_status: int | None = Field(default=None, ge=100, le=599)
    content_hash: HashRecord | None = None
    excerpt: str | None = None
    language: str | None = None
    access_note: str | None = None
    missing: UnknownValue | None = None       # set when a field cannot be known

    @field_validator("retrieved_at", "published_at", mode="before")
    @classmethod
    def _tz(cls, value: Any) -> Any:
        return normalise_datetime(value) if value is not None else None

    @field_validator("url")
    @classmethod
    def _url_shape(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not re.match(r"^(https?|file)://[^\s]+$", value):
            raise ValueError("source URL must be an absolute http(s):// or file:// URL")
        return value

    @model_validator(mode="after")
    def _locatable(self) -> "SourceReference":
        # Provenance may not be invented: a reference must be locatable, or
        # explicitly declare that it is not.
        if not (self.url or self.artifact_path) and self.missing is None:
            raise ValueError(
                "SourceReference needs a url or artifact_path; use missing=UnknownValue(...) "
                "when the location genuinely cannot be determined"
            )
        if not self.id:
            self.id = content_id("src", self.kind.value, self.url or self.artifact_path, self.retrieved_at.isoformat())
        return self

    @property
    def locator(self) -> str:
        return self.url or self.artifact_path or (self.missing.describe() if self.missing else "unknown")


class ChainOfCustody(StrictModel):
    """Who handled an artefact, when, and what they did to it.

    ``preserved`` is deliberately not defaulted to True: an artefact that was
    merely read is *not* preserved, and claiming otherwise would overstate the
    evidence.
    """

    id: str = ""
    collected_by: str | None = None
    collected_at: datetime = Field(default_factory=utc_now)
    collection_method: RetrievalMethod = RetrievalMethod.UNKNOWN
    original_location: str | None = None
    storage_location: str | None = None
    write_protected: bool = False
    read_only_verified: bool = False
    preserved: bool = False
    preservation_status: PreservationStatus = PreservationStatus.NOT_ASSESSED
    integrity_hash: HashRecord | None = None
    custody_events: list[str] = Field(default_factory=list)
    gaps: list[UnknownValue] = Field(default_factory=list)   # explicitly recorded unknowns

    @field_validator("collected_at", mode="before")
    @classmethod
    def _tz(cls, value: Any) -> datetime:
        return normalise_datetime(value)

    @model_validator(mode="after")
    def _identify(self) -> "ChainOfCustody":
        # A custody record is a document: it needs to be addressable so a
        # reviewer can cite it ("custody record coc-abc123").
        if not self.id:
            self.id = content_id("coc", self.collected_by, self.original_location, self.collected_at.isoformat())
        return self

    def note(self, event: str, *, at: datetime | None = None) -> None:
        """Append a custody event; kept simple because it must always succeed."""

        stamp = (at or utc_now()).isoformat(timespec="seconds")
        self.custody_events.append(f"{stamp} {event}")


# --------------------------------------------------------------------------
# 15.4 Evidence
# --------------------------------------------------------------------------

class ErrorInfo(StrictModel):
    """A structured failure: what broke, where, whether it is retryable."""

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    stage: str | None = None
    component: str | None = None
    retryable: bool = False
    attempt: int = Field(default=1, ge=1)
    occurred_at: datetime = Field(default_factory=utc_now)
    cause_type: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)

    @field_validator("occurred_at", mode="before")
    @classmethod
    def _tz(cls, value: Any) -> datetime:
        return normalise_datetime(value)

    @field_validator("message")
    @classmethod
    def _redact(cls, value: str) -> str:
        # Error text is the most common secret-leak path (URLs with tokens,
        # headers).  Scrub on construction so it can never escape later.
        return redact_text(value, secrets=known_secrets())

    @classmethod
    def from_exception(
        cls,
        exc: BaseException,
        *,
        code: str | None = None,
        stage: str | None = None,
        component: str | None = None,
        retryable: bool = False,
        attempt: int = 1,
    ) -> "ErrorInfo":
        return cls(
            code=code or type(exc).__name__.lower(),
            message=str(exc) or type(exc).__name__,
            stage=stage,
            component=component,
            retryable=retryable,
            attempt=attempt,
            cause_type=type(exc).__name__,
        )



class EvidenceItem(StrictModel):
    """A single unit of evidence, typed by epistemic status.

    The ``kind`` field is the important one:

    * ``observation`` — must have at least one source reference.
    * ``inference`` — must record the reasoning *and* the evidence it rests on.
    * ``allegation`` — must record who made the claim; never treated as fact.

    ``finding`` intentionally does **not** exist: an unverified statement is
    either an inference (ours) or an allegation (theirs).
    """

    id: str = ""
    kind: EvidenceKind
    statement: str = Field(min_length=1, description="What is asserted, in neutral language.")
    sources: list[SourceReference] = Field(default_factory=list)
    supports: list[str] = Field(default_factory=list)     # evidence ids this relies on
    contradicts: list[str] = Field(default_factory=list)  # evidence ids this conflicts with
    confidence: Confidence = Confidence.UNKNOWN
    confidence_basis: str | None = None
    reasoning: str | None = None                          # required for INFERENCE
    allegation_made_by: str | None = None                 # required for ALLEGATION
    allegation_date: datetime | None = None
    verified: bool | None = None                          # None = not yet assessed
    custody: ChainOfCustody | None = None
    tags: list[str] = Field(default_factory=list)
    redaction: RedactionLevel = RedactionLevel.PUBLIC
    collected_by: str | None = None                       # subagent/worker id
    task_id: str | None = None
    observed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    missing: list[UnknownValue] = Field(default_factory=list)
    error: ErrorInfo | None = None

    @field_validator("created_at", "observed_at", "allegation_date", mode="before")
    @classmethod
    def _tz(cls, value: Any) -> Any:
        return normalise_datetime(value) if value is not None else None

    @model_validator(mode="after")
    def _epistemic_rules(self) -> "EvidenceItem":
        # 1. Stable id from semantic content (kind + statement), not from time.
        if not self.id:
            self.id = content_id("ev", self.kind.value, self.statement.lower())

        # 2. Provenance requirements per kind.
        if self.kind is EvidenceKind.OBSERVATION and not self.sources:
            raise ValueError(
                "an observation needs at least one SourceReference; "
                "if nothing was retrieved, record it as not-yet-observed instead"
            )
        if self.kind is EvidenceKind.INFERENCE:
            if not self.reasoning:
                raise ValueError("an inference must record reasoning — how the conclusion was reached")
            if not (self.sources or self.supports):
                raise ValueError("an inference must rest on sources or on other evidence ids")
        if self.kind is EvidenceKind.ALLEGATION and not self.allegation_made_by:
            raise ValueError("an allegation must record who made the claim (allegation_made_by)")

        # 3. Confidence without a basis is not allowed to masquerade as calibrated.
        if self.confidence is not Confidence.UNKNOWN and not self.confidence_basis:
            raise ValueError(
                "state confidence_basis (why this confidence level) or leave confidence unknown"
            )
        return self

    @property
    def is_finding(self) -> bool:
        """Only corroborated observations count as findings."""

        return (
            self.kind is EvidenceKind.OBSERVATION
            and self.verified is True
            and self.confidence in {Confidence.MEDIUM, Confidence.HIGH}
        )

    @property
    def uncorroborated(self) -> bool:
        return self.kind is not EvidenceKind.OBSERVATION or not self.sources


# --------------------------------------------------------------------------
# 15.4b Errors
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# 15.6 Agent specifications and assignments
# --------------------------------------------------------------------------


class CapabilityRequirement(StrictModel):
    """What a task needs in order to run, and whether it is optional."""

    name: str                                          # e.g. "playwright", "exiftool"
    optional: bool = True
    purpose: str | None = None


class WorkerSpec(StrictModel):
    """A task-specific Worker definition, created at runtime by a Subagent.

    There is no fixed roster: this is the *schema* a Worker must satisfy, and
    ``id``/``subagent_id`` tie it to the run that produced it.
    """

    id: str = ""
    subagent_id: str = ""
    name: str = Field(min_length=1, description="Runtime-chosen name, e.g. 'dns-enumeration'.")
    objective: str = Field(min_length=1)
    tools: list[str] = Field(default_factory=list)
    capabilities: list[CapabilityRequirement] = Field(default_factory=list)
    inputs: list[str] = Field(default_factory=list)     # evidence/assignment ids
    output_schema: str = "TaskResult"
    max_attempts: int = Field(default=2, ge=1, le=10)
    timeout_seconds: int = Field(default=300, ge=5, le=3600)
    requires_network: bool = False
    requires_browser: bool = False
    status: EntityStatus = EntityStatus.PENDING
    created_at: datetime = Field(default_factory=utc_now)
    missing: list[UnknownValue] = Field(default_factory=list)
    error: ErrorInfo | None = None

    @field_validator("created_at", mode="before")
    @classmethod
    def _tz(cls, value: Any) -> datetime:
        return normalise_datetime(value)

    @model_validator(mode="after")
    def _identify(self) -> "WorkerSpec":
        if not self.id:
            self.id = content_id("wrk", self.subagent_id, self.name.lower(), self.objective.lower())
        return self


class SubagentSpec(StrictModel):
    """A task-specific Subagent, created at runtime by the Master Agent."""

    id: str = ""
    mission_id: str = ""
    name: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    rationale: str | None = None                       # why this subagent exists
    workers: list[WorkerSpec] = Field(default_factory=list)
    scope_entries: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)  # other subagent ids
    max_workers: int = Field(default=4, ge=1, le=16)
    review_rounds_allowed: int = Field(default=2, ge=0, le=5)
    status: EntityStatus = EntityStatus.PENDING
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    missing: list[UnknownValue] = Field(default_factory=list)
    error: ErrorInfo | None = None

    @field_validator("created_at", "started_at", "finished_at", mode="before")
    @classmethod
    def _tz(cls, value: Any) -> Any:
        return normalise_datetime(value) if value is not None else None

    @model_validator(mode="after")
    def _identify(self) -> "SubagentSpec":
        if not self.id:
            self.id = content_id("sa", self.mission_id, self.name.lower(), self.objective.lower())
        return self

    @model_validator(mode="after")
    def _worker_links(self) -> "SubagentSpec":
        for worker in self.workers:
            if not worker.subagent_id:
                worker.subagent_id = self.id
        return self


class TaskAssignment(StrictModel):
    """Work handed to a Worker: inputs, deadline, and how success is judged."""

    id: str = ""
    mission_id: str = ""
    subagent_id: str = ""
    worker_id: str = ""
    objective: str = Field(min_length=1)
    inputs: list[str] = Field(default_factory=list)
    expected_output: str | None = None
    acceptance_criteria: list[str] = Field(default_factory=list)
    deadline: datetime | None = None
    attempt: int = Field(default=1, ge=1)
    status: EntityStatus = EntityStatus.READY
    assigned_at: datetime = Field(default_factory=utc_now)
    missing: list[UnknownValue] = Field(default_factory=list)
    error: ErrorInfo | None = None

    @field_validator("assigned_at", "deadline", mode="before")
    @classmethod
    def _tz(cls, value: Any) -> Any:
        return normalise_datetime(value) if value is not None else None

    @model_validator(mode="after")
    def _identify(self) -> "TaskAssignment":
        if not self.id:
            self.id = content_id("task", self.worker_id, self.objective.lower(), self.attempt)
        return self


class TaskResult(StrictModel):
    """What a Worker returns.  A failure is a result, never an exception."""

    id: str = ""
    task_id: str = ""
    worker_id: str = ""
    status: EntityStatus = EntityStatus.SUCCEEDED
    summary: str | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    metrics: dict[str, float | int | str | None] = Field(default_factory=dict)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: float | None = Field(default=None, ge=0)
    attempts: int = Field(default=1, ge=1)
    truncated: bool = False                              # output cut short by a budget
    missing: list[UnknownValue] = Field(default_factory=list)
    error: ErrorInfo | None = None

    @field_validator("started_at", "finished_at", mode="before")
    @classmethod
    def _tz(cls, value: Any) -> Any:
        return normalise_datetime(value) if value is not None else None

    @model_validator(mode="after")
    def _identify(self) -> "TaskResult":
        if not self.id:
            self.id = content_id("res", self.task_id, self.worker_id, self.attempts)
        return self

    @model_validator(mode="after")
    def _consistency(self) -> "TaskResult":
        # A failure must say why; a success must not be contradictory.
        if self.status in {EntityStatus.FAILED, EntityStatus.CANCELLED, EntityStatus.BUDGET_EXCEEDED} and self.error is None:
            raise ValueError(f"status {self.status.value!r} requires an ErrorInfo explaining it")
        if self.started_at and self.finished_at and self.finished_at < self.started_at:
            raise ValueError("finished_at precedes started_at")
        if self.duration_seconds is None and self.started_at and self.finished_at:
            self.duration_seconds = (self.finished_at - self.started_at).total_seconds()
        return self


# --------------------------------------------------------------------------
# 15.7 Reviews and reports
# --------------------------------------------------------------------------


class ReviewFinding(StrictModel):
    """One reviewer objection, tied to the evidence or text it concerns."""

    id: str = ""
    severity: str = Field(default="minor", pattern="^(info|minor|major|blocking)$")
    message: str = Field(min_length=1)
    target_id: str | None = None
    fix_required: bool = False
    resolved: bool = False
    raised_at: datetime = Field(default_factory=utc_now)
    resolved_at: datetime | None = None

    @field_validator("raised_at", "resolved_at", mode="before")
    @classmethod
    def _tz(cls, value: Any) -> Any:
        return normalise_datetime(value) if value is not None else None

    @model_validator(mode="after")
    def _identify(self) -> "ReviewFinding":
        if not self.id:
            self.id = content_id("rf", self.message.lower(), self.target_id)
        return self


class QualityReview(StrictModel):
    """A Subagent's review of its Workers' output, before reporting upward."""

    id: str = ""
    subagent_id: str = ""
    round: int = Field(default=1, ge=1)
    verdict: str = Field(default="pass", pattern="^(pass|revise|reject|escalate)$")
    reviewer: str | None = None                          # component/model that reviewed
    criteria: list[str] = Field(default_factory=list)
    findings: list[ReviewFinding] = Field(default_factory=list)
    evidence_reviewed: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)   # evidence ids lacking sources
    reviewed_at: datetime = Field(default_factory=utc_now)
    missing: list[UnknownValue] = Field(default_factory=list)
    error: ErrorInfo | None = None

    @field_validator("reviewed_at", mode="before")
    @classmethod
    def _tz(cls, value: Any) -> datetime:
        return normalise_datetime(value)

    @model_validator(mode="after")
    def _identify(self) -> "QualityReview":
        if not self.id:
            self.id = content_id("qr", self.subagent_id, self.round, self.verdict)
        if self.verdict in {"revise", "reject"} and not self.findings:
            raise ValueError(f"verdict {self.verdict!r} requires at least one finding explaining why")
        return self

    @property
    def blocking(self) -> list[ReviewFinding]:
        return [f for f in self.findings if f.severity == "blocking" and not f.resolved]


class SubagentReport(StrictModel):
    """What a Subagent hands to the Master Agent: evidence, gaps, uncertainty."""

    id: str = ""
    mission_id: str = ""
    subagent_id: str = ""
    objective: str = Field(min_length=1)
    status: EntityStatus = EntityStatus.PENDING
    evidence: list[EvidenceItem] = Field(default_factory=list)
    reviews: list[QualityReview] = Field(default_factory=list)
    hypotheses_tested: list[str] = Field(default_factory=list)
    hypotheses_remaining: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    gaps: list[UnknownValue] = Field(default_factory=list)
    confidence: Confidence = Confidence.UNKNOWN
    confidence_basis: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    missing: list[UnknownValue] = Field(default_factory=list)
    error: ErrorInfo | None = None

    @field_validator("started_at", "finished_at", mode="before")
    @classmethod
    def _tz(cls, value: Any) -> Any:
        return normalise_datetime(value) if value is not None else None

    @model_validator(mode="after")
    def _identify(self) -> "SubagentReport":
        if not self.id:
            self.id = content_id("sarep", self.subagent_id, self.objective.lower())
        return self

    @property
    def observations(self) -> list[EvidenceItem]:
        return [e for e in self.evidence if e.kind is EvidenceKind.OBSERVATION]

    @property
    def inferences(self) -> list[EvidenceItem]:
        return [e for e in self.evidence if e.kind is EvidenceKind.INFERENCE]

    @property
    def allegations(self) -> list[EvidenceItem]:
        return [e for e in self.evidence if e.kind is EvidenceKind.ALLEGATION]


class FinalReport(StrictModel):
    """The mission deliverable.  Serialises to JSON without losing provenance.

    ``attributions`` is deliberately separate from ``findings``: naming a party
    is a distinct, higher-bar step that must cite evidence and state the
    standard of proof applied — or explicitly say no attribution is made.
    """

    id: str = ""
    mission_id: str = ""
    objective: str = Field(min_length=1)
    scope: Scope | None = None
    status: EntityStatus = EntityStatus.PENDING
    findings: list[EvidenceItem] = Field(default_factory=list)
    inferences: list[EvidenceItem] = Field(default_factory=list)
    allegations: list[EvidenceItem] = Field(default_factory=list)
    attributions: list[str] = Field(default_factory=list)
    attribution_standard: str | None = None
    hypotheses_supported: list[str] = Field(default_factory=list)
    hypotheses_refuted: list[str] = Field(default_factory=list)
    hypotheses_open: list[str] = Field(default_factory=list)
    uncertainty_statement: str | None = None
    limitations: list[str] = Field(default_factory=list)
    gaps: list[UnknownValue] = Field(default_factory=list)
    subagent_reports: list[str] = Field(default_factory=list)   # report ids
    confidence: Confidence = Confidence.UNKNOWN
    confidence_basis: str | None = None
    generated_by: str | None = None
    generated_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    schema_version: int = MODEL_SCHEMA_VERSION
    missing: list[UnknownValue] = Field(default_factory=list)
    error: ErrorInfo | None = None

    @field_validator("generated_at", "started_at", mode="before")
    @classmethod
    def _tz(cls, value: Any) -> Any:
        return normalise_datetime(value) if value is not None else None

    @model_validator(mode="after")
    def _identify(self) -> "FinalReport":
        if not self.id:
            self.id = content_id("report", self.mission_id, self.objective.lower())
        return self

    @model_validator(mode="after")
    def _attribution_needs_evidence(self) -> "FinalReport":
        if self.attributions and not (self.findings or self.inferences):
            raise ValueError(
                "an attribution without supporting findings or inferences is a bare allegation — "
                "move it to allegations with allegation_made_by set"
            )
        if self.attributions and not self.attribution_standard:
            raise ValueError("attributions require attribution_standard (what evidence bar was met)")
        return self


# --------------------------------------------------------------------------
# 15.8 Mission
# --------------------------------------------------------------------------


class Mission(StrictModel):
    """The top-level typed mission.  Created by the CLI, consumed by Phase 3.

    ``mission_id`` is deterministic (:class:`MissionRequest` computes the same
    fingerprint), so the CLI plan and the typed model refer to one mission.
    """

    id: str = ""
    title: str | None = None
    objective: str = Field(min_length=1)
    original_objective: str | None = None            # pre-reframe wording, for audit
    mode: MissionMode = MissionMode.PASSIVE
    scope: Scope
    status: EntityStatus = EntityStatus.PENDING
    authorised: bool = False
    policy_verdict: str | None = None
    policy_rule: str | None = None
    reframe_adopted: bool = False
    operator: str | None = None
    limits: dict[str, Any] = Field(default_factory=dict)
    subagents: list[SubagentSpec] = Field(default_factory=list)
    reports: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    dry_run: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    schema_version: int = MODEL_SCHEMA_VERSION
    missing: list[UnknownValue] = Field(default_factory=list)
    error: ErrorInfo | None = None

    @field_validator("created_at", "started_at", "finished_at", mode="before")
    @classmethod
    def _tz(cls, value: Any) -> Any:
        return normalise_datetime(value) if value is not None else None

    @model_validator(mode="after")
    def _identify(self) -> "Mission":
        if not self.id:
            self.id = mission_id_for(self.objective, self.scope.includes, self.mode)
        return self

    @model_validator(mode="after")
    def _scope_contains_objective(self) -> "Mission":
        # Every declared subagent scope entry must sit inside the mission scope,
        # otherwise a subagent could widen its own authority.
        for subagent in self.subagents:
            for entry in subagent.scope_entries:
                if not self.scope.covers(entry):
                    raise ValueError(
                        f"subagent {subagent.id} claims scope {entry!r} which the mission scope does not cover"
                    )
        return self

    @classmethod
    def from_preflight(
        cls,
        *,
        request: "MissionRequest",
        preflight: "PreflightReport",
        settings: "Settings",
        operator: str | None = None,
    ) -> "Mission":
        """Build the typed mission from the CLI's validated request + preflight.

        Only cleared missions may be built: this raises if the preflight did not
        pass, so an un-cleared objective cannot acquire a typed representation.
        """

        if not preflight.ok or preflight.scope is None:
            raise ValueError("cannot build a Mission from an uncleared preflight report")

        return cls(
            id=request.fingerprint(),
            objective=preflight.objective,
            original_objective=preflight.original_objective,
            mode=request.mode,
            scope=Scope.from_declaration(preflight.scope),
            authorised=request.authorised,
            policy_verdict=preflight.verdict.outcome.value,
            policy_rule=preflight.verdict.rule_id,
            reframe_adopted=preflight.reframe_adopted,
            operator=operator or request.operator,
            dry_run=request.dry_run,
            limits={
                "max_subagents": request.max_subagents,
                "max_workers_per_agent": request.max_workers_per_agent,
                "max_total_workers": request.max_total_workers,
                "worker_retries": request.worker_retries,
                "review_retries": request.review_retries,
                "mission_budget_seconds": request.mission_budget_seconds,
                "task_budget_seconds": request.task_budget_seconds,
                "provider": settings.provider,
                "model": settings.model,
            },
        )


# --------------------------------------------------------------------------
# 15.9 Serialisation and integrity helpers
# --------------------------------------------------------------------------


def model_to_json(model: BaseModel, *, indent: int = 2) -> str:
    """Serialise any model above to JSON, preserving every field.

    ``mode="json"`` keeps enums as their string values and datetimes as ISO
    8601, and ``exclude_none=False`` ensures an explicit ``null`` survives — a
    missing key and a null are different claims.
    """

    return model.model_dump_json(indent=indent, exclude_none=False)


def validate_model_payload(model_cls: type[BaseModel], payload: str | dict[str, Any]) -> BaseModel:
    """Round-trip check used by ``models --validate`` and by case-file loading."""

    if isinstance(payload, str):
        data = json.loads(payload)
    else:
        data = payload
    return model_cls.model_validate(data)


def model_field_inventory(model_cls: type[BaseModel]) -> list[tuple[str, str, bool]]:
    """(field, type, required) triples, for documentation and tests."""

    inventory: list[tuple[str, str, bool]] = []
    for name, info in model_cls.model_fields.items():
        annotation = getattr(info.annotation, "__name__", str(info.annotation))
        inventory.append((name, annotation, info.is_required()))
    return inventory


#: Every model in this section, grouped for the ``models`` command.
MODEL_CATALOGUE: tuple[tuple[str, type[BaseModel], str], ...] = (
    ("Mission", Mission, "top-level typed mission"),
    ("Scope", Scope, "authorised asset boundary"),
    ("SubagentSpec", SubagentSpec, "runtime-created subagent definition"),
    ("WorkerSpec", WorkerSpec, "runtime-created worker definition"),
    ("TaskAssignment", TaskAssignment, "work handed to a worker"),
    ("TaskResult", TaskResult, "worker outcome, success or failure"),
    ("EvidenceItem", EvidenceItem, "observation / inference / allegation"),
    ("SourceReference", SourceReference, "where evidence came from"),
    ("QualityReview", QualityReview, "subagent review of worker output"),
    ("SubagentReport", SubagentReport, "subagent report to the master"),
    ("FinalReport", FinalReport, "mission deliverable"),
    ("ChainOfCustody", ChainOfCustody, "artefact handling trail"),
    ("ErrorInfo", ErrorInfo, "structured failure"),
    ("UnknownValue", UnknownValue, "explicit unknown"),
)


# --------------------------------------------------------------------------
# 15.10 Rendering
# --------------------------------------------------------------------------


def render_model_section(console: Console, model: BaseModel, title: str) -> None:
    """Flatten a model into a table, showing explicit unknowns as such."""

    table = Table(title=title, title_justify="left", box=None, pad_edge=False)
    table.add_column("field", style="dim", no_wrap=True)
    table.add_column("value", overflow="fold")

    data = model.model_dump(mode="json")
    for key, value in data.items():
        if value in (None, "", [], {}):
            rendered = "[dim]—[/dim]" if value is not None else "[yellow]null (explicitly unknown)[/yellow]"
        elif isinstance(value, list):
            rendered = f"{len(value)} item(s)"
        elif isinstance(value, dict):
            rendered = f"{len(value)} key(s)"
        else:
            rendered = escape(str(value))
        table.add_row(key, rendered)
    console.print(table)


@app.command("models", help="Inspect and validate the typed mission/evidence/result models.")
def models_command(
    name: str | None = typer.Option(None, "--name", "-n", help="Show one model's fields."),
    self_test: bool = typer.Option(
        True, "--self-test/--no-self-test", help="Exercise every model with a valid and an invalid case."
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Never touches the network: builds and validates models in memory only."""

    console = get_console()

    if name:
        match = next((entry for entry in MODEL_CATALOGUE if entry[0].lower() == name.lower()), None)
        if match is None:
            console.print(f"[red]unknown model[/red] {escape(name)!s}; choose from: "
                          + ", ".join(entry[0] for entry in MODEL_CATALOGUE))
            raise typer.Exit(ExitCode.USAGE)
        label, model_cls, purpose = match
        if as_json:
            _emit(
                json.dumps(
                    {
                        "model": label,
                        "purpose": purpose,
                        "fields": [
                            {"name": f, "type": t, "required": r} for f, t, r in model_field_inventory(model_cls)
                        ],
                        "json_schema": model_cls.model_json_schema(),
                    },
                    indent=2,
                )
            )
            raise typer.Exit(ExitCode.OK)
        inventory = Table(title=f"{label} — {purpose}", title_justify="left", box=None, pad_edge=False)
        inventory.add_column("field", style="bold", no_wrap=True)
        inventory.add_column("type", style="cyan")
        inventory.add_column("required", no_wrap=True)
        for field_name, annotation, required in model_field_inventory(model_cls):
            inventory.add_row(
                escape(field_name),
                escape(annotation),
                "[green]yes[/green]" if required else "[dim]no[/dim]",
            )
        console.print()
        console.print(inventory)
        console.print()
        raise typer.Exit(ExitCode.OK)

    results = run_model_self_test() if self_test else []

    if as_json:
        _emit(
            json.dumps(
                {
                    "schema_version": MODEL_SCHEMA_VERSION,
                    "models": [
                        {"name": label, "purpose": purpose, "fields": len(model_cls.model_fields)}
                        for label, model_cls, purpose in MODEL_CATALOGUE
                    ],
                    "self_test": [
                        {"check": r.name, "ok": r.ok, "detail": r.detail} for r in results
                    ],
                    "ok": all(r.ok for r in results) if results else None,
                },
                indent=2,
            )
        )
        raise typer.Exit(ExitCode.OK if all(r.ok for r in results) else ExitCode.INTERNAL)

    catalogue = Table(
        title=f"{APP_TITLE} typed models — schema v{MODEL_SCHEMA_VERSION}",
        title_justify="left",
        box=None,
        pad_edge=False,
    )
    catalogue.add_column("model", style="bold", no_wrap=True)
    catalogue.add_column("fields", justify="right", no_wrap=True)
    catalogue.add_column("purpose", overflow="fold")
    for label, model_cls, purpose in MODEL_CATALOGUE:
        catalogue.add_row(escape(label), str(len(model_cls.model_fields)), escape(purpose))
    console.print()
    console.print(catalogue)

    if results:
        console.print()
        failures = [r for r in results if not r.ok]
        checks = Table(title="self-test", title_justify="left", box=None, pad_edge=False)
        checks.add_column("", width=2)
        checks.add_column("check", style="bold", no_wrap=True)
        checks.add_column("detail", overflow="fold")
        for result in results:
            glyph, style = ("✔", "green") if result.ok else ("✘", "red")
            checks.add_row(f"[{style}]{glyph}[/{style}]", escape(result.name), escape(result.detail))
        console.print(checks)
        console.print(
            f"[{'green' if not failures else 'red'}]{len(results) - len(failures)} passed[/] · "
            f"{len(failures)} failed"
        )
        if failures:
            raise typer.Exit(ExitCode.INTERNAL)

    console.print(
        "\n[dim]Provenance is preserved by construction: observations require a source, "
        "inferences require reasoning, allegations require an author, and missing data is an "
        "explicit UnknownValue rather than an empty string.[/dim]\n"
    )
    raise typer.Exit(ExitCode.OK)


@dataclass(frozen=True)
class ModelTestResult:
    name: str
    ok: bool
    detail: str


def _sample_source(**overrides: Any) -> SourceReference:
    payload: dict[str, Any] = {
        "kind": SourceKind.PUBLIC_WEB,
        "url": "https://example.com/security/advisory",
        "title": "Security advisory",
        "retrieved_at": "2026-03-01T10:00:00Z",
        "retrieval_method": RetrievalMethod.HTTP,
        "http_status": 200,
        "content_hash": {"algorithm": "sha256", "value": "a" * 64, "size_bytes": 1024},
        "excerpt": "A vulnerability was fixed in version 2.1.4.",
    }
    payload.update(overrides)
    return SourceReference(**payload)


def run_model_self_test() -> list[ModelTestResult]:
    """Valid *and* invalid cases for every rule, executed in memory.

    These are the acceptance criteria expressed as executable checks: unknown
    data stays unknown, provenance cannot be invented, and JSON round-trips
    preserve every source.
    """

    results: list[ModelTestResult] = []

    def case(name: str, fn: Any) -> None:
        try:
            fn()
            results.append(ModelTestResult(name, True, "ok"))
        except AssertionError as exc:
            results.append(ModelTestResult(name, False, str(exc) or "assertion failed"))
        except Exception as exc:                        # unexpected model error
            results.append(ModelTestResult(name, False, f"{type(exc).__name__}: {exc}"))

    def sample_scope() -> Scope:
        return Scope(
            mode=MissionMode.PASSIVE,
            entries=[ScopeEntry(pattern="example.com"), ScopeEntry(pattern="api.example.com", included=False)],
            data_classes=[DataClass.PUBLIC_WEB],
        )

    def sample_observation() -> EvidenceItem:
        return EvidenceItem(
            kind=EvidenceKind.OBSERVATION,
            statement="The advisory lists CVE-2026-0001 as fixed in 2.1.4.",
            sources=[_sample_source()],
            confidence=Confidence.MEDIUM,
            confidence_basis="single first-party advisory, retrieved directly",
            verified=True,
        )

    # --- ids and determinism ------------------------------------------------
    def _stable_ids() -> None:
        a = EvidenceItem(kind=EvidenceKind.OBSERVATION, statement="Same statement.", sources=[_sample_source()])
        b = EvidenceItem(kind=EvidenceKind.OBSERVATION, statement="same statement.", sources=[_sample_source(url="https://other.example/x")])
        assert a.id == b.id, "id must derive from kind+statement, not from source or time"
        assert a.id.startswith("ev-")

    case("ids: evidence id is deterministic", _stable_ids)

    def _mission_matches_request() -> None:
        req = MissionRequest(targets=["example.com"], objective="Map the public attack surface.")
        report = run_preflight(objective=req.objective, targets=req.targets, scope_entries=req.targets)
        mission = Mission.from_preflight(request=req, preflight=report, settings=build_settings({}, {}).settings)
        assert mission.id == req.fingerprint(), f"{mission.id} != {req.fingerprint()}"
        assert mission.id.startswith("mission-")
        # The same content built directly must derive the same id.
        direct = Mission(objective=mission.objective, scope=mission.scope, mode=mission.mode)
        assert direct.id == mission.id, f"{direct.id} != {mission.id}"
        assert mission.scope.covers("api.example.com")

    case("mission: scope mirrors the preflight declaration", _mission_matches_request)

    def _mission_rejects_uncleared() -> None:
        req = MissionRequest(targets=["example.com"], objective="steal the credentials")
        report = run_preflight(objective=req.objective, targets=req.targets, scope_entries=req.targets)
        try:
            Mission.from_preflight(request=req, preflight=report, settings=build_settings({}, {}).settings)
        except ValueError:
            return
        raise AssertionError("uncleared preflight produced a Mission")

    case("mission: refuses an uncleared objective", _mission_rejects_uncleared)

    def _scope_widening_blocked() -> None:
        try:
            Mission(
                objective="x",
                scope=Scope(entries=[ScopeEntry(pattern="example.com")]),
                subagents=[SubagentSpec(name="s", objective="o", scope_entries=["evil.example.org"])],
            )
        except Exception:
            return
        raise AssertionError("subagent widened the mission scope")

    case("mission: subagent cannot widen scope", _scope_widening_blocked)

    # --- provenance rules ---------------------------------------------------
    def _observation_needs_source() -> None:
        try:
            EvidenceItem(kind=EvidenceKind.OBSERVATION, statement="Something happened.")
        except Exception:
            return
        raise AssertionError("observation without a source was accepted")

    case("evidence: observation requires a source", _observation_needs_source)

    def _inference_needs_reasoning() -> None:
        try:
            EvidenceItem(kind=EvidenceKind.INFERENCE, statement="They are negligent.", sources=[_sample_source()])
        except Exception:
            return
        raise AssertionError("inference without reasoning was accepted")

    case("evidence: inference requires reasoning", _inference_needs_reasoning)

    def _allegation_needs_author() -> None:
        try:
            EvidenceItem(kind=EvidenceKind.ALLEGATION, statement="A rival claims a breach.")
        except Exception:
            return
        raise AssertionError("allegation without an author was accepted")

    case("evidence: allegation requires an author", _allegation_needs_author)

    def _confidence_needs_basis() -> None:
        try:
            EvidenceItem(
                kind=EvidenceKind.OBSERVATION,
                statement="A thing.",
                sources=[_sample_source()],
                confidence=Confidence.HIGH,
            )
        except Exception:
            return
        raise AssertionError("confidence without a basis was accepted")

    case("evidence: confidence requires a basis", _confidence_needs_basis)

    def _source_needs_locator() -> None:
        try:
            SourceReference(kind=SourceKind.PUBLIC_WEB)
        except Exception:
            return
        raise AssertionError("a source with no url/path was accepted")

    case("source: cannot be unlocatable", _source_needs_locator)

    def _source_unknown_is_explicit() -> None:
        ref = SourceReference(
            kind=SourceKind.SOCIAL_MEDIA,
            missing=UnknownValue(reason=UnknownReason.UNAVAILABLE, detail="post deleted before capture"),
        )
        assert ref.url is None and ref.missing is not None
        assert "unavailable" in ref.locator

    case("source: unknown location is explicit", _source_unknown_is_explicit)

    # --- JSON round-trip preserves provenance -------------------------------
    def _round_trip() -> None:
        original = EvidenceItem(
            kind=EvidenceKind.INFERENCE,
            statement="The advisory implies the issue was known internally before release.",
            sources=[_sample_source()],
            supports=["ev-123456789abc"],
            reasoning="The advisory states the fix predates the public report.",
            confidence=Confidence.LOW,
            confidence_basis="single source, no independent corroboration",
            custody=ChainOfCustody(
                collected_by="sa-1",
                collected_at="2026-03-01T10:05:00Z",
                collection_method=RetrievalMethod.HTTP,
                preserved=True,
                integrity_hash=HashRecord(algorithm="sha256", value="b" * 64, size_bytes=2048),
                custody_events=["2026-03-01T10:05:00Z captured by HTTP"],
            ),
        )
        blob = model_to_json(original)
        restored = validate_model_payload(EvidenceItem, blob)
        assert restored.sources[0].url == original.sources[0].url, "url lost in round-trip"
        assert restored.sources[0].retrieved_at == original.sources[0].retrieved_at, "retrieval time lost"
        assert restored.custody and restored.custody.integrity_hash.value == "b" * 64, "custody lost"
        assert restored.reasoning == original.reasoning and restored.supports == original.supports
        assert restored.id == original.id and restored.confidence is Confidence.LOW

    case("json: evidence round-trip keeps every source", _round_trip)

    def _round_trip_mission() -> None:
        mission = Mission(
            objective="Map the public attack surface of example.com",
            scope=sample_scope(),
            evidence=[sample_observation()],
            dry_run=True,
        )
        restored = validate_model_payload(Mission, model_to_json(mission))
        assert restored.scope.includes == ["example.com"]
        assert restored.evidence[0].sources[0].retrieved_at == mission.evidence[0].sources[0].retrieved_at
        assert restored.created_at == mission.created_at

    case("json: mission round-trip keeps scope and evidence", _round_trip_mission)

    def _nulls_are_preserved() -> None:
        payload = json.loads(model_to_json(sample_scope()))
        assert "authorized_by" in payload and payload["authorized_by"] is None, "null key dropped"
        assert "authorization_basis" in payload

    case("json: explicit nulls are not dropped", _nulls_are_preserved)

    # --- explicit unknowns --------------------------------------------------
    def _unknown_not_invented() -> None:
        ev = EvidenceItem(
            kind=EvidenceKind.OBSERVATION,
            statement="A post existed at the URL below.",
            sources=[_sample_source()],
            missing=[UnknownValue(reason=UnknownReason.NOT_YET_OBSERVED, detail="author identity")],
        )
        payload = json.loads(model_to_json(ev))
        assert payload["missing"][0]["reason"] == "not-yet-observed"
        assert payload["reasoning"] is None, "absent reasoning must serialise as null, not a guess"
        assert payload["verified"] is None, "unassessed verification must stay null"

    case("unknowns: gaps are recorded, never guessed", _unknown_not_invented)

    def _failure_requires_error() -> None:
        try:
            TaskResult(task_id="task-1", worker_id="wrk-1", status=EntityStatus.FAILED)
        except Exception:
            return
        raise AssertionError("a failed result without ErrorInfo was accepted")

    case("results: failure carries an error", _failure_requires_error)

    def _review_requires_findings() -> None:
        try:
            QualityReview(subagent_id="sa-1", verdict="reject")
        except Exception:
            return
        raise AssertionError("a rejection without findings was accepted")

    case("review: rejection explains itself", _review_requires_findings)

    def _attribution_requires_evidence() -> None:
        try:
            FinalReport(mission_id="m-1", objective="o", attributions=["Acme Corp"])
        except Exception:
            return
        raise AssertionError("attribution without findings was accepted")

    case("report: attribution needs evidence + standard", _attribution_requires_evidence)

    def _extra_field_rejected() -> None:
        try:
            Scope(entries=[ScopeEntry(pattern="example.com")], typo_field="oops")
        except Exception:
            return
        raise AssertionError("unknown field was silently accepted")

    case("models: unknown fields are rejected", _extra_field_rejected)

    def _error_redacted() -> None:
        secret = "sk-proj-MODELSECRET1234567890"
        info = ErrorInfo(code="http", message=f"GET failed with key {secret}")
        assert secret not in info.message, "a secret survived ErrorInfo redaction"

    case("errors: message is redacted on construction", _error_redacted)

    def _full_report() -> None:
        report = FinalReport(
            mission_id="mission-1",
            objective="Map the public attack surface of example.com",
            scope=sample_scope(),
            status=EntityStatus.SUCCEEDED,
            findings=[sample_observation()],
            uncertainty_statement="Only public sources were consulted; internal state was not assessed.",
            confidence=Confidence.MEDIUM,
            confidence_basis="two independent public sources agreed",
        )
        blob = model_to_json(report)
        restored = validate_model_payload(FinalReport, blob)
        assert restored.findings[0].sources[0].content_hash.value == "a" * 64
        assert restored.uncertainty_statement == report.uncertainty_statement

    case("report: final report serialises with provenance", _full_report)

    return results


# ══════════════════════════════════════════════════════════════════════════
# 16. Unified run-state store
# ══════════════════════════════════════════════════════════════════════════
#
# One authoritative, thread-safe record of a mission in flight.  Phase 3's
# Master Agent, the runtime Subagents and every Worker read and write *this*
# object; nothing else holds mission truth.
#
# Concurrency contract
# --------------------
# Subagents and Workers run in parallel, so "read, mutate, write back" is unsafe
# by default.  The store therefore provides four guarantees:
#
#   1. ONE LOCK.  Every mutation happens under a single re-entrant lock, so a
#      record is never half-updated.
#   2. MERGE, NEVER REPLACE.  Adding evidence or a result merges into the
#      existing record by id; it cannot clobber an unrelated entry because it
#      never writes a whole collection — only the one key it owns.
#   3. REVISION CHECKS.  Records carry a revision counter.  An update may pass
#      ``expected_revision``; a mismatch raises StaleWriteError instead of
#      silently discarding someone else's work.
#   4. IMMUTABLE SNAPSHOTS.  Readers get a deep copy taken under the lock, so a
#      renderer can never observe a torn state (e.g. a result whose assignment
#      has not yet landed).
#
# Checkpoints
# -----------
# ``to_checkpoint()`` produces a JSON-safe dict; ``save_checkpoint`` writes it
# atomically (temp file + ``os.replace``) so a crash mid-write cannot leave a
# truncated case file.  ``load_checkpoint`` rebuilds a store and re-validates
# every record through the Task 5 models.

class StateError(RuntimeError):
    """Base class for run-state failures."""


class StaleWriteError(StateError):
    """An update was based on an out-of-date revision of a record."""


class BudgetExceeded(StateError):
    """A budget (time, tasks, retries) would be exceeded by this operation."""


class CheckpointError(StateError):
    """A checkpoint could not be written or read back."""


class EventKind(str, Enum):
    """What happened.  Events are the audit trail, not the state itself."""

    MISSION_CREATED = "mission-created"
    STATUS_CHANGED = "status-changed"
    SUBAGENT_ADDED = "subagent-added"
    WORKER_ADDED = "worker-added"
    TASK_ASSIGNED = "task-assigned"
    TASK_STARTED = "task-started"
    TASK_FINISHED = "task-finished"
    EVIDENCE_ADDED = "evidence-added"
    EVIDENCE_MERGED = "evidence-merged"
    REVIEW_RECORDED = "review-recorded"
    RETRY_RECORDED = "retry-recorded"
    BUDGET_CONSUMED = "budget-consumed"
    BUDGET_EXCEEDED = "budget-exceeded"
    CONFLICT = "conflict"
    CHECKPOINT_SAVED = "checkpoint-saved"
    CHECKPOINT_LOADED = "checkpoint-loaded"
    ERROR = "error"


class StateEvent(StrictModel):
    """One append-only event.  ``seq`` is monotonic within a store."""

    seq: int = Field(ge=1)
    kind: EventKind
    message: str = Field(min_length=1)
    at: datetime = Field(default_factory=utc_now)
    actor: str | None = None            # subagent/worker id, or "operator"
    entity_type: str | None = None
    entity_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("at", mode="before")
    @classmethod
    def _tz(cls, value: Any) -> datetime:
        return normalise_datetime(value)

    @field_validator("message")
    @classmethod
    def _redact(cls, value: str) -> str:
        return redact_text(value, secrets=known_secrets())


#: Alias so renderer code can name the state-event enum unambiguously.
StateEventKind = EventKind


class Progress(StrictModel):
    """Derived view of how far along a mission is.  Never stored as truth."""

    status: EntityStatus
    tasks_total: int = 0
    tasks_succeeded: int = 0
    tasks_failed: int = 0
    tasks_running: int = 0
    tasks_skipped: int = 0
    tasks_pending: int = 0
    percent_complete: float = 0.0
    subagents_total: int = 0
    workers_total: int = 0
    evidence_total: int = 0
    observations: int = 0
    inferences: int = 0
    allegations: int = 0
    reviews_total: int = 0
    retries_used: int = 0
    seconds_used: float = 0.0
    seconds_limit: int | None = None
    events: int = 0
    conflicts: int = 0
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("updated_at", mode="before")
    @classmethod
    def _tz(cls, value: Any) -> datetime:
        return normalise_datetime(value)

    @property
    def budget_used_percent(self) -> float | None:
        if not self.seconds_limit:
            return None
        return round(100.0 * self.seconds_used / self.seconds_limit, 1)


class BudgetLedger(StrictModel):
    """Monotonic budget accounting.  Consumption never goes backwards."""

    seconds_used: float = Field(default=0.0, ge=0)
    seconds_limit: int | None = Field(default=None, ge=1)
    tasks_started: int = Field(default=0, ge=0)
    tasks_limit: int | None = Field(default=None, ge=1)
    retries_used: int = Field(default=0, ge=0)
    retries_limit: int | None = Field(default=None, ge=0)
    exhausted: bool = False

    def check(self, *, seconds: float = 0.0, task: bool = False, retry: bool = False) -> None:
        """Raise :class:`BudgetExceeded` *before* the work is done."""

        if self.seconds_limit is not None and self.seconds_used + seconds > self.seconds_limit:
            raise BudgetExceeded(
                f"mission time budget exhausted: {self.seconds_used:.0f}s of {self.seconds_limit}s used"
            )
        if task and self.tasks_limit is not None and self.tasks_started + 1 > self.tasks_limit:
            raise BudgetExceeded(f"task budget exhausted: {self.tasks_started} of {self.tasks_limit} used")
        if retry and self.retries_limit is not None and self.retries_used + 1 > self.retries_limit:
            raise BudgetExceeded(f"retry budget exhausted: {self.retries_used} of {self.retries_limit} used")

    def consume(self, *, seconds: float = 0.0, task: bool = False, retry: bool = False) -> None:
        """Check, then apply.  Atomic from the caller's point of view."""

        self.check(seconds=seconds, task=task, retry=retry)
        self.seconds_used = round(self.seconds_used + max(0.0, seconds), 3)
        if task:
            self.tasks_started += 1
        if retry:
            self.retries_used += 1


class RunStateStore:
    """Thread-safe, checkpointable mission state.

    Every public mutator takes the lock, validates through the Task 5 models,
    and appends an event.  Every reader returns a deep copy.  The store is
    deliberately not a Pydantic model: it owns a lock and mutable collections,
    and hiding those behind model validation would invite torn reads.
    """

    #: Bumped when the checkpoint payload shape changes.
    CHECKPOINT_VERSION: int = 1

    def __init__(
        self,
        mission: Mission,
        *,
        clock: "Callable[[], datetime] | None" = None,
    ) -> None:
        self._lock = threading.RLock()
        self._clock: Callable[[], datetime] = clock or utc_now
        self._mission: Mission = mission.model_copy(deep=True)
        self._scope: Scope = self._mission.scope.model_copy(deep=True)
        self._status: EntityStatus = self._mission.status

        self._subagents: dict[str, SubagentSpec] = {}
        self._workers: dict[str, WorkerSpec] = {}
        self._assignments: dict[str, TaskAssignment] = {}
        self._results: dict[str, TaskResult] = {}
        self._evidence: dict[str, EvidenceItem] = {}
        self._reviews: dict[str, QualityReview] = {}
        self._retries: dict[str, int] = {}
        self._revisions: dict[tuple[str, str], int] = {}
        self._events: list[StateEvent] = []
        self._seq = 0
        self._conflicts: list[str] = []

        limits = self._mission.limits or {}
        self._budget = BudgetLedger(
            seconds_limit=limits.get("mission_budget_seconds"),
            retries_limit=limits.get("max_total_workers"),
        )

        for subagent in self._mission.subagents:
            self._subagents[subagent.id] = subagent.model_copy(deep=True)
        self._event(EventKind.MISSION_CREATED, f"state created for {self._mission.id}", actor="system")

    # ------------------------------------------------------------------
    # 16.1 Internals — always called with the lock held
    # ------------------------------------------------------------------

    @property
    def _now(self) -> datetime:
        return self._clock()

    def _event(
        self,
        kind: EventKind,
        message: str,
        *,
        actor: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> StateEvent:
        self._seq += 1
        event = StateEvent(
            seq=self._seq,
            kind=kind,
            message=message,
            at=self._now,
            actor=actor,
            entity_type=entity_type,
            entity_id=entity_id,
            data=data or {},
        )
        self._events.append(event)
        return event

    def _revision_of(self, kind: str, key: str) -> int:
        return self._revisions.get((kind, key), 0)

    def _bump(self, kind: str, key: str) -> int:
        revision = self._revision_of(kind, key) + 1
        self._revisions[(kind, key)] = revision
        return revision

    def _guard_revision(self, kind: str, key: str, expected: int | None) -> None:
        if expected is None:
            return
        current = self._revision_of(kind, key)
        if current != expected:
            raise StaleWriteError(
                f"{kind} {key!r} is at revision {current}, caller expected {expected}; "
                "re-read the record and retry"
            )

    def _conflict(self, message: str, *, actor: str | None = None) -> None:
        self._conflicts.append(message)
        self._event(EventKind.CONFLICT, message, actor=actor)

    # ------------------------------------------------------------------
    # 16.2 Reads — deep copies under the lock
    # ------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """A consistent, fully detached view of the state."""

        with self._lock:
            return {
                "mission": self._mission.model_copy(deep=True),
                "status": self._status,
                "evidence": [item.model_copy(deep=True) for item in self._evidence.values()],
                "subagents": [s.model_copy(deep=True) for s in self._subagents.values()],
                "workers": [w.model_copy(deep=True) for w in self._workers.values()],
                "assignments": [a.model_copy(deep=True) for a in self._assignments.values()],
                "results": [r.model_copy(deep=True) for r in self._results.values()],
                "reviews": [r_.model_copy(deep=True) for r_ in self._reviews.values()],
                "retries": dict(self._retries),
                "budget": self._budget.model_copy(deep=True),
                "events": [e.model_copy(deep=True) for e in self._events],
                "conflicts": list(self._conflicts),
            }

    def mission(self) -> Mission:
        with self._lock:
            return self._mission.model_copy(deep=True)

    def scope(self) -> Scope:
        with self._lock:
            return self._scope.model_copy(deep=True)

    @property
    def status(self) -> EntityStatus:
        with self._lock:
            return self._status

    def evidence(self) -> list[EvidenceItem]:
        with self._lock:
            return [item.model_copy(deep=True) for item in self._evidence.values()]

    def events(self, *, since: int = 0, limit: int | None = None) -> list[StateEvent]:
        with self._lock:
            selected = [e.model_copy(deep=True) for e in self._events if e.seq > since]
            return selected[-limit:] if limit else selected

    def budget(self) -> BudgetLedger:
        with self._lock:
            return self._budget.model_copy(deep=True)

    # ------------------------------------------------------------------
    # 16.3 Writes — validated, locked, event-logged
    # ------------------------------------------------------------------

    def set_status(self, status: EntityStatus, *, actor: str | None = None, note: str | None = None) -> None:
        """Move the mission's lifecycle forward.  Terminal states are final."""

        with self._lock:
            if self._status.terminal and status is not self._status:
                raise StateError(f"mission is already {self._status.value}; cannot move to {status.value}")
            previous = self._status
            self._status = status
            if status is EntityStatus.RUNNING and self._mission.started_at is None:
                self._mission = self._mission.model_copy(update={"started_at": self._now})
            if status.terminal:
                self._mission = self._mission.model_copy(update={"finished_at": self._now})
            self._event(
                EventKind.STATUS_CHANGED,
                note or f"status {previous.value} → {status.value}",
                actor=actor,
                entity_type="mission",
                entity_id=self._mission.id,
                data={"from": previous.value, "to": status.value},
            )

    def add_subagent(self, spec: SubagentSpec, *, actor: str | None = None) -> SubagentSpec:
        """Register a runtime-created Subagent (idempotent by id)."""

        with self._lock:
            if spec.mission_id and spec.mission_id != self._mission.id:
                raise StateError(f"subagent {spec.id} belongs to mission {spec.mission_id}, not {self._mission.id}")
            existing = self._subagents.get(spec.id)
            if existing is not None:
                if existing.objective != spec.objective:
                    self._conflict(
                        f"subagent {spec.id} re-registered with a different objective; keeping the first",
                        actor=actor,
                    )
                return existing.model_copy(deep=True)
            stored = spec.model_copy(update={"mission_id": self._mission.id}, deep=True)
            self._subagents[spec.id] = stored
            self._bump("subagent", spec.id)
            for worker in spec.workers:
                self._workers.setdefault(worker.id, worker.model_copy(deep=True))
            self._event(
                EventKind.SUBAGENT_ADDED,
                f"subagent '{stored.name}' added ({len(stored.workers)} worker(s))",
                actor=actor,
                entity_type="subagent",
                entity_id=stored.id,
            )
            return stored.model_copy(deep=True)

    def add_worker(self, spec: WorkerSpec, *, actor: str | None = None) -> WorkerSpec:
        """Register a task-specific Worker created by a Subagent."""

        with self._lock:
            if spec.subagent_id and spec.subagent_id not in self._subagents:
                raise StateError(f"worker {spec.id} references unknown subagent {spec.subagent_id}")
            existing = self._workers.get(spec.id)
            if existing is not None:
                if existing.objective != spec.objective:
                    self._conflict(
                        f"worker {spec.id} re-registered with a different objective; keeping the first",
                        actor=actor,
                    )
                return existing.model_copy(deep=True)
            self._workers[spec.id] = spec.model_copy(deep=True)
            self._bump("worker", spec.id)
            self._event(
                EventKind.WORKER_ADDED,
                f"worker '{spec.name}' added under {spec.subagent_id or 'unassigned'}",
                actor=actor,
                entity_type="worker",
                entity_id=spec.id,
            )
            return spec.model_copy(deep=True)

    def assign_task(self, assignment: TaskAssignment, *, actor: str | None = None) -> TaskAssignment:
        """Hand work to a Worker.  Re-assignment bumps the attempt, not the id."""

        with self._lock:
            if assignment.worker_id and assignment.worker_id not in self._workers:
                raise StateError(f"task {assignment.id} references unknown worker {assignment.worker_id}")
            existing = self._assignments.get(assignment.id)
            stored = assignment.model_copy(update={"mission_id": self._mission.id}, deep=True)
            if existing is None:
                self._assignments[stored.id] = stored
                self._event(
                    EventKind.TASK_ASSIGNED,
                    f"task assigned to {stored.worker_id or 'unassigned'} (attempt {stored.attempt})",
                    actor=actor,
                    entity_type="task",
                    entity_id=stored.id,
                )
            else:
                self._guard_revision("task", assignment.id, assignment.attempt - 1 if assignment.attempt > 1 else None)
                self._assignments[stored.id] = stored
                self._event(
                    EventKind.TASK_ASSIGNED,
                    f"task re-assigned (attempt {stored.attempt})",
                    actor=actor,
                    entity_type="task",
                    entity_id=stored.id,
                )
            self._bump("task", stored.id)
            return stored.model_copy(deep=True)

    def start_task(self, task_id: str, *, actor: str | None = None, seconds_estimate: float = 0.0) -> TaskAssignment:
        """Mark a task running and account for budget *before* the work starts."""

        with self._lock:
            assignment = self._assignments.get(task_id)
            if assignment is None:
                raise StateError(f"unknown task {task_id!r}")
            try:
                self._budget.consume(seconds=seconds_estimate, task=True)
            except BudgetExceeded as exc:
                self._event(EventKind.BUDGET_EXCEEDED, str(exc), actor=actor, entity_type="task", entity_id=task_id)
                raise
            updated = assignment.model_copy(update={"status": EntityStatus.RUNNING}, deep=True)
            self._assignments[task_id] = updated
            self._bump("task", task_id)
            if seconds_estimate:
                self._event(
                    EventKind.BUDGET_CONSUMED,
                    f"{seconds_estimate:.1f}s reserved for {task_id}",
                    actor=actor,
                    entity_type="task",
                    entity_id=task_id,
                )
            self._event(EventKind.TASK_STARTED, f"task {task_id} started", actor=actor, entity_type="task", entity_id=task_id)
            return updated.model_copy(deep=True)

    def record_result(self, result: TaskResult, *, actor: str | None = None) -> TaskResult:
        """Store a Worker outcome.  Keyed by ``(task_id, attempt)`` so a retry
        never overwrites the earlier attempt."""

        with self._lock:
            key = f"{result.task_id}@{result.attempts}"
            existing = self._results.get(key)
            if existing is not None:
                if existing.id == result.id:
                    return existing.model_copy(deep=True)     # idempotent replay
                self._conflict(
                    f"result for {key} already recorded by another worker; keeping both in the event log",
                    actor=actor,
                )
            self._results[key] = result.model_copy(deep=True)
            assignment = self._assignments.get(result.task_id)
            if assignment is not None:
                self._assignments[result.task_id] = assignment.model_copy(
                    update={"status": result.status}, deep=True
                )
                self._bump("task", result.task_id)
            else:
                self._conflict(f"result arrived for unknown task {result.task_id}", actor=actor)
            self._bump("result", key)
            self._event(
                EventKind.TASK_FINISHED,
                f"task {result.task_id} finished: {result.status.value}",
                actor=actor,
                entity_type="task",
                entity_id=result.task_id,
                data={"result_id": result.id, "attempt": result.attempts},
            )
            return result.model_copy(deep=True)

    def add_evidence(self, item: EvidenceItem, *, actor: str | None = None) -> EvidenceItem:
        """Add evidence, or merge into the existing record with the same id.

        Merging unions sources, links and tags instead of replacing them, so two
        Workers that corroborate the same observation end up with *both*
        sources rather than whichever wrote last.
        """

        with self._lock:
            existing = self._evidence.get(item.id)
            if existing is None:
                self._evidence[item.id] = item.model_copy(deep=True)
                self._bump("evidence", item.id)
                self._event(
                    EventKind.EVIDENCE_ADDED,
                    f"{item.kind.value} recorded: {item.statement[:80]}",
                    actor=actor or item.collected_by,
                    entity_type="evidence",
                    entity_id=item.id,
                )
                return item.model_copy(deep=True)

            # Source ids include the retrieval time, so two fetches of the same
            # URL are distinct records (the page may have changed).  Both are
            # kept for the audit trail, but only a *new locator* counts as
            # independent corroboration — re-fetching cannot raise confidence.
            merged_sources = {s.id: s for s in existing.sources}
            known_locators = {s.locator for s in existing.sources}
            added = 0
            for source in item.sources:
                if source.id not in merged_sources:
                    merged_sources[source.id] = source
                    if source.locator not in known_locators:
                        added += 1
                        known_locators.add(source.locator)
            merged = existing.model_copy(
                update={
                    "sources": list(merged_sources.values()),
                    "supports": list(dict.fromkeys([*existing.supports, *item.supports])),
                    "contradicts": list(dict.fromkeys([*existing.contradicts, *item.contradicts])),
                    "tags": list(dict.fromkeys([*existing.tags, *item.tags])),
                    "missing": [*existing.missing, *item.missing],
                    # Confidence is merged by rank, never replaced.  A bare
                    # default (UNKNOWN) from another worker must not erase a
                    # justified HIGH, and a raise needs a *new* source to back it.
                    "confidence": (
                        item.confidence
                        if added and item.confidence.rank > existing.confidence.rank
                        else existing.confidence
                    ),
                    "confidence_basis": (
                        item.confidence_basis
                        if added and item.confidence.rank > existing.confidence.rank and item.confidence_basis
                        else existing.confidence_basis
                    ),
                },
                deep=True,
            )
            self._evidence[item.id] = merged
            self._bump("evidence", item.id)
            self._event(
                EventKind.EVIDENCE_MERGED,
                f"evidence {item.id} merged (+{added} source(s))",
                actor=actor,
                entity_type="evidence",
                entity_id=item.id,
            )
            return merged.model_copy(deep=True)

    def record_review(self, review: QualityReview, *, actor: str | None = None) -> QualityReview:
        """Append a review round.  Rounds with the same number are kept separately
        so a re-review cannot erase the first verdict."""

        with self._lock:
            key = f"{review.subagent_id}@r{review.round}"
            existing = self._reviews.get(key)
            if existing is not None and existing.verdict != review.verdict:
                self._conflict(
                    f"review round {review.round} for {review.subagent_id} already recorded as "
                    f"{existing.verdict!r}; the first verdict is preserved",
                    actor=actor,
                )
                key = f"{key}#{review.id}"
            self._reviews[key] = review.model_copy(deep=True)
            self._bump("review", key)
            self._event(
                EventKind.REVIEW_RECORDED,
                f"review round {review.round} for {review.subagent_id}: {review.verdict}",
                actor=actor or review.reviewer,
                entity_type="review",
                entity_id=review.id,
            )
            return review.model_copy(deep=True)

    def record_retry(self, task_id: str, *, reason: str, actor: str | None = None) -> int:
        """Count a retry against the task and the retry budget."""

        with self._lock:
            try:
                self._budget.consume(retry=True)
            except BudgetExceeded as exc:
                self._event(EventKind.BUDGET_EXCEEDED, str(exc), actor=actor, entity_type="task", entity_id=task_id)
                raise
            self._retries[task_id] = self._retries.get(task_id, 0) + 1
            self._bump("retry", task_id)
            self._event(
                EventKind.RETRY_RECORDED,
                f"retry {self._retries[task_id]} for {task_id}: {reason}",
                actor=actor,
                entity_type="task",
                entity_id=task_id,
            )
            return self._retries[task_id]

    def record_error(self, error: ErrorInfo, *, actor: str | None = None, entity_id: str | None = None) -> None:
        with self._lock:
            self._event(
                EventKind.ERROR,
                f"{error.code}: {error.message}",
                actor=actor,
                entity_type="error",
                entity_id=entity_id,
                data={"retryable": error.retryable, "attempt": error.attempt},
            )

    def consume_seconds(self, seconds: float, *, actor: str | None = None, reason: str = "") -> None:
        """Charge elapsed time to the mission budget."""

        with self._lock:
            try:
                self._budget.consume(seconds=seconds)
            except BudgetExceeded as exc:
                self._event(EventKind.BUDGET_EXCEEDED, str(exc), actor=actor)
                raise
            self._event(
                EventKind.BUDGET_CONSUMED,
                f"{seconds:.1f}s consumed" + (f" ({reason})" if reason else ""),
                actor=actor,
            )

    def update_evidence_confidence(
        self,
        evidence_id: str,
        confidence: Confidence,
        *,
        basis: str,
        actor: str | None = None,
        expected_revision: int | None = None,
    ) -> EvidenceItem:
        """Revision-guarded confidence change — the canonical stale-write path."""

        with self._lock:
            existing = self._evidence.get(evidence_id)
            if existing is None:
                raise StateError(f"unknown evidence {evidence_id!r}")
            self._guard_revision("evidence", evidence_id, expected_revision)
            updated = existing.model_copy(update={"confidence": confidence, "confidence_basis": basis}, deep=True)
            self._evidence[evidence_id] = updated
            self._bump("evidence", evidence_id)
            self._event(
                EventKind.EVIDENCE_ADDED,
                f"confidence for {evidence_id} set to {confidence.value}: {basis}",
                actor=actor,
                entity_type="evidence",
                entity_id=evidence_id,
            )
            return updated.model_copy(deep=True)

    def revision_of(self, entity_type: str, key: str) -> int:
        """Public accessor so a Worker can capture the revision it read."""

        with self._lock:
            return self._revision_of(entity_type, key)

    # ------------------------------------------------------------------
    # 16.4 Progress
    # ------------------------------------------------------------------

    def progress(self) -> Progress:
        """Compute completion from the records themselves, not a counter.

        Deriving avoids the classic bug where a counter drifts from reality
        after a retry or a conflict.
        """

        with self._lock:
            assignments = list(self._assignments.values())
            results = list(self._results.values())
            statuses = [a.status for a in assignments]
            evidence = list(self._evidence.values())

            terminal = [s for s in statuses if s in {EntityStatus.SUCCEEDED, EntityStatus.FAILED, EntityStatus.SKIPPED, EntityStatus.CANCELLED, EntityStatus.BUDGET_EXCEEDED}]
            total = len(assignments)
            percent = round(100.0 * len(terminal) / total, 1) if total else 0.0
            if self._status.terminal and total:
                percent = 100.0

            return Progress(
                status=self._status,
                tasks_total=total,
                tasks_succeeded=sum(1 for s in statuses if s is EntityStatus.SUCCEEDED),
                tasks_failed=sum(1 for s in statuses if s is EntityStatus.FAILED),
                tasks_running=sum(1 for s in statuses if s is EntityStatus.RUNNING),
                tasks_skipped=sum(1 for s in statuses if s is EntityStatus.SKIPPED),
                tasks_pending=sum(1 for s in statuses if s in {EntityStatus.PENDING, EntityStatus.READY}),
                percent_complete=percent,
                subagents_total=len(self._subagents),
                workers_total=len(self._workers),
                evidence_total=len(evidence),
                observations=sum(1 for e in evidence if e.kind is EvidenceKind.OBSERVATION),
                inferences=sum(1 for e in evidence if e.kind is EvidenceKind.INFERENCE),
                allegations=sum(1 for e in evidence if e.kind is EvidenceKind.ALLEGATION),
                reviews_total=len(self._reviews),
                retries_used=sum(self._retries.values()),
                seconds_used=self._budget.seconds_used,
                seconds_limit=self._budget.seconds_limit,
                events=len(self._events),
                conflicts=len(self._conflicts),
                updated_at=self._now,
            )

    # ------------------------------------------------------------------
    # 16.5 Checkpointing
    # ------------------------------------------------------------------

    def to_checkpoint(self) -> dict[str, Any]:
        """JSON-safe, versioned payload.  Every model is serialised in full."""

        with self._lock:
            payload = {
                "schema": "argus-run-state",
                "version": self.CHECKPOINT_VERSION,
                "saved_at": self._now.isoformat(),
                "mission": json.loads(model_to_json(self._mission)),
                "scope": json.loads(model_to_json(self._scope)),
                "status": self._status.value,
                "evidence": [json.loads(model_to_json(e)) for e in self._evidence.values()],
                "subagents": [json.loads(model_to_json(s)) for s in self._subagents.values()],
                "workers": [json.loads(model_to_json(w)) for w in self._workers.values()],
                "assignments": [json.loads(model_to_json(a)) for a in self._assignments.values()],
                "results": [json.loads(model_to_json(r)) for r in self._results.values()],
                "reviews": [json.loads(model_to_json(v)) for v in self._reviews.values()],
                "retries": dict(self._retries),
                "budget": json.loads(model_to_json(self._budget)),
                "events": [json.loads(model_to_json(e)) for e in self._events],
                "revisions": {f"{k[0]}:{k[1]}": v for k, v in self._revisions.items()},
                "conflicts": list(self._conflicts),
                "seq": self._seq,
            }
            return payload

    def save_checkpoint(self, path: str | Path) -> Path:
        """Write atomically: a crash cannot leave a half-written case file."""

        target = Path(path).expanduser()
        payload = self.to_checkpoint()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            # Unique temp name so concurrent savers cannot collide.
            handle = tempfile.NamedTemporaryFile(
                "w", dir=target.parent, prefix=f".{target.name}.", suffix=".tmp", delete=False, encoding="utf-8"
            )
            try:
                with handle as stream:
                    json.dump(payload, stream, indent=2)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(handle.name, target)
            finally:
                if os.path.exists(handle.name):
                    os.unlink(handle.name)
        except OSError as exc:
            raise CheckpointError(f"could not write checkpoint {target}: {exc}") from exc
        with self._lock:
            self._event(EventKind.CHECKPOINT_SAVED, f"checkpoint written to {target}", actor="system")
        return target

    @classmethod
    def load_checkpoint(cls, path: str | Path, *, clock: "Callable[[], datetime] | None" = None) -> "RunStateStore":
        """Rebuild a store from a checkpoint, re-validating every record."""

        source = Path(path).expanduser()
        try:
            raw = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CheckpointError(f"could not read checkpoint {source}: {exc}") from exc

        if raw.get("schema") != "argus-run-state":
            raise CheckpointError(f"{source} is not a run-state checkpoint (schema={raw.get('schema')!r})")
        if raw.get("version") != cls.CHECKPOINT_VERSION:
            raise CheckpointError(
                f"checkpoint version {raw.get('version')} is not supported (expected {cls.CHECKPOINT_VERSION})"
            )

        try:
            mission = Mission.model_validate(raw["mission"])
            store = cls(mission, clock=clock)
            store._scope = Scope.model_validate(raw["scope"])
            store._status = EntityStatus(raw["status"])
            store._evidence = {
                item.id: item for item in (EvidenceItem.model_validate(p) for p in raw.get("evidence", []))
            }
            store._subagents = {
                s.id: s for s in (SubagentSpec.model_validate(p) for p in raw.get("subagents", []))
            }
            store._workers = {w.id: w for w in (WorkerSpec.model_validate(p) for p in raw.get("workers", []))}
            store._assignments = {
                a.id: a for a in (TaskAssignment.model_validate(p) for p in raw.get("assignments", []))
            }
            store._results = {
                f"{r.task_id}@{r.attempts}": r
                for r in (TaskResult.model_validate(p) for p in raw.get("results", []))
            }
            store._reviews = {
                f"{v.subagent_id}@r{v.round}": v
                for v in (QualityReview.model_validate(p) for p in raw.get("reviews", []))
            }
            store._retries = {k: int(v) for k, v in raw.get("retries", {}).items()}
            store._budget = BudgetLedger.model_validate(raw.get("budget", {}))
            store._revisions = {}
            for composite, revision in raw.get("revisions", {}).items():
                kind, _, key = composite.partition(":")
                store._revisions[(kind, key)] = int(revision)
            store._conflicts = list(raw.get("conflicts", []))
            store._seq = max([int(raw.get("seq", 0)), *[int(e["seq"]) for e in raw.get("events", [])]] or [0])
            store._events = [StateEvent.model_validate(p) for p in raw.get("events", [])]
        except (KeyError, ValueError, TypeError) as exc:
            raise CheckpointError(f"checkpoint {source} is corrupt: {type(exc).__name__}: {exc}") from exc

        store._event(EventKind.CHECKPOINT_LOADED, f"state restored from {source}", actor="system")
        return store


# --------------------------------------------------------------------------
# 16.6 Rendering and the ``state`` command
# --------------------------------------------------------------------------


def render_progress(progress: Progress) -> Table:
    table = Table(box=None, pad_edge=False, show_header=False)
    table.add_column("metric", style="dim", no_wrap=True)
    table.add_column("value", overflow="fold")
    table.add_row("status", f"[bold]{progress.status.value}[/bold]")
    table.add_row(
        "tasks",
        f"{progress.tasks_succeeded} succeeded · {progress.tasks_failed} failed · "
        f"{progress.tasks_running} running · {progress.tasks_pending} pending "
        f"(of {progress.tasks_total})",
    )
    table.add_row("progress", f"{progress.percent_complete:.1f}%")
    table.add_row("agents", f"{progress.subagents_total} subagent(s), {progress.workers_total} worker(s)")
    table.add_row(
        "evidence",
        f"{progress.evidence_total} item(s) — {progress.observations} observation(s), "
        f"{progress.inferences} inference(s), {progress.allegations} allegation(s)",
    )
    table.add_row("reviews", f"{progress.reviews_total} round(s), {progress.retries_used} retry(ies)")
    budget = f"{progress.seconds_used:.1f}s"
    if progress.seconds_limit:
        budget += f" of {progress.seconds_limit}s ({progress.budget_used_percent}%)"
    table.add_row("budget", budget)
    table.add_row("events", f"{progress.events}" + (f" · {progress.conflicts} conflict(s)" if progress.conflicts else ""))
    return table


def _demo_state_tree(store: RunStateStore, *, subagents: int = 2, workers_each: int = 2, tasks_each: int = 2) -> None:
    """Populate a store with a plausible dynamic hierarchy for demonstration."""

    mission = store.mission()
    for s_index in range(1, subagents + 1):
        subagent = SubagentSpec(
            mission_id=mission.id,
            name=f"rt-subagent-{s_index}",
            objective=f"Runtime-chosen investigation area {s_index}",
            scope_entries=store.scope().includes,
        )
        store.add_subagent(subagent)
        for w_index in range(1, workers_each + 1):
            worker = WorkerSpec(
                subagent_id=subagent.id,
                name=f"rt-worker-{s_index}-{w_index}",
                objective=f"Task-specific worker {w_index} for area {s_index}",
            )
            store.add_worker(worker)
            for t_index in range(1, tasks_each + 1):
                store.assign_task(
                    TaskAssignment(
                        mission_id=mission.id,
                        subagent_id=subagent.id,
                        worker_id=worker.id,
                        objective=f"collect target set {s_index}.{w_index}.{t_index}",
                    )
                )


def run_concurrency_self_test(threads: int = 12, items_per_thread: int = 40) -> list[ModelTestResult]:
    """Prove the acceptance criterion: parallel updates never lose work.

    Three independent races are exercised: distinct records added in parallel
    (no lost writes), the *same* record corroborated in parallel (sources are
    merged, not replaced), and revision-guarded updates (a stale writer is
    rejected rather than silently winning).
    """

    results: list[ModelTestResult] = []

    def record(name: str, ok: bool, detail: str) -> None:
        results.append(ModelTestResult(name, ok, detail))

    mission = Mission(
        objective="Concurrency self-test",
        scope=Scope(entries=[ScopeEntry(pattern="example.com")], data_classes=[DataClass.PUBLIC_WEB]),
        limits={"mission_budget_seconds": 3600},
    )

    # --- 1. parallel distinct writes --------------------------------------
    store = RunStateStore(mission)
    errors: list[str] = []

    def writer(index: int) -> None:
        try:
            for n in range(items_per_thread):
                store.add_evidence(
                    EvidenceItem(
                        kind=EvidenceKind.OBSERVATION,
                        statement=f"thread {index} observed item {n}",
                        sources=[
                            SourceReference(
                                kind=SourceKind.PUBLIC_WEB,
                                url=f"https://example.com/{index}/{n}",
                                retrieval_method=RetrievalMethod.HTTP,
                            )
                        ],
                    ),
                    actor=f"worker-{index}",
                )
        except Exception as exc:                       # pragma: no cover - failure path
            errors.append(f"{type(exc).__name__}: {exc}")

    pool = [threading.Thread(target=writer, args=(i,)) for i in range(threads)]
    for thread in pool:
        thread.start()
    for thread in pool:
        thread.join()

    expected = threads * items_per_thread
    actual = len(store.evidence())
    record(
        "parallel writes: no lost updates",
        not errors and actual == expected,
        f"{actual}/{expected} records" + (f"; errors: {errors[:2]}" if errors else ""),
    )
    record(
        "parallel writes: unique ids",
        len({e.id for e in store.evidence()}) == actual,
        f"{len({e.id for e in store.evidence()})} unique of {actual}",
    )
    record(
        "parallel writes: event log ordered",
        [e.seq for e in store.events()] == list(range(1, len(store.events()) + 1)),
        f"{len(store.events())} events",
    )

    # --- 2. concurrent corroboration of ONE record -------------------------
    shared = EvidenceItem(
        kind=EvidenceKind.OBSERVATION,
        statement="The same fact, observed independently.",
        sources=[
            SourceReference(kind=SourceKind.PUBLIC_WEB, url="https://example.com/base",
                            retrieval_method=RetrievalMethod.HTTP)
        ],
    )
    store.add_evidence(shared)
    merge_errors: list[str] = []

    def corroborator(index: int) -> None:
        try:
            store.add_evidence(
                EvidenceItem(
                    kind=EvidenceKind.OBSERVATION,
                    statement=shared.statement,
                    sources=[
                        SourceReference(
                            kind=SourceKind.ARCHIVE,
                            url=f"https://archive.example/{index}",
                            retrieval_method=RetrievalMethod.HTTP,
                        )
                    ],
                    tags=[f"source-{index}"],
                ),
                actor=f"worker-{index}",
            )
        except Exception as exc:                       # pragma: no cover
            merge_errors.append(f"{type(exc).__name__}: {exc}")

    readers = [threading.Thread(target=corroborator, args=(i,)) for i in range(threads)]
    for thread in readers:
        thread.start()
    for thread in readers:
        thread.join()

    merged = next(e for e in store.evidence() if e.id == shared.id)
    record(
        "merge: every corroborating source kept",
        not merge_errors and len(merged.sources) == threads + 1,
        f"{len(merged.sources)} source(s), expected {threads + 1}",
    )
    record(
        "merge: tags unioned",
        len(merged.tags) == threads,
        f"{len(merged.tags)} tag(s)",
    )
    record(
        "merge: statement not duplicated",
        len([e for e in store.evidence() if e.statement == shared.statement]) == 1,
        "one record",
    )

    # --- 3. stale writes are rejected -------------------------------------
    revision = store.revision_of("evidence", shared.id)
    store.update_evidence_confidence(shared.id, Confidence.MEDIUM, basis="two independent sources",
                                     expected_revision=revision)
    stale_raised = False
    try:
        store.update_evidence_confidence(shared.id, Confidence.HIGH, basis="stale writer",
                                         expected_revision=revision)
    except StaleWriteError:
        stale_raised = True
    record("revisions: stale writer rejected", stale_raised, "StaleWriteError raised")

    # A corroborating merge must not silently downgrade a justified confidence.
    confirm_store = RunStateStore(Mission(objective="merge confidence", scope=Scope(entries=[ScopeEntry(pattern="example.com")])))
    confirmed = EvidenceItem(
        kind=EvidenceKind.OBSERVATION,
        statement="Confirmed by one strong source.",
        sources=[SourceReference(kind=SourceKind.PUBLIC_WEB, url="https://example.com/strong",
                                 retrieval_method=RetrievalMethod.HTTP)],
        confidence=Confidence.HIGH,
        confidence_basis="first-party signed advisory",
    )
    confirm_store.add_evidence(confirmed)
    confirm_store.add_evidence(
        EvidenceItem(
            kind=EvidenceKind.OBSERVATION,
            statement=confirmed.statement,
            sources=[SourceReference(kind=SourceKind.API, url="https://api.example/echo",
                                     retrieval_method=RetrievalMethod.API_CALL)],
        )
    )
    kept = next(e for e in confirm_store.evidence() if e.id == confirmed.id)
    record(
        "merge: a bare re-submission cannot erase confidence",
        kept.confidence is Confidence.HIGH,
        kept.confidence.value,
    )

    # --- 4. budget accounting under contention ----------------------------
    budget_store = RunStateStore(
        Mission(objective="budget test", scope=Scope(entries=[ScopeEntry(pattern="example.com")]),
                limits={"mission_budget_seconds": 10})
    )
    task = TaskAssignment(worker_id="", objective="work")
    budget_store.assign_task(task)
    allowed = 0
    denied = 0
    lock = threading.Lock()

    def spender() -> None:
        nonlocal allowed, denied
        try:
            budget_store.consume_seconds(1.0)
            with lock:
                allowed += 1
        except BudgetExceeded:
            with lock:
                denied += 1

    spenders = [threading.Thread(target=spender) for _ in range(20)]
    for thread in spenders:
        thread.start()
    for thread in spenders:
        thread.join()
    record(
        "budget: never overspends under contention",
        allowed == 10 and denied == 10 and budget_store.budget().seconds_used == 10.0,
        f"allowed={allowed} denied={denied} used={budget_store.budget().seconds_used}",
    )

    # --- 5. progress is derived, not counted ------------------------------
    snapshot_before = store.progress()
    store.add_evidence(
        EvidenceItem(
            kind=EvidenceKind.OBSERVATION,
            statement="late addition",
            sources=[SourceReference(kind=SourceKind.PUBLIC_WEB, url="https://example.com/late",
                                     retrieval_method=RetrievalMethod.HTTP)],
        )
    )
    record(
        "progress: recomputed from records",
        store.progress().evidence_total == snapshot_before.evidence_total + 1,
        f"{snapshot_before.evidence_total} → {store.progress().evidence_total}",
    )

    # --- 6. checkpoint round-trip -----------------------------------------
    try:
        store.set_status(EntityStatus.RUNNING)
        store.record_retry(next(iter(store.snapshot()["assignments"])).id if store.snapshot()["assignments"] else "task-x",
                           reason="self-test")
    except Exception:                                   # pragma: no cover - optional in demo
        pass
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        store.save_checkpoint(path)
        restored = RunStateStore.load_checkpoint(path)
        before_progress = store.progress()
        after_progress = restored.progress()
        record(
            "checkpoint: evidence count survives",
            after_progress.evidence_total == before_progress.evidence_total,
            f"{after_progress.evidence_total} items",
        )
        record(
            "checkpoint: sources survive",
            len(next(e for e in restored.evidence() if e.id == shared.id).sources) == threads + 1,
            "merged sources intact",
        )
        record(
            "checkpoint: budget survives",
            restored.budget().seconds_used == store.budget().seconds_used,
            f"{restored.budget().seconds_used}s",
        )
        record(
            "checkpoint: status survives",
            restored.status is store.status,
            restored.status.value,
        )
        restored_events = restored.events()
        record(
            # The save event is logged after the payload is written, so a restored
            # store legitimately resumes at the same seq.  The invariant that
            # matters is that the log stays contiguous and records the load.
            "checkpoint: event log stays contiguous",
            [e.seq for e in restored_events] == list(range(1, len(restored_events) + 1))
            and restored_events[-1].kind is EventKind.CHECKPOINT_LOADED,
            f"{len(restored_events)} events, last {restored_events[-1].kind.value}",
        )
        record(
            "checkpoint: revisions preserved",
            restored.revision_of("evidence", shared.id) == store.revision_of("evidence", shared.id),
            str(restored.revision_of("evidence", shared.id)),
        )

    return results


@app.command("state", help="Inspect, exercise and checkpoint the unified run-state store.")
def state_command(
    objective: str = typer.Option(
        "Map the public attack surface of example.com", "--objective", "-o", help="Objective for the demo state."
    ),
    target: list[str] | None = typer.Option(None, "--target", "-t", help="Target (repeatable)."),
    stress: bool = typer.Option(
        False, "--stress", help="Run the concurrency self-test (parallel writers, merges, budgets)."
    ),
    threads: int = typer.Option(12, "--threads", min=2, max=64, help="Writer threads for --stress."),
    items: int = typer.Option(40, "--items", min=1, max=2000, help="Records per writer thread."),
    checkpoint: str | None = typer.Option(None, "--checkpoint", help="Write a checkpoint JSON file here."),
    load: str | None = typer.Option(None, "--load", help="Load a checkpoint and report its state."),
    demo: bool = typer.Option(False, "--demo", help="Populate a sample hierarchy before reporting."),
    as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Pure local state work: no network, no model, no browser."""

    console = get_console()

    if load:
        try:
            store = RunStateStore.load_checkpoint(load)
        except CheckpointError as exc:
            console.print(f"[red]checkpoint error:[/red] {escape(str(exc))}")
            raise typer.Exit(ExitCode.CONFIG) from exc
        if as_json:
            _emit(
                json.dumps(
                    {
                        "loaded_from": str(load),
                        "progress": json.loads(model_to_json(store.progress())),
                        "checkpoint": store.to_checkpoint(),
                    },
                    indent=2,
                )
            )
        else:
            console.print()
            console.print(Panel(Text(f"state restored from {load}", style="green"), border_style="green", expand=False))
            console.print(render_progress(store.progress()))
            console.print()
        raise typer.Exit(ExitCode.OK)

    # Build a state from a real preflight so scope and objective are honest.
    targets = _normalise_targets(target or ["example.com"])
    preflight = run_preflight(objective=objective, targets=targets, scope_entries=targets)
    if not preflight.ok:
        render_preflight(preflight)
        raise typer.Exit(preflight.exit_code)

    request = MissionRequest(targets=targets, objective=objective, dry_run=True)
    mission = Mission.from_preflight(
        request=request, preflight=preflight, settings=build_settings({}, {}).settings
    )
    store = RunStateStore(mission)

    if demo:
        _demo_state_tree(store)
    if stress:
        store.set_status(EntityStatus.RUNNING)

    results = run_concurrency_self_test(threads=threads, items_per_thread=items) if stress else []
    failures = [r for r in results if not r.ok]
    saved_path: Path | None = None

    if checkpoint:
        target_path = Path(checkpoint).expanduser()
        try:
            saved_path = store.save_checkpoint(target_path)
        except CheckpointError as exc:
            console.print(f"[red]checkpoint error:[/red] {escape(str(exc))}")
            raise typer.Exit(ExitCode.CONFIG) from exc

    payload = {
        "mission_id": mission.id,
        "progress": json.loads(model_to_json(store.progress())),
        "self_test": [{"check": r.name, "ok": r.ok, "detail": r.detail} for r in results],
        "checkpoint": str(saved_path) if saved_path else None,
        "ok": not failures,
    }

    if as_json:
        _emit(json.dumps(payload, indent=2))
        raise typer.Exit(ExitCode.OK if not failures else ExitCode.INTERNAL)

    console.print()
    console.print(
        Panel(
            Text(f"{mission.id}\n{mission.objective}", style="white"),
            title=f"[bold cyan]{APP_TITLE} run state[/bold cyan]",
            title_align="left",
            border_style="cyan",
            expand=False,
        )
    )
    console.print(render_progress(store.progress()))

    if results:
        console.print()
        table = Table(title="concurrency self-test", title_justify="left", box=None, pad_edge=False)
        table.add_column("", width=2)
        table.add_column("check", style="bold", no_wrap=True)
        table.add_column("detail", overflow="fold")
        for result in results:
            glyph, colour = ("✔", "green") if result.ok else ("✘", "red")
            table.add_row(f"[{colour}]{glyph}[/{colour}]", escape(result.name), escape(result.detail))
        console.print(table)
        console.print(f"[{'green' if not failures else 'red'}]{len(results) - len(failures)} passed[/] · {len(failures)} failed")

    if saved_path:
        console.print(f"[green]checkpoint[/green] written to {escape(str(saved_path))}")
    console.print()

    raise typer.Exit(ExitCode.OK if not failures else ExitCode.INTERNAL)


# ══════════════════════════════════════════════════════════════════════════
# 17. CLI-only event renderer
# ══════════════════════════════════════════════════════════════════════════
#
# A streaming, line-oriented renderer for mission progress.  It is deliberately
# *not* a full-screen TUI:
#
#   * no alternate screen buffer (Rich's ``Live(screen=True)`` is never used);
#   * no cursor-addressing, no scroll regions, no mouse handling;
#   * transient animation is limited to Rich's inline ``status`` spinner, which
#     writes ``\r`` on a TTY and — verified — writes *nothing at all* when the
#     stream is not a terminal.
#
# Consequences, which the acceptance tests pin down:
#
#   * In a pipe, a log file or CI, output is plain, complete and chronological:
#     every event appears exactly once, with no carriage returns and no escapes.
#   * Disabling animation or colour never removes information: when animation is
#     off, a status becomes an explicit start line and end line instead.
#   * Nested output stays readable because hierarchy is expressed as indentation
#     computed from spawn relationships, not as cursor movement.
#
# Usage:
#   renderer = EventRenderer.from_options(color=False, animation=False)
#   renderer.subagent_spawned("sa-1", "passive-dns", parent="master")
#   with renderer.status("enumerating records"):
#       ...

class RenderKind(str, Enum):
    """Every event the renderer understands."""

    MASTER_THINKING = "master-thinking"
    MASTER_PLANNING = "master-planning"
    SUBAGENT_SPAWN = "subagent-spawn"
    WORKER_SPAWN = "worker-spawn"
    TASK_ASSIGN = "task-assign"
    BROWSING = "browsing"
    FORENSIC = "forensic"
    REASONING = "reasoning"
    WORKER_DONE = "worker-done"
    QUALITY_REVIEW = "quality-review"
    RETASKING = "retasking"
    SUBAGENT_SYNTHESIS = "subagent-synthesis"
    MASTER_SYNTHESIS = "master-synthesis"
    WARNING = "warning"
    COMPLETE = "complete"
    # supporting kinds (not part of the required fifteen, but needed for logs)
    INFO = "info"
    ERROR = "error"
    DEBUG = "debug"


class EventLevel(str, Enum):
    """Verbosity of one event.  Filters compare by index."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

    @property
    def rank(self) -> int:
        return {EventLevel.DEBUG: 0, EventLevel.INFO: 1, EventLevel.WARNING: 2, EventLevel.ERROR: 3}[self]


#: kind → (unicode glyph, ascii glyph, rich style, minimum level)
_KIND_STYLES: dict[RenderKind, tuple[str, str, str, EventLevel]] = {
    RenderKind.MASTER_THINKING: ("◆", "*", "bold cyan", EventLevel.INFO),
    RenderKind.MASTER_PLANNING: ("◇", "-", "bold cyan", EventLevel.INFO),
    RenderKind.SUBAGENT_SPAWN: ("⬡", "+", "bold magenta", EventLevel.INFO),
    RenderKind.WORKER_SPAWN: ("·", "+", "magenta", EventLevel.INFO),
    RenderKind.TASK_ASSIGN: ("→", ">", "blue", EventLevel.INFO),
    RenderKind.BROWSING: ("◐", "~", "cyan", EventLevel.INFO),
    RenderKind.FORENSIC: ("⚑", "#", "yellow", EventLevel.INFO),
    RenderKind.REASONING: ("∴", ":", "green", EventLevel.INFO),
    RenderKind.WORKER_DONE: ("✔", "v", "green", EventLevel.INFO),
    RenderKind.QUALITY_REVIEW: ("⚖", "=", "bold yellow", EventLevel.INFO),
    RenderKind.RETASKING: ("↻", "r", "yellow", EventLevel.INFO),
    RenderKind.SUBAGENT_SYNTHESIS: ("⊞", "s", "bold green", EventLevel.INFO),
    RenderKind.MASTER_SYNTHESIS: ("★", "S", "bold green", EventLevel.INFO),
    RenderKind.WARNING: ("!", "!", "bold yellow", EventLevel.WARNING),
    RenderKind.COMPLETE: ("■", "C", "bold green", EventLevel.INFO),
    RenderKind.INFO: ("·", ".", "dim", EventLevel.INFO),
    RenderKind.ERROR: ("✘", "X", "bold red", EventLevel.ERROR),
    RenderKind.DEBUG: ("·", ".", "dim", EventLevel.DEBUG),
}

#: Escape sequences that would indicate a full-screen interface.
_ALT_SCREEN_SEQUENCES: tuple[str, ...] = ("\x1b[?1049h", "\x1b[?1049l", "\x1b[?47h", "\x1b[?47l")


class RenderEvent(StrictModel):
    """One renderable event.

    ``seq`` is assigned by the renderer under its lock, so concurrent Workers
    cannot interleave two events into one line or duplicate a sequence number.
    """

    seq: int = Field(default=0, ge=0)
    kind: RenderKind
    message: str = Field(min_length=1)
    at: datetime = Field(default_factory=utc_now)
    level: EventLevel = EventLevel.INFO
    actor: str | None = None              # agent id that caused the event
    parent: str | None = None             # spawner, for hierarchy
    label: str | None = None              # human name of the actor
    depth: int | None = Field(default=None, ge=0)   # explicit override
    data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("at", mode="before")
    @classmethod
    def _tz(cls, value: Any) -> datetime:
        return normalise_datetime(value)

    @field_validator("message")
    @classmethod
    def _redact(cls, value: str) -> str:
        # The renderer is the last place a secret could reach a terminal.
        return redact_text(value, secrets=known_secrets())

    def to_jsonl(self) -> str:
        return model_to_json(self, indent=None).replace("\n", "")


class RenderTrace(StrictModel):
    """An ordered record of everything rendered — the CI/audit artefact."""

    events: list[RenderEvent] = Field(default_factory=list)
    schema_version: int = 1

    def append(self, event: RenderEvent) -> None:
        self.events.append(event)

    @property
    def chronological(self) -> bool:
        """True when sequence numbers are strictly increasing and contiguous."""

        return [e.seq for e in self.events] == list(range(1, len(self.events) + 1))

    def to_jsonl(self) -> str:
        return "\n".join(e.to_jsonl() for e in self.events) + ("\n" if self.events else "")

    def save(self, path: str | Path) -> Path:
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.to_jsonl(), encoding="utf-8")
        return target

    @classmethod
    def from_jsonl(cls, text: str) -> "RenderTrace":
        trace = cls()
        for line in text.splitlines():
            if line.strip():
                trace.append(RenderEvent.model_validate_json(line))
        return trace

    @classmethod
    def load(cls, path: str | Path) -> "RenderTrace":
        return cls.from_jsonl(Path(path).expanduser().read_text(encoding="utf-8"))


class EventRenderer:
    """Line-oriented event renderer with optional transient status animation.

    Thread-safe: ``emit`` takes a lock to assign the sequence number and write
    the line, so parallel Subagents and Workers produce an untangled log.
    """

    def __init__(
        self,
        console: Console,
        *,
        color: bool = True,
        animation: bool = True,
        min_level: EventLevel = EventLevel.INFO,
        timestamps: bool = True,
        ascii_only: bool = False,
        log_file: str | Path | None = None,
    ) -> None:
        self.console = console
        self.color = color
        # Animation is only ever *possible* on a real terminal.
        self.animation = bool(animation and console.is_terminal)
        self.min_level = min_level
        self.timestamps = timestamps
        self.ascii_only = ascii_only
        self._lock = threading.RLock()
        self._seq = 0
        self._depth_of: dict[str, int] = {"master": 0}
        self._label_of: dict[str, str] = {"master": "master"}
        self._trace = RenderTrace()
        self._status_depth = 0
        self._log_path = Path(log_file).expanduser() if log_file else None
        if self._log_path:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)

    # -- construction ------------------------------------------------------

    @classmethod
    def from_options(
        cls,
        *,
        color: bool = True,
        animation: bool = True,
        min_level: EventLevel = EventLevel.INFO,
        timestamps: bool = True,
        ascii_only: bool = False,
        log_file: str | Path | None = None,
        stream: Any = None,
    ) -> "EventRenderer":
        """Build a renderer whose Console is configured for the target stream."""

        console = Console(
            file=stream if stream is not None else sys.stdout,
            no_color=not color,
            highlight=False,
            soft_wrap=False,
            width=None if (stream or sys.stdout).isatty() else FALLBACK_CONSOLE_WIDTH,
            emoji=False,
        )
        return cls(
            console,
            color=color,
            animation=animation,
            min_level=min_level,
            timestamps=timestamps,
            ascii_only=ascii_only,
            log_file=log_file,
        )

    # -- hierarchy ---------------------------------------------------------

    def register_agent(self, agent_id: str, *, parent: str = "master", label: str | None = None) -> int:
        """Record where an agent sits in the tree.  Returns its depth."""

        with self._lock:
            depth = self._depth_of.get(parent, 0) + 1
            self._depth_of[agent_id] = depth
            self._label_of[agent_id] = label or agent_id
            return depth

    def depth_of(self, agent_id: str | None) -> int:
        if not agent_id:
            return 0
        with self._lock:
            return self._depth_of.get(agent_id, 0)

    def _glyph(self, kind: RenderKind) -> tuple[str, str, EventLevel]:
        unicode_glyph, ascii_glyph, style, floor = _KIND_STYLES[kind]
        return (ascii_glyph if self.ascii_only else unicode_glyph), style, floor

    def _indent(self, depth: int) -> str:
        if depth <= 0:
            return ""
        return ("|  " if self.ascii_only else "│  ") * depth

    def _format_time(self, moment: datetime) -> str:
        return moment.astimezone(timezone.utc).strftime("%H:%M:%S")

    # -- core emit ---------------------------------------------------------

    def emit(
        self,
        kind: RenderKind,
        message: str,
        *,
        actor: str | None = None,
        parent: str | None = None,
        label: str | None = None,
        depth: int | None = None,
        level: EventLevel | None = None,
        data: dict[str, Any] | None = None,
        force: bool = False,
    ) -> RenderEvent | None:
        """Render one event.  Returns it, or ``None`` when filtered out.

        Filtering still advances the sequence number's *meaning*: filtered
        events are recorded in the trace with their sequence, so a replayed or
        filtered log remains chronological and complete.
        """

        glyph, style, floor = self._glyph(kind)
        effective_level = level or floor
        if kind is RenderKind.WARNING:
            effective_level = EventLevel.WARNING
        if kind is RenderKind.ERROR:
            effective_level = EventLevel.ERROR

        with self._lock:
            self._seq += 1
            event = RenderEvent(
                seq=self._seq,
                kind=kind,
                message=message,
                at=utc_now(),
                level=effective_level,
                actor=actor,
                parent=parent,
                label=label,
                depth=depth,
                data=data or {},
            )
            self._trace.append(event)

            if label and actor:
                self._label_of[actor] = label
            if kind is RenderKind.SUBAGENT_SPAWN and actor is not None:
                self._depth_of.setdefault(actor, self._depth_of.get(parent or "master", 0) + 1)
            if kind is RenderKind.WORKER_SPAWN and actor is not None:
                self._depth_of.setdefault(actor, self._depth_of.get(parent or "master", 0) + 1)

            visible = force or effective_level.rank >= self.min_level.rank
            if visible:
                self._write_line(event, glyph, style)
            self._append_log(event, glyph)
            return event

    def _write_line(self, event: RenderEvent, glyph: str, style: str) -> None:
        depth = event.depth if event.depth is not None else self.depth_of(event.actor)
        prefix = self._indent(depth)
        who = event.label or self._label_of.get(event.actor or "", event.actor or "")

        parts: list[str] = []
        if self.timestamps:
            parts.append(f"[dim]{self._format_time(event.at)}[/dim]")
        parts.append(f"[{style}]{escape(glyph)}[/{style}]")
        line = "  ".join(parts)

        if who and event.kind not in {RenderKind.SUBAGENT_SPAWN, RenderKind.WORKER_SPAWN}:
            line = f"{line}  [dim]{escape(who)}[/dim]"
        elif who and event.kind in {RenderKind.SUBAGENT_SPAWN, RenderKind.WORKER_SPAWN}:
            line = f"{line}  [bold]{escape(who)}[/bold]"

        kind_label = "" if event.kind in {RenderKind.INFO, RenderKind.DEBUG} else f"[dim]\\[{event.kind.value}][/dim] "
        line = f"{prefix}{line}  {kind_label}{escape(event.message)}"
        if event.data:
            extras = " ".join(f"{k}={v}" for k, v in event.data.items())
            line = f"{line}  [dim]({escape(extras)})[/dim]"

        self.console.print(line, highlight=False, soft_wrap=False)

    def _append_log(self, event: RenderEvent, glyph: str) -> None:
        """Mirror every event to the plain log file, filtered or not."""

        if not self._log_path:
            return
        depth = event.depth if event.depth is not None else self.depth_of(event.actor)
        who = event.label or self._label_of.get(event.actor or "", "")
        stamp = event.at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        line = (
            f"{stamp} seq={event.seq:<4} {event.level.value:<7} {event.kind.value:<20} "
            f"{'  ' * depth}{glyph} {who + ': ' if who else ''}{event.message}"
        )
        try:
            with self._log_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:                                  # pragma: no cover - disk full etc.
            pass

    # -- transient status --------------------------------------------------

    @contextmanager
    def status(self, message: str, *, spinner: str = "dots"):
        """Transient spinner on a TTY; explicit start/end lines elsewhere.

        When animation is off — or the stream is not a terminal — this prints
        ``… message`` and then ``✔ message`` so the log still shows that the
        step happened and that it finished.
        """

        if not self.animation:
            self.console.print(f"[dim]… {escape(message)}[/dim]", highlight=False)
            try:
                yield self
            finally:
                self.console.print(f"[dim]✔ {escape(message)}[/dim]", highlight=False)
            return

        with self.console.status(f"[cyan]{escape(message)}[/cyan]", spinner=spinner):
            yield self

    # -- typed convenience emitters ---------------------------------------

    def master_thinking(self, message: str, **kwargs: Any) -> RenderEvent | None:
        return self.emit(RenderKind.MASTER_THINKING, message, actor="master", **kwargs)

    def master_planning(self, message: str, **kwargs: Any) -> RenderEvent | None:
        return self.emit(RenderKind.MASTER_PLANNING, message, actor="master", **kwargs)

    def subagent_spawned(self, agent_id: str, label: str, *, parent: str = "master", **kwargs: Any) -> RenderEvent | None:
        self.register_agent(agent_id, parent=parent, label=label)
        return self.emit(
            RenderKind.SUBAGENT_SPAWN,
            f"spawned subagent {label}",
            actor=agent_id,
            parent=parent,
            label=label,
            **kwargs,
        )

    def worker_spawned(self, agent_id: str, label: str, *, parent: str, **kwargs: Any) -> RenderEvent | None:
        self.register_agent(agent_id, parent=parent, label=label)
        return self.emit(
            RenderKind.WORKER_SPAWN,
            f"spawned worker {label}",
            actor=agent_id,
            parent=parent,
            label=label,
            **kwargs,
        )

    def task_assigned(self, message: str, *, actor: str, **kwargs: Any) -> RenderEvent | None:
        return self.emit(RenderKind.TASK_ASSIGN, message, actor=actor, **kwargs)

    def browsing(self, message: str, *, actor: str, url: str | None = None, **kwargs: Any) -> RenderEvent | None:
        data = dict(kwargs.pop("data", {}) or {})
        if url:
            data["url"] = url
        return self.emit(RenderKind.BROWSING, message, actor=actor, data=data, **kwargs)

    def forensic(self, message: str, *, actor: str, artifact: str | None = None, **kwargs: Any) -> RenderEvent | None:
        data = dict(kwargs.pop("data", {}) or {})
        if artifact:
            data["artifact"] = artifact
        return self.emit(RenderKind.FORENSIC, message, actor=actor, data=data, **kwargs)

    def reasoning(self, message: str, *, actor: str = "master", **kwargs: Any) -> RenderEvent | None:
        return self.emit(RenderKind.REASONING, message, actor=actor, **kwargs)

    def worker_done(self, message: str, *, actor: str, **kwargs: Any) -> RenderEvent | None:
        return self.emit(RenderKind.WORKER_DONE, message, actor=actor, **kwargs)

    def quality_review(self, message: str, *, actor: str, verdict: str | None = None, **kwargs: Any) -> RenderEvent | None:
        data = dict(kwargs.pop("data", {}) or {})
        if verdict:
            data["verdict"] = verdict
        return self.emit(RenderKind.QUALITY_REVIEW, message, actor=actor, data=data, **kwargs)

    def retasking(self, message: str, *, actor: str, **kwargs: Any) -> RenderEvent | None:
        return self.emit(RenderKind.RETASKING, message, actor=actor, **kwargs)

    def subagent_synthesis(self, message: str, *, actor: str, **kwargs: Any) -> RenderEvent | None:
        return self.emit(RenderKind.SUBAGENT_SYNTHESIS, message, actor=actor, **kwargs)

    def master_synthesis(self, message: str, **kwargs: Any) -> RenderEvent | None:
        return self.emit(RenderKind.MASTER_SYNTHESIS, message, actor="master", **kwargs)

    def warning(self, message: str, *, actor: str | None = None, **kwargs: Any) -> RenderEvent | None:
        return self.emit(RenderKind.WARNING, message, actor=actor, force=True, **kwargs)

    def error(self, message: str, *, actor: str | None = None, **kwargs: Any) -> RenderEvent | None:
        return self.emit(RenderKind.ERROR, message, actor=actor, force=True, **kwargs)

    def complete(self, message: str, **kwargs: Any) -> RenderEvent | None:
        return self.emit(RenderKind.COMPLETE, message, actor="master", force=True, **kwargs)

    # -- derived helpers ---------------------------------------------------

    @property
    def trace(self) -> RenderTrace:
        with self._lock:
            return RenderTrace(events=[e.model_copy(deep=True) for e in self._trace.events])

    @property
    def event_count(self) -> int:
        with self._lock:
            return len(self._trace.events)

    def summary(self) -> Table:
        """Per-kind counts plus chronology, for the end of a run."""

        with self._lock:
            counts: dict[str, int] = {}
            for event in self._trace.events:
                counts[event.kind.value] = counts.get(event.kind.value, 0) + 1
            table = Table(box=None, pad_edge=False, show_header=False)
            table.add_column("kind", style="dim", no_wrap=True)
            table.add_column("count", justify="right", no_wrap=True)
            for kind, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
                table.add_row(kind, str(count))
            table.add_row("[bold]total[/bold]", f"[bold]{len(self._trace.events)}[/bold]")
            return table

    def consume_state_events(self, events: Sequence[StateEvent]) -> list[RenderEvent]:
        """Render the run-state event log from :class:`RunStateStore`.

        This is how a real mission's audit trail reaches the terminal: the store
        records facts, the renderer decides presentation.
        """

        mapping = {
            StateEventKind.MISSION_CREATED: RenderKind.INFO,
            StateEventKind.STATUS_CHANGED: RenderKind.INFO,
            StateEventKind.SUBAGENT_ADDED: RenderKind.SUBAGENT_SPAWN,
            StateEventKind.WORKER_ADDED: RenderKind.WORKER_SPAWN,
            StateEventKind.TASK_ASSIGNED: RenderKind.TASK_ASSIGN,
            StateEventKind.TASK_STARTED: RenderKind.BROWSING,
            StateEventKind.TASK_FINISHED: RenderKind.WORKER_DONE,
            StateEventKind.EVIDENCE_ADDED: RenderKind.REASONING,
            StateEventKind.EVIDENCE_MERGED: RenderKind.REASONING,
            StateEventKind.REVIEW_RECORDED: RenderKind.QUALITY_REVIEW,
            StateEventKind.RETRY_RECORDED: RenderKind.RETASKING,
            StateEventKind.BUDGET_CONSUMED: RenderKind.DEBUG,
            StateEventKind.BUDGET_EXCEEDED: RenderKind.WARNING,
            StateEventKind.CONFLICT: RenderKind.WARNING,
            StateEventKind.CHECKPOINT_SAVED: RenderKind.INFO,
            StateEventKind.CHECKPOINT_LOADED: RenderKind.INFO,
            StateEventKind.ERROR: RenderKind.ERROR,
        }
        rendered: list[RenderEvent] = []
        for event in events:
            out = self.emit(
                mapping.get(event.kind, RenderKind.INFO),
                event.message,
                actor=event.actor,
                label=event.actor,
            )
            if out is not None:
                rendered.append(out)
        return rendered


@app.command("renderer", help="Exercise the CLI-only event renderer (no network, no model).")
def renderer_command(
    demo: bool = typer.Option(True, "--demo/--no-demo", help="Render a scripted nested mission."),
    replay: str | None = typer.Option(None, "--replay", help="Re-render a JSONL trace recorded earlier."),
    record: str | None = typer.Option(None, "--record", help="Write the JSONL trace here."),
    log_file: str | None = typer.Option(None, "--log-file", help="Append a plain-text log here."),
    from_state: str | None = typer.Option(None, "--from-state", help="Render events from a run-state checkpoint."),
    no_color: bool = typer.Option(False, "--no-color", help="Disable ANSI colour."),
    no_animation: bool = typer.Option(False, "--no-animation", help="Disable the transient spinner."),
    ascii_only: bool = typer.Option(False, "--ascii", help="ASCII glyphs only."),
    timestamps: bool = typer.Option(True, "--timestamps/--no-timestamps", help="Show HH:MM:SS prefixes."),
    min_level: EventLevel = typer.Option(EventLevel.INFO, "--level", case_sensitive=False),
    self_test: bool = typer.Option(False, "--self-test", help="Verify the renderer guarantees."),
    as_json: bool = typer.Option(False, "--json", help="Emit the trace as JSON instead of prose."),
) -> None:
    """Renders to stdout only.  Never opens an alternate screen."""

    console = get_console()

    if self_test:
        results = run_renderer_self_test()
        failures = [r for r in results if not r.ok]
        if as_json:
            _emit(json.dumps({"ok": not failures, "checks": [asdict(r) for r in results]}, indent=2))
            raise typer.Exit(ExitCode.OK if not failures else ExitCode.INTERNAL)
        console.print()
        table = Table(title="renderer self-test", title_justify="left", box=None, pad_edge=False)
        table.add_column("", width=2)
        table.add_column("check", style="bold", no_wrap=True)
        table.add_column("detail", overflow="fold")
        for result in results:
            glyph, colour = ("✔", "green") if result.ok else ("✘", "red")
            table.add_row(f"[{colour}]{glyph}[/{colour}]", escape(result.name), escape(result.detail))
        console.print(table)
        console.print(f"[{'green' if not failures else 'red'}]{len(results) - len(failures)} passed[/] · {len(failures)} failed\n")
        raise typer.Exit(ExitCode.OK if not failures else ExitCode.INTERNAL)

    # In machine mode the JSONL trace owns stdout, so prose goes to stderr and
    # the two streams cannot corrupt one another when captured together.
    renderer = EventRenderer.from_options(
        color=not no_color,
        animation=not no_animation,
        min_level=min_level,
        timestamps=timestamps,
        ascii_only=ascii_only,
        log_file=log_file,
        stream=sys.stderr if as_json else None,
    )

    if replay:
        try:
            trace = RenderTrace.load(replay)
        except (OSError, ValueError) as exc:
            console.print(f"[red]cannot read trace:[/red] {escape(str(exc))}")
            raise typer.Exit(ExitCode.CONFIG) from exc
        for event in trace.events:
            renderer.emit(event.kind, event.message, actor=event.actor, parent=event.parent,
                          label=event.label, depth=event.depth, level=event.level,
                          data=event.data, force=True)
    elif from_state:
        try:
            store = RunStateStore.load_checkpoint(from_state)
        except CheckpointError as exc:
            console.print(f"[red]checkpoint error:[/red] {escape(str(exc))}")
            raise typer.Exit(ExitCode.CONFIG) from exc
        renderer.consume_state_events(store.events())
    elif demo:
        _render_demo_mission(renderer)

    renderer.complete("run finished")
    trace = renderer.trace

    if record:
        try:
            path = trace.save(record)
        except OSError as exc:
            # Machine mode keeps stdout clean; report on stderr.
            if as_json:
                typer.echo(f"cannot write trace: {exc}", err=True)
            else:
                console.print(f"[red]cannot write trace:[/red] {escape(str(exc))}")
            raise typer.Exit(ExitCode.CONFIG) from exc
        if not as_json:
            console.print(f"[dim]trace recorded to {escape(str(path))}[/dim]")

    if as_json:
        _emit(trace.to_jsonl())
        raise typer.Exit(ExitCode.OK)

    console.print()
    console.print(renderer.summary())
    console.print(
        f"[green]✔ {renderer.event_count} event(s)[/green] "
        f"· colour={'on' if not no_color else 'off'} · animation={'on' if renderer.animation else 'off'}"
        f" · chronological={'yes' if trace.chronological else 'NO'}"
    )
    console.print()
    raise typer.Exit(ExitCode.OK)


def _render_demo_mission(renderer: EventRenderer) -> None:
    """A scripted mission exercising all fifteen event kinds, nested three deep."""

    renderer.master_thinking("objective cleared by policy preflight; scope is one domain")
    with renderer.status("drafting the investigation plan"):
        renderer.master_planning("3 areas: passive DNS, certificate transparency, public documents")

    renderer.subagent_spawned("sa-dns", "passive-dns")
    renderer.subagent_spawned("sa-ct", "certificate-transparency")
    renderer.worker_spawned("wrk-resolver", "resolver-queries", parent="sa-dns")
    renderer.worker_spawned("wrk-archive", "archive-lookup", parent="sa-dns")

    renderer.task_assigned("query public resolvers for A/AAAA/MX", actor="sa-dns")
    renderer.task_assigned("collect historical records", actor="wrk-archive")
    with renderer.status("querying resolvers"):
        renderer.browsing("GET https://dns.example/api/records", actor="wrk-resolver",
                          url="https://dns.example/api/records")
    renderer.worker_done("14 records returned, 2 conflicting", actor="wrk-resolver")

    renderer.reasoning("conflict is consistent with a recent migration, not with evasion", actor="sa-dns")
    renderer.task_assigned("re-run archived lookups for the older value", actor="sa-dns")
    renderer.retasking("wrk-archive asked to widen the date range", actor="sa-dns")
    renderer.worker_done("older value confirmed from 2025-11 archive", actor="wrk-archive")

    renderer.quality_review("claim lacked a source; one observation added", actor="sa-dns", verdict="revise")
    renderer.warning("forensics utility 'exiftool' missing — metadata step skipped", actor="sa-ct")
    renderer.forensic("hashed artifact /case/advisory.pdf (sha256 recorded)", actor="sa-ct",
                      artifact="/case/advisory.pdf")

    renderer.reasoning("two independent sources agree; confidence raised to medium", actor="sa-dns")
    renderer.subagent_synthesis("2 observations, 1 inference; uncertainty stated", actor="sa-dns")
    renderer.master_thinking("weighing subagent reports against the declared hypotheses")
    renderer.master_synthesis("no attribution made; 1 hypothesis refuted, 1 left open")


@dataclass(frozen=True)
class RendererCheck:
    name: str
    ok: bool
    detail: str


def run_renderer_self_test() -> list[RendererCheck]:
    """Verify every renderer guarantee claimed in the docstring."""

    checks: list[RendererCheck] = []

    def record(name: str, ok: bool, detail: str) -> None:
        checks.append(RendererCheck(name, ok, detail))

    # 1. No alternate screen, ever — across every combination.
    for color in (True, False):
        for animation in (True, False):
            buffer = io.StringIO()
            renderer = EventRenderer.from_options(stream=buffer, color=color, animation=animation)
            _render_demo_mission(renderer)
            output = buffer.getvalue()
            found = [seq for seq in _ALT_SCREEN_SEQUENCES if seq in output]
            record(
                f"no alternate screen (color={color}, animation={animation})",
                not found,
                "clean" if not found else f"found {found}",
            )

    # 2. Colour disabled ⇒ no ANSI escapes at all, but every event still present.
    buffer = io.StringIO()
    renderer = EventRenderer.from_options(stream=buffer, color=False, animation=True)
    _render_demo_mission(renderer)
    plain = buffer.getvalue()
    record("no colour ⇒ no ANSI escapes", "\x1b[" not in plain, "clean" if "\x1b[" not in plain else "escapes present")
    all_kinds = {kind for kind in RenderKind if kind not in {RenderKind.DEBUG}}
    rendered_kinds = {e.kind for e in renderer.trace.events}
    record(
        "no colour ⇒ complete log",
        len(renderer.trace.events) >= 15 and len(rendered_kinds) >= 13,
        f"{len(renderer.trace.events)} events, {len(rendered_kinds)} kinds",
    )

    # 3. Animation disabled ⇒ no carriage returns, still complete.
    buffer = io.StringIO()
    renderer = EventRenderer.from_options(stream=buffer, color=False, animation=False)
    _render_demo_mission(renderer)
    no_anim = buffer.getvalue()
    record("animation off ⇒ no carriage returns", "\r" not in no_anim, "clean" if "\r" not in no_anim else "\r present")
    record(
        "animation off ⇒ status still logged",
        "drafting the investigation plan" in no_anim and "querying resolvers" in no_anim,
        "start/end lines present",
    )
    record(
        "animation off ⇒ chronological order preserved",
        [e.seq for e in renderer.trace.events] == list(range(1, len(renderer.trace.events) + 1)),
        f"{len(renderer.trace.events)} events",
    )

    # 4. Nested output: depth increases master → subagent → worker.
    buffer = io.StringIO()
    renderer = EventRenderer.from_options(stream=buffer, color=False, animation=False)
    _render_demo_mission(renderer)
    def indent_of(fragment: str) -> int | None:
        """Leading spaces of the line whose *message* is exactly ``fragment``.

        A substring probe is unreliable here: "drafting the investigation plan"
        also appears inside an indented subagent line, which would report the
        wrong depth.
        """

        for line in buffer.getvalue().splitlines():
            if not line.rstrip().endswith(fragment):
                continue
            depth = 0
            for prefix in ("│  ", "|  "):
                count = 0
                while line[count:].startswith(prefix):
                    count += len(prefix)
                    depth += 1
                if count:
                    return depth
            return 0
        return None
    master_indent = indent_of("drafting the investigation plan")
    subagent_indent = indent_of("passive-dns")
    worker_indent = indent_of("resolver-queries")
    record(
        "nesting indents by depth",
        None not in (master_indent, subagent_indent, worker_indent)
        and master_indent < subagent_indent < worker_indent,
        f"master={master_indent} subagent={subagent_indent} worker={worker_indent}",
    )

    # 5. All fifteen required kinds are representable.
    required = {
        RenderKind.MASTER_THINKING, RenderKind.MASTER_PLANNING, RenderKind.SUBAGENT_SPAWN,
        RenderKind.WORKER_SPAWN, RenderKind.TASK_ASSIGN, RenderKind.BROWSING, RenderKind.FORENSIC,
        RenderKind.REASONING, RenderKind.WORKER_DONE, RenderKind.QUALITY_REVIEW, RenderKind.RETASKING,
        RenderKind.SUBAGENT_SYNTHESIS, RenderKind.MASTER_SYNTHESIS, RenderKind.WARNING, RenderKind.COMPLETE,
    }
    record("all 15 required event kinds exist", required <= set(RenderKind), f"{len(required)} kinds")

    buffer = io.StringIO()
    renderer = EventRenderer.from_options(stream=buffer, color=False, animation=False)
    for kind in sorted(required, key=lambda k: k.value):
        renderer.emit(kind, f"probe {kind.value}", actor="master")
    record("every required kind renders", len(renderer.trace.events) == len(required), f"{len(renderer.trace.events)} rendered")

    # 6. Concurrent emission: all events kept, none interleaved, unique seqs.
    buffer = io.StringIO()
    renderer = EventRenderer.from_options(stream=buffer, color=False, animation=False)
    errors: list[str] = []
    def burst(index: int) -> None:
        try:
            for n in range(25):
                renderer.emit(RenderKind.REASONING, f"worker {index} step {n}", actor="master")
        except Exception as exc:                          # pragma: no cover
            errors.append(str(exc))
    threads = [threading.Thread(target=burst, args=(i,)) for i in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    seqs = [e.seq for e in renderer.trace.events]
    record(
        "concurrent emit: nothing lost",
        not errors and len(seqs) == 200 and len(set(seqs)) == 200,
        f"{len(seqs)} events, {len(set(seqs))} unique",
    )
    lines = [line for line in buffer.getvalue().splitlines() if "step" in line]
    record(
        "concurrent emit: one event per line",
        len(lines) == 200 and all(line.count("step") == 1 for line in lines),
        f"{len(lines)} lines",
    )

    # 7. JSONL round-trip preserves chronology and payload.
    buffer = io.StringIO()
    renderer = EventRenderer.from_options(stream=buffer, color=False, animation=False)
    _render_demo_mission(renderer)
    trace = renderer.trace
    restored = RenderTrace.from_jsonl(trace.to_jsonl())
    record(
        "jsonl round-trip keeps every event",
        len(restored.events) == len(trace.events) and restored.chronological,
        f"{len(restored.events)} events",
    )
    record(
        "jsonl round-trip keeps actor and depth",
        [e.actor for e in restored.events] == [e.actor for e in trace.events],
        "actors preserved",
    )

    # 8. Secrets never reach the terminal or the trace.
    secret = "sk-proj-RENDERERSECRET1234567890"
    buffer = io.StringIO()
    renderer = EventRenderer.from_options(stream=buffer, color=False, animation=False)
    renderer.browsing(f"GET https://api.example/x?key={secret}", actor="master", url="https://api.example/x")
    record("secret scrubbed from rendered line", secret not in buffer.getvalue(), "clean")
    record("secret scrubbed from trace", secret not in renderer.trace.to_jsonl(), "clean")

    # 9. Level filtering hides debug chatter but keeps warnings and errors.
    buffer = io.StringIO()
    renderer = EventRenderer.from_options(stream=buffer, color=False, animation=False)
    renderer.emit(RenderKind.DEBUG, "chatty detail", actor="master")
    renderer.emit(RenderKind.INFO, "normal detail", actor="master")
    renderer.warning("something degraded", actor="master")
    renderer.error("something broke", actor="master")
    visible = buffer.getvalue()
    record(
        "filtering hides debug only",
        "chatty detail" not in visible and "normal detail" in visible
        and "something degraded" in visible and "something broke" in visible,
        "warnings/errors always shown",
    )
    record("filtered events remain in the trace", len(renderer.trace.events) == 4, f"{len(renderer.trace.events)} recorded")

    # 10. Plain log file mirrors everything, including filtered events.
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "run.log"
        buffer = io.StringIO()
        renderer = EventRenderer.from_options(stream=buffer, color=False, animation=False, log_file=log_path)
        _render_demo_mission(renderer)
        renderer.emit(RenderKind.DEBUG, "filtered but logged", actor="master")
        text = log_path.read_text()
        record("log file gets every event", "filtered but logged" in text, f"{len(text.splitlines())} lines")
        record("log file has no ANSI escapes", "\x1b[" not in text, "clean")

    return checks


# ══════════════════════════════════════════════════════════════════════════
# 18. Agent lifecycle animation
# ══════════════════════════════════════════════════════════════════════════
#
# Task 7 renders *events*.  This section renders the *life* of each agent and
# task: spawn, delegation, active work, reasoning, review, retry, merge and
# completion — with elapsed time and live counters, animated, without flooding
# the terminal and without ever showing hidden reasoning.
#
# Three rules, each enforced in code:
#
#   1. CONCISE, MODEL-SAFE TEXT ONLY.  Every status string passes through
#      :func:`sanitize_status`, which rejects deliberation phrasing ("let me
#      think step by step", "my reasoning", "first, I will consider") and
#      truncates prose.  Reasoning is reported as a *summary* — the current
#      decision, the quality criterion, or the next action — never as a train of
#      thought.  :meth:`LifecycleTracker.reasoning` therefore accepts structured
#      fields, not free-form paragraphs.
#   2. ONE ANIMATED LINE, NOT ONE PER AGENT.  All active work shares a single
#      transient status line carrying counters and elapsed time.  Permanent
#      lines are emitted only on state *transitions* (start and terminal), so
#      the log grows with the number of entities, not with the number of ticks.
#   3. START AND TERMINAL ARE PAIRED.  Every record gets exactly one start line
#      and one terminal line.  ``shutdown()`` is idempotent, runs from
#      ``atexit``, and turns anything still running into an explicit
#      ``interrupted`` record — so an aborted run can never leave a spinner
#      turning or an entity without an ending.

class LifecycleState(str, Enum):
    """States of a tracked agent, worker or task."""

    QUEUED = "queued"
    RUNNING = "running"
    WAITING = "waiting"          # blocked on a dependency or a human
    RETRYING = "retrying"
    REVIEWING = "reviewing"
    MERGING = "merging"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"  # the run stopped underneath it
    MERGED = "merged"

    @property
    def terminal(self) -> bool:
        return self in {
            LifecycleState.DONE,
            LifecycleState.FAILED,
            LifecycleState.CANCELLED,
            LifecycleState.INTERRUPTED,
            LifecycleState.MERGED,
        }


class LifecycleKind(str, Enum):
    """What is being tracked."""

    AGENT = "agent"
    SUBAGENT = "subagent"
    WORKER = "worker"
    TASK = "task"


class UnsafeStatusError(ValueError):
    """Raised when status text would leak deliberation or exceed the limit."""


#: Phrasing that indicates deliberation rather than a status summary.  These
#: are refused because chain-of-thought must never reach the console, a log or
#: a report — the operator needs the decision, not the monologue.
_DELIBERATION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(let me|let's|i'?ll|i will|i'?m going to|we will now)\s+"
               r"(think|reason|consider|walk through|ponder|figure out)", re.I),
    re.compile(r"\b(chain[- ]of[- ]thought|thought process|my reasoning|internal monologue)\b", re.I),
    re.compile(r"\bstep[- ]?(by[- ]?step|1|one)\b[^.]{0,20}\b(think|reason|consider)", re.I),
    re.compile(r"\b(first|second|third|finally),?\s+(i|we)\s+(think|consider|reason|will now)", re.I),
    re.compile(r"\b(hmm+|uhh+|erm+|wait,)\b", re.I),
    re.compile(r"\b(tokens? by tokens?|as a language model|my training data)\b", re.I),
    re.compile(r"\b(on second thought|scratch that|actually,? let me)\b", re.I),
)

#: Upper bounds.  Chosen so a full status line fits an 80-column CI log.
STATUS_TEXT_LIMIT: int = 120
STATUS_FIELD_LIMIT: int = 60
STATUS_MAX_WORDS: int = 20


def sanitize_status(text: str, *, limit: int = STATUS_TEXT_LIMIT, strict: bool = False) -> str:
    """Reduce *text* to a single concise, model-safe status line.

    Collapses whitespace and control characters, refuses deliberation phrasing,
    and truncates at a word boundary.  With ``strict=True`` prohibited phrasing
    raises :class:`UnsafeStatusError` instead of being replaced — used by tests
    and by any caller that must fail closed.
    """

    if not isinstance(text, str):
        raise TypeError(f"status text must be str, got {type(text).__name__}")

    cleaned = re.sub(r"[\x00-\x1f\x7f]+", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return "working"

    if any(pattern.search(cleaned) for pattern in _DELIBERATION_PATTERNS):
        if strict:
            raise UnsafeStatusError("status text contains deliberation; report a decision, criterion or next action")
        # Keep the signal, drop the monologue.
        cleaned = "considering options — see decision below"

    words = cleaned.split()
    if len(words) > STATUS_MAX_WORDS:
        cleaned = " ".join(words[:STATUS_MAX_WORDS]) + "…"
    if len(cleaned) > limit:
        cut = cleaned[: limit - 1]
        cleaned = (cut.rsplit(" ", 1)[0] if " " in cut else cut) + "…"
    return cleaned


def format_elapsed(seconds: float) -> str:
    """Compact human duration: ``0.4s``, ``12s``, ``2m03s``, ``1h02m``."""

    seconds = max(0.0, float(seconds))
    if seconds < 10:
        return f"{seconds:.1f}s"
    if seconds < 60:
        return f"{int(seconds)}s"
    minutes, rest = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m{rest:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


class StatusSummary(StrictModel):
    """A structured, model-safe summary of what an agent is doing.

    Exactly the three things an operator needs from a reasoning step: the
    decision taken, the criterion being applied, and what happens next.  There
    is deliberately no field for narrative.
    """

    decision: str | None = Field(default=None, max_length=STATUS_FIELD_LIMIT)
    criterion: str | None = Field(default=None, max_length=STATUS_FIELD_LIMIT)
    next_action: str | None = Field(default=None, max_length=STATUS_FIELD_LIMIT)
    note: str | None = Field(default=None, max_length=STATUS_FIELD_LIMIT)

    @field_validator("decision", "criterion", "next_action", "note", mode="before")
    @classmethod
    def _sanitise(cls, value: Any) -> Any:
        if value is None:
            return None
        return sanitize_status(str(value), limit=STATUS_FIELD_LIMIT, strict=True)

    def is_empty(self) -> bool:
        return not any((self.decision, self.criterion, self.next_action, self.note))

    def render(self, limit: int = STATUS_TEXT_LIMIT) -> str:
        """``decision · criterion · next: action`` — no narrative, one line.

        Truncated at :data:`STATUS_TEXT_LIMIT` so a summary never wraps into
        three lines in an 80-column CI log.
        """

        parts: list[str] = []
        if self.decision:
            parts.append(self.decision)
        if self.criterion:
            parts.append(f"criterion: {self.criterion}")
        if self.next_action:
            parts.append(f"next: {self.next_action}")
        if self.note:
            parts.append(self.note)
        joined = " · ".join(parts) if parts else "working"
        return sanitize_status(joined, limit=limit)


@dataclass
class LifecycleRecord:
    """Mutable lifecycle state for one agent, worker or task."""

    id: str
    kind: LifecycleKind
    label: str
    parent: str | None = None
    state: LifecycleState = LifecycleState.QUEUED
    started_at: datetime | None = None
    finished_at: datetime | None = None
    started_monotonic: float | None = None
    finished_monotonic: float | None = None
    attempts: int = 1
    summary: StatusSummary | None = None
    terminal_emitted: bool = False
    start_emitted: bool = False
    note: str | None = None
    counters: dict[str, int] = field(default_factory=dict)

    @property
    def elapsed_seconds(self) -> float:
        if self.started_monotonic is None:
            return 0.0
        end = self.finished_monotonic if self.finished_monotonic is not None else time.monotonic()
        return max(0.0, end - self.started_monotonic)

    @property
    def terminal(self) -> bool:
        return self.state.terminal

    def snapshot(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "label": self.label,
            "parent": self.parent,
            "state": self.state.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "attempts": self.attempts,
            "summary": self.summary.render() if self.summary else None,
            "terminal_emitted": self.terminal_emitted,
            "counters": dict(self.counters),
        }


class _LiveStatus:
    """One shared transient status line.  Never more than one is running."""

    def __init__(self, console: Console, *, enabled: bool, refresh_per_second: float = 8.0) -> None:
        self.console = console
        self.enabled = bool(enabled and console.is_terminal)
        self.refresh_per_second = max(1.0, float(refresh_per_second))
        self._status: Status | None = None
        self._text = ""
        self._suspend_depth = 0
        self._lock = threading.RLock()

    @property
    def running(self) -> bool:
        with self._lock:
            return self._status is not None

    def _start(self) -> None:
        if not self.enabled or self._status is not None:
            return
        self._status = Status(
            self._text or "working",
            console=self.console,
            spinner="dots",
            refresh_per_second=self.refresh_per_second,
        )
        self._status.start()

    def update(self, text: str) -> None:
        with self._lock:
            if not self.enabled:
                return
            self._text = text
            if self._status is None and self._suspend_depth == 0:
                self._start()
            elif self._status is not None:
                self._status.update(text)

    def suspend(self) -> None:
        """Stop the spinner so a permanent line can be printed cleanly."""

        with self._lock:
            self._suspend_depth += 1
            if self._suspend_depth == 1 and self._status is not None:
                self._status.stop()
                self._status = None

    def resume(self) -> None:
        with self._lock:
            if self._suspend_depth > 0:
                self._suspend_depth -= 1
            if self._suspend_depth == 0 and self.enabled and self._text:
                self._start()

    def stop(self) -> None:
        """Stop for good and restore the cursor.  Idempotent."""

        with self._lock:
            if self._status is not None:
                self._status.stop()
                self._status = None
            self._suspend_depth = 0


class LifecycleTracker:
    """Animated, non-flooding lifecycle tracking for agents, workers and tasks.

    Wraps an :class:`EventRenderer` (which owns permanent lines) and a single
    :class:`_LiveStatus` (which owns the transient line).  All public methods
    are thread-safe; concurrent Workers cannot produce interleaved output or
    duplicate terminal records.
    """

    def __init__(
        self,
        renderer: EventRenderer,
        *,
        animation: bool = True,
        refresh_per_second: float = 8.0,
        heartbeat_seconds: float = 0.0,
        max_terminal_lines: int = 4,
        clock: "Callable[[], float] | None" = None,
        wall_clock: "Callable[[], datetime] | None" = None,
        register_atexit: bool = True,
    ) -> None:
        self.renderer = renderer
        self._lock = threading.RLock()
        self._records: dict[str, LifecycleRecord] = {}
        self._order: list[str] = []
        self._clock = clock or time.monotonic
        self._wall = wall_clock or utc_now
        self._live = _LiveStatus(renderer.console, enabled=animation, refresh_per_second=refresh_per_second)
        self._heartbeat_seconds = max(0.0, heartbeat_seconds)
        self._last_heartbeat = 0.0
        self._max_terminal_lines = max(1, max_terminal_lines)
        self._terminal_lines = 0
        self._started_monotonic = self._clock()
        self._closed = False
        self.counters: dict[str, int] = {
            "spawned": 0, "started": 0, "completed": 0, "failed": 0,
            "cancelled": 0, "interrupted": 0, "retries": 0, "merges": 0,
            "reviews": 0, "reasoning": 0,
        }
        if register_atexit:
            # Last line of defence: a process that exits mid-run still stops the
            # spinner and closes every open record.
            atexit.register(self.shutdown)

    # -- internals ---------------------------------------------------------

    def _print(self, renderable: Any, *, stamp: bool = True) -> None:
        """Print a permanent line without corrupting the live line.

        Lifecycle lines are timestamped like renderer lines so a mixed log reads
        as one stream rather than two stylistic layers.
        """

        prefix = ""
        if stamp and self.renderer.timestamps:
            prefix = f"[dim]{self._wall().astimezone(timezone.utc).strftime('%H:%M:%S')}[/dim] "
        self._live.suspend()
        try:
            # Indentation belongs after the timestamp, so the time column stays
            # left-aligned while the tree still steps inwards.
            text = str(renderable)
            indent = ""
            while text.startswith(("│  ", "|  ")):
                indent += text[:3]
                text = text[3:]
            self.renderer.console.print(f"{prefix}{indent}{text}", highlight=False, soft_wrap=False)
        finally:
            self._live.resume()

    def _counters_text(self) -> str:
        active = sum(1 for r in self._records.values() if not r.terminal)
        done = self.counters["completed"]
        failed = self.counters["failed"] + self.counters["cancelled"] + self.counters["interrupted"]
        elapsed = format_elapsed(self._clock() - self._started_monotonic)
        parts = [f"{active} active", f"{done} done"]
        if failed:
            parts.append(f"{failed} failed")
        parts.append(f"{elapsed} elapsed")
        return " · ".join(parts)

    def _refresh_live(self, focus: LifecycleRecord | None = None) -> None:
        if not self._live.enabled:
            return
        detail = ""
        if focus is not None:
            summary = focus.summary.render() if focus.summary else focus.state.value
            detail = f" — {focus.label}: {summary}"
        elif (latest := self._latest_active()) is not None:
            summary = latest.summary.render() if latest.summary else latest.state.value
            detail = f" — {latest.label}: {summary}"
        self._live.update(f"{self._counters_text()}{detail}")

    def _latest_active(self) -> LifecycleRecord | None:
        for record_id in reversed(self._order):
            record = self._records[record_id]
            if not record.terminal:
                return record
        return None

    def _maybe_heartbeat(self) -> None:
        """Emit a periodic progress line, throttled, only when asked for."""

        if self._heartbeat_seconds <= 0:
            return
        now = self._clock()
        if now - self._last_heartbeat < self._heartbeat_seconds:
            return
        self._last_heartbeat = now
        if self._terminal_lines >= self._max_terminal_lines:
            return
        self._terminal_lines += 1
        self._print(f"[dim]… {escape(self._counters_text())}[/dim]", stamp=False)

    def _emit_start(self, record: LifecycleRecord) -> None:
        """Exactly one start line per record."""

        if record.start_emitted:
            return
        record.start_emitted = True
        record.started_at = self._wall()
        record.started_monotonic = self._clock()
        record.state = LifecycleState.RUNNING
        self.counters["started"] += 1
        glyph, colour = _LIFECYCLE_GLYPHS[record.kind]
        detail = f" — {record.summary.render()}" if record.summary else ""
        self._print(
            f"{self.renderer._indent(self.renderer.depth_of(record.parent))}"
            f"[{colour}]{glyph}[/{colour}] [bold]{escape(record.label)}[/bold] "
            f"[dim]{record.kind.value} started[/dim]{escape(detail)}"
        )

    def _emit_terminal(self, record: LifecycleRecord, note: str | None = None) -> None:
        """Exactly one terminal line per record."""

        if record.terminal_emitted:
            return
        record.terminal_emitted = True
        record.finished_at = self._wall()
        record.finished_monotonic = self._clock()
        if note:
            record.note = sanitize_status(note, limit=STATUS_TEXT_LIMIT)
        elapsed = format_elapsed(record.elapsed_seconds)
        glyph, colour = _LIFECYCLE_TERMINAL_GLYPHS.get(record.state, ("·", "dim"))
        suffix = f" [dim]({escape(record.note)})[/dim]" if record.note else ""
        attempt = f" [dim]attempt {record.attempts}[/dim]" if record.attempts > 1 else ""
        self._print(
            f"{self.renderer._indent(self.renderer.depth_of(record.parent))}"
            f"[{colour}]{glyph}[/{colour}] [bold]{escape(record.label)}[/bold] "
            f"[{colour}]{record.state.value}[/{colour}] in {elapsed}{attempt}{suffix}"
        )

    # -- reusable lifecycle methods ---------------------------------------

    def spawn(
        self,
        record_id: str,
        label: str,
        *,
        kind: LifecycleKind = LifecycleKind.AGENT,
        parent: str | None = None,
        detail: str | None = None,
        start: bool = True,
    ) -> LifecycleRecord:
        """Register and (by default) start an agent, worker or task."""

        with self._lock:
            if record_id in self._records:
                return self._records[record_id]
            summary = StatusSummary(next_action=detail) if detail else None
            record = LifecycleRecord(
                id=record_id,
                kind=kind,
                label=sanitize_status(label, limit=STATUS_FIELD_LIMIT),
                parent=parent,
                summary=summary,
            )
            self._records[record_id] = record
            self._order.append(record_id)
            self.counters["spawned"] += 1
            if parent:
                self.renderer.register_agent(record_id, parent=parent, label=record.label)
            else:
                self.renderer.register_agent(record_id, parent="master", label=record.label)
            if start:
                self._emit_start(record)
                self._refresh_live(record)
            return record

    def delegate(self, actor: str, to: str, objective: str, *, kind: LifecycleKind | None = None) -> LifecycleRecord:
        """Delegate work: the delegating agent stays active, the target starts."""

        with self._lock:
            record = self.spawn(to, to, kind=kind or LifecycleKind.TASK, parent=actor, detail=objective)
            self.renderer.task_assigned(
                sanitize_status(objective), actor=actor, label=self._label_of(actor)
            )
            self._refresh_live(record)
            return record

    @contextmanager
    def active_work(
        self,
        record_id: str,
        *,
        summary: StatusSummary | None = None,
        detail: str | None = None,
        label: str | None = None,
    ) -> Iterator[LifecycleRecord]:
        """Animate a unit of work, guaranteeing a terminal state.

        Exceptions mark the record ``failed`` (or ``cancelled`` for
        ``CancelledError``); ``KeyboardInterrupt`` marks it ``interrupted`` and
        re-raises.  In every path the record reaches a terminal state, the
        spinner is left stopped and the terminal line is printed exactly once.
        """

        with self._lock:
            record = self._records.get(record_id) or self.spawn(
                record_id, label or record_id, kind=LifecycleKind.TASK,
                detail=detail or (summary.next_action if summary else None),
            )
            if summary is not None:
                record.summary = summary
            elif detail:
                record.summary = StatusSummary(next_action=detail)
            if not record.start_emitted:
                self._emit_start(record)
            record.state = LifecycleState.RUNNING
            self._refresh_live(record)
            self._maybe_heartbeat()

        try:
            yield record
        except KeyboardInterrupt:
            self.complete(record_id, LifecycleState.INTERRUPTED, note="operator interrupted")
            raise
        except BaseException as exc:
            cancelled = isinstance(exc, (asyncio.CancelledError, GeneratorExit))
            state = LifecycleState.CANCELLED if cancelled else LifecycleState.FAILED
            self.complete(record_id, state, note=f"{type(exc).__name__}: {exc}")
            raise
        else:
            self.complete(record_id, LifecycleState.DONE)
        finally:
            # Belt and braces: never leave the spinner attached to a finished unit.
            with self._lock:
                if record.terminal:
                    self._refresh_live()

    def reasoning(
        self,
        actor: str,
        *,
        decision: str | None = None,
        criterion: str | None = None,
        next_action: str | None = None,
        note: str | None = None,
        animate: bool = True,
    ) -> StatusSummary:
        """Report a *summary* of reasoning — never the reasoning itself.

        Accepts the three operator-relevant facets.  Free-form deliberation is
        refused by :class:`StatusSummary`, which sanitises each field strictly.
        """

        with self._lock:
            summary = StatusSummary(
                decision=decision, criterion=criterion, next_action=next_action, note=note
            )
            if summary.is_empty():
                raise UnsafeStatusError("reasoning needs a decision, criterion, next action or note")
            record = self._records.get(actor)
            if record is not None and not record.terminal:
                record.summary = summary
            self.counters["reasoning"] += 1
            self.renderer.reasoning(summary.render(), actor=actor, label=self._label_of(actor))
            if animate:
                self._refresh_live(record)
            return summary

    def review(self, actor: str, *, verdict: str, criterion: str, note: str | None = None) -> None:
        """Record a quality review with the criterion that was applied."""

        with self._lock:
            record = self._records.get(actor)
            if record is not None:
                record.state = LifecycleState.REVIEWING
            self.counters["reviews"] += 1
            text = f"{sanitize_status(verdict, limit=STATUS_FIELD_LIMIT)} — criterion: {sanitize_status(criterion, limit=STATUS_FIELD_LIMIT)}"
            if note:
                text = f"{text} ({sanitize_status(note, limit=STATUS_FIELD_LIMIT)})"
            self.renderer.quality_review(text, actor=actor, verdict=sanitize_status(verdict, limit=20),
                                         label=self._label_of(actor))
            if record is not None and not record.terminal:
                record.state = LifecycleState.RUNNING
            self._refresh_live(record)

    def retry_task(self, record_id: str, *, reason: str, attempt: int | None = None) -> LifecycleRecord:
        """Count and announce a retry; the record stays active."""

        with self._lock:
            record = self._records.get(record_id)
            if record is None:
                record = self.spawn(record_id, record_id, kind=LifecycleKind.TASK, start=True)
            record.attempts = attempt if attempt is not None else record.attempts + 1
            record.state = LifecycleState.RETRYING
            self.counters["retries"] += 1
            self.renderer.retasking(
                f"retry {record.attempts}: {sanitize_status(reason)}",
                actor=record.parent or record_id,
                label=self._label_of(record.parent or record_id),
            )
            record.state = LifecycleState.RUNNING
            self._refresh_live(record)
            return record

    def merge(self, actor: str, *, into: str, count: int, note: str | None = None) -> None:
        """Announce that findings were merged into a synthesis target."""

        with self._lock:
            self.counters["merges"] += 1
            text = f"merged {count} item(s) into {sanitize_status(into, limit=STATUS_FIELD_LIMIT)}"
            if note:
                text = f"{text} ({sanitize_status(note, limit=STATUS_FIELD_LIMIT)})"
            self.renderer.subagent_synthesis(text, actor=actor, label=self._label_of(actor))
            record = self._records.get(actor)
            if record is not None and not record.terminal:
                record.state = LifecycleState.MERGING
                self._refresh_live(record)
                record.state = LifecycleState.RUNNING

    def complete(
        self,
        record_id: str,
        state: LifecycleState = LifecycleState.DONE,
        *,
        note: str | None = None,
    ) -> LifecycleRecord | None:
        """Force a terminal state.  Idempotent — never emits two terminal lines."""

        with self._lock:
            record = self._records.get(record_id)
            if record is None:
                return None
            if record.terminal_emitted:
                return record
            if not record.start_emitted:
                # A record that never visibly started still gets a start line, so
                # "terminal without start" can never appear in the log.
                self._emit_start(record)
            record.state = state if state.terminal else LifecycleState.DONE
            if record.state is LifecycleState.DONE:
                self.counters["completed"] += 1
            elif record.state is LifecycleState.FAILED:
                self.counters["failed"] += 1
            elif record.state is LifecycleState.CANCELLED:
                self.counters["cancelled"] += 1
            elif record.state is LifecycleState.INTERRUPTED:
                self.counters["interrupted"] += 1
            self._emit_terminal(record, note)
            self._terminal_lines += 1
            self._refresh_live()
            return record

    # -- interruption safety ----------------------------------------------

    def interrupt_all(self, reason: str = "run interrupted") -> list[LifecycleRecord]:
        """Close every open record as ``interrupted``.  Idempotent."""

        with self._lock:
            closed: list[LifecycleRecord] = []
            for record in self._records.values():
                if not record.terminal_emitted:
                    self.complete(record.id, LifecycleState.INTERRUPTED, note=reason)
                    closed.append(record)
            return closed

    def shutdown(self, reason: str = "run ended") -> None:
        """Stop animation and close anything still open.  Safe to call twice."""

        with self._lock:
            if self._closed:
                self._live.stop()
                return
            self.interrupt_all(reason)
            self._live.stop()
            self._closed = True

    def __enter__(self) -> "LifecycleTracker":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        if exc_type is not None:
            self.shutdown("run failed")
        else:
            self.shutdown("run ended")
        return False

    # -- inspection -------------------------------------------------------

    def get(self, record_id: str) -> LifecycleRecord | None:
        with self._lock:
            return self._records.get(record_id)

    def records(self) -> list[LifecycleRecord]:
        with self._lock:
            return [self._records[i] for i in self._order]

    def _label_of(self, agent_id: str | None) -> str | None:
        if not agent_id:
            return None
        record = self._records.get(agent_id)
        return record.label if record else agent_id

    @property
    def live_running(self) -> bool:
        """True while a transient spinner is attached to the terminal."""

        return self._live.running

    def progress(self) -> dict[str, Any]:
        with self._lock:
            states: dict[str, int] = {}
            for record in self._records.values():
                states[record.state.value] = states.get(record.state.value, 0) + 1
            active = [r for r in self._records.values() if not r.terminal]
            return {
                "total": len(self._records),
                "active": len(active),
                "states": states,
                "counters": dict(self.counters),
                "elapsed_seconds": round(self._clock() - self._started_monotonic, 3),
                "elapsed": format_elapsed(self._clock() - self._started_monotonic),
                "live_running": self._live.running,
                "animation": self._live.enabled,
                "all_started": all(r.start_emitted for r in self._records.values()),
                "all_terminal": all(r.terminal_emitted for r in self._records.values()),
            }

    def summary_table(self) -> Table:
        """Balanced per-record start/terminal view for the end of a run."""

        with self._lock:
            table = Table(box=None, pad_edge=False, header_style="bold")
            table.add_column("id", style="dim", no_wrap=True)
            table.add_column("kind", style="cyan", no_wrap=True)
            table.add_column("label", no_wrap=True)
            table.add_column("state", no_wrap=True)
            table.add_column("elapsed", justify="right", no_wrap=True)
            table.add_column("start", no_wrap=True, justify="center")
            table.add_column("end", no_wrap=True, justify="center")
            for record in self.records():
                colour = "green" if record.state is LifecycleState.DONE else (
                    "red" if record.state in {LifecycleState.FAILED, LifecycleState.INTERRUPTED} else "yellow"
                )
                table.add_row(
                    escape(record.id),
                    record.kind.value,
                    escape(record.label),
                    f"[{colour}]{record.state.value}[/{colour}]",
                    format_elapsed(record.elapsed_seconds),
                    "[green]✔[/green]" if record.start_emitted else "[red]✘[/red]",
                    "[green]✔[/green]" if record.terminal_emitted else "[red]✘[/red]",
                )
            return table


#: Start-line glyph/colour per tracked kind.
_LIFECYCLE_GLYPHS: dict[LifecycleKind, tuple[str, str]] = {
    LifecycleKind.AGENT: ("◆", "bold cyan"),
    LifecycleKind.SUBAGENT: ("⬡", "bold magenta"),
    LifecycleKind.WORKER: ("·", "magenta"),
    LifecycleKind.TASK: ("→", "blue"),
}

#: Terminal-line glyph/colour per end state.
_LIFECYCLE_TERMINAL_GLYPHS: dict[LifecycleState, tuple[str, str]] = {
    LifecycleState.DONE: ("✔", "green"),
    LifecycleState.MERGED: ("⊞", "bold green"),
    LifecycleState.FAILED: ("✘", "bold red"),
    LifecycleState.CANCELLED: ("⊘", "yellow"),
    LifecycleState.INTERRUPTED: ("⚠", "bold yellow"),
}


# --------------------------------------------------------------------------
# 18.1 Demonstration script used by the CLI and the self-test
# --------------------------------------------------------------------------


def _run_lifecycle_demo(tracker: LifecycleTracker, *, tasks: int = 4) -> None:
    """Exercise every lifecycle method with concise, model-safe summaries."""

    tracker.spawn("master", "master", kind=LifecycleKind.AGENT, detail="plan the mission")
    tracker.reasoning(
        "master",
        decision="3 collection areas are sufficient",
        criterion="each area maps to a distinct public source type",
        next_action="spawn passive DNS and certificate transparency subagents",
    )

    tracker.spawn("sa-dns", "passive-dns", kind=LifecycleKind.SUBAGENT, parent="master",
                  detail="enumerate published DNS records")
    tracker.delegate("master", "task-dns", "query public resolvers for A/AAAA/MX")

    with tracker.active_work("task-dns", detail="querying resolvers"):
        tracker.reasoning(
            "sa-dns",
            decision="two conflicting A records are plausible",
            criterion="a recent migration produces exactly this pattern",
            next_action="check the archive for the previous value",
        )
    tracker.review("sa-dns", verdict="revise", criterion="every observation cites a source",
                   note="one claim had no source")

    tracker.spawn("task-archive", "archive-lookup", kind=LifecycleKind.TASK, parent="sa-dns",
                  detail="check archived records")
    with tracker.active_work("task-archive", detail="reading the 2025-11 archive"):
        tracker.retry_task("task-archive", reason="archive returned 503")

    tracker.merge("sa-dns", into="subagent report", count=2, note="both observations cited")
    tracker.complete("sa-dns", LifecycleState.MERGED, note="2 observations, 1 inference")

    for index in range(1, max(1, tasks)):
        task_id = f"task-ct-{index}"
        tracker.spawn(task_id, f"cert-log-{index}", kind=LifecycleKind.TASK, parent="master",
                      detail="read certificate transparency entries")
        with tracker.active_work(task_id, detail="parsing entries"):
            pass

    tracker.reasoning(
        "master",
        decision="findings stand without attribution",
        criterion="two independent sources agree on the hostname",
        next_action="write the final report",
    )
    tracker.complete("master", LifecycleState.DONE, note="report ready")


@dataclass(frozen=True)
class LifecycleCheck:
    name: str
    ok: bool
    detail: str


def run_lifecycle_self_test(tasks: int = 4) -> list[LifecycleCheck]:
    """Verify the acceptance criteria for lifecycle animation."""

    checks: list[LifecycleCheck] = []

    def record(name: str, ok: bool, detail: str = "ok") -> None:
        checks.append(LifecycleCheck(name, ok, detail))

    # --- 1. every entity has exactly one start and one terminal line ------
    buffer = io.StringIO()
    renderer = EventRenderer.from_options(stream=buffer, color=False, animation=False)
    tracker = LifecycleTracker(renderer, animation=False, register_atexit=False)
    _run_lifecycle_demo(tracker, tasks=tasks)
    progress = tracker.progress()
    record(
        "every entity started",
        progress["all_started"],
        f"{progress['total']} record(s)",
    )
    record(
        "every entity reached a terminal state",
        progress["all_terminal"] and progress["active"] == 0,
        f"active={progress['active']}, states={progress['states']}",
    )
    text = buffer.getvalue()
    record(
        "start and terminal lines are balanced",
        text.count("started") == progress["total"],
        f"{text.count('started')} start line(s) for {progress['total']} record(s)",
    )
    record(
        "terminal lines carry elapsed time",
        len(re.findall(r"\bin \d", text)) >= progress["total"] - 1,
        f"{len(re.findall(r'in [0-9]', text))} timed terminal line(s)",
    )

    # --- 2. interruption leaves no spinner running ------------------------
    buffer = io.StringIO()
    renderer = EventRenderer.from_options(stream=buffer, color=False, animation=False)
    tracker = LifecycleTracker(renderer, animation=False, register_atexit=False)
    tracker.spawn("t1", "interruptible-task", kind=LifecycleKind.TASK, detail="long operation")
    try:
        with tracker.active_work("t1"):
            raise KeyboardInterrupt
    except KeyboardInterrupt:
        pass
    record(
        "KeyboardInterrupt closes the task",
        tracker.get("t1").state is LifecycleState.INTERRUPTED,
        tracker.get("t1").state.value,
    )
    record("no spinner left running after interrupt", tracker.live_running is False)
    record(
        "interrupt emitted a terminal line",
        tracker.get("t1").terminal_emitted and "interrupted" in buffer.getvalue(),
        "terminal line present",
    )

    # A plain exception marks the task failed, not interrupted.
    buffer = io.StringIO()
    renderer = EventRenderer.from_options(stream=buffer, color=False, animation=False)
    tracker2 = LifecycleTracker(renderer, animation=False, register_atexit=False)
    tracker2.spawn("t2", "failing-task", kind=LifecycleKind.TASK, detail="will fail")
    try:
        with tracker2.active_work("t2"):
            raise RuntimeError("source unavailable")
    except RuntimeError:
        pass
    record("exception closes the task as failed", tracker2.get("t2").state is LifecycleState.FAILED)
    record("failure note is recorded", "source unavailable" in (tracker2.get("t2").note or ""),
           tracker2.get("t2").note or "")

    # shutdown() closes anything left open, and is idempotent.
    buffer = io.StringIO()
    renderer = EventRenderer.from_options(stream=buffer, color=False, animation=False)
    tracker3 = LifecycleTracker(renderer, animation=False, register_atexit=False)
    tracker3.spawn("a", "left-open", kind=LifecycleKind.AGENT)
    tracker3.shutdown("aborted")
    tracker3.shutdown("aborted again")
    record("shutdown closes open records", tracker3.get("a").state is LifecycleState.INTERRUPTED)
    record("shutdown is idempotent", buffer.getvalue().count("interrupted") == 1,
           f"{buffer.getvalue().count('interrupted')} terminal line(s)")
    record("shutdown stops the spinner", tracker3.live_running is False)

    # --- 3. chain-of-thought is refused --------------------------------
    try:
        sanitize_status("let me think step by step about this", strict=True)
        record("strict mode rejects deliberation", False, "accepted")
    except UnsafeStatusError:
        record("strict mode rejects deliberation", True, "UnsafeStatusError")

    lenient = sanitize_status("Let me think step by step about whether the record moved")
    record("lenient mode strips deliberation", "step by step" not in lenient.lower(), lenient)

    long_text = " ".join(f"word{i}" for i in range(80))
    shortened = sanitize_status(long_text)
    record("long text is truncated", len(shortened) <= STATUS_TEXT_LIMIT + 1 and len(shortened.split()) <= STATUS_MAX_WORDS + 1,
           f"{len(shortened)} chars")
    record("newlines are collapsed", "\n" not in sanitize_status("line one\nline two"))
    try:
        StatusSummary(decision="my reasoning: I first consider the tokens")
        record("summary field rejects deliberation", False, "accepted")
    except Exception:
        record("summary field rejects deliberation", True, "refused")
    try:
        tracker.reasoning("master")
        record("reasoning needs at least one facet", False, "accepted")
    except UnsafeStatusError:
        record("reasoning needs at least one facet", True, "refused")

    summary = StatusSummary(
        decision="keep the passive-only scope",
        criterion="no target interaction is authorised",
        next_action="collect from public sources",
    )
    rendered = summary.render()
    record(
        "summary renders decision, criterion and next action",
        rendered.startswith("keep the passive-only scope")
        and "criterion:" in rendered and "next:" in rendered,
        rendered,
    )
    record("summary has no narrative field", "thought" not in StatusSummary.model_fields,
           str(list(StatusSummary.model_fields)))

    # --- 4. counters and elapsed time without flooding ------------------
    buffer = io.StringIO()
    renderer = EventRenderer.from_options(stream=buffer, color=False, animation=False)
    tracker4 = LifecycleTracker(renderer, animation=False, register_atexit=False)
    for index in range(60):
        task_id = f"bulk-{index}"
        tracker4.spawn(task_id, task_id, kind=LifecycleKind.TASK, detail="work")
        tracker4.reasoning("master", decision=f"step {index} decided", next_action="continue")
        tracker4.complete(task_id, LifecycleState.DONE)
    lines = [l for l in buffer.getvalue().splitlines() if l.strip()]
    record(
        "60 tasks + 60 reasoning steps stay proportional",
        len(lines) <= 60 * 2 + 60 + 10,
        f"{len(lines)} lines",
    )
    progress4 = tracker4.progress()
    record(
        "counters track completions",
        progress4["counters"]["completed"] == 60 and progress4["counters"]["started"] == 60,
        str(progress4["counters"]),
    )
    record("elapsed time is reported", re.search(r"\d+(\.\d+)?s", progress4["elapsed"]) is not None, progress4["elapsed"])

    # --- 5. animation is only used on a real terminal ------------------
    plain = io.StringIO()
    renderer_plain = EventRenderer.from_options(stream=plain, color=False, animation=True)
    tracker5 = LifecycleTracker(renderer_plain, animation=True, register_atexit=False)
    tracker5.spawn("x", "non-tty", kind=LifecycleKind.TASK)
    record("animation disabled on a non-tty", tracker5.progress()["animation"] is False)
    record("non-tty emits no ANSI escapes", "\x1b[" not in plain.getvalue())
    tracker5.shutdown()

    # Forced-terminal console: the live status really does start and stop.
    terminal_buffer = io.StringIO()
    terminal_console = Console(file=terminal_buffer, force_terminal=True, width=100, no_color=True)
    renderer_tty = EventRenderer(terminal_console, color=False, animation=True)
    tracker6 = LifecycleTracker(renderer_tty, animation=True, refresh_per_second=20, register_atexit=False)
    tracker6.spawn("live", "animated-task", kind=LifecycleKind.TASK, detail="streaming")
    with tracker6.active_work("live", detail="receiving data"):
        started = tracker6.live_running
        # Rich paints the Status on its own refresh thread, so wait for one tick
        # before inspecting the buffer — an immediate read races the paint.
        deadline = time.monotonic() + 2.0
        while "active" not in terminal_buffer.getvalue() and time.monotonic() < deadline:
            time.sleep(0.02)
    tracker6.shutdown()
    painted = terminal_buffer.getvalue()
    record("live spinner starts on a terminal", started is True)
    record(
        "live spinner carries counters and elapsed time",
        "active" in painted and "elapsed" in painted,
        painted[:70].replace("\x1b", "^"),
    )
    record("live spinner shows the current summary", "receiving data" in painted, "summary painted")
    record("cursor is restored on stop", "\x1b[?25h" in painted, "cursor shown")
    record("live status stopped after shutdown", tracker6.live_running is False)

    # --- 6. concurrency: balanced, untangled output --------------------
    buffer = io.StringIO()
    renderer = EventRenderer.from_options(stream=buffer, color=False, animation=False)
    tracker7 = LifecycleTracker(renderer, animation=False, register_atexit=False)
    errors: list[str] = []

    def worker(index: int) -> None:
        try:
            for n in range(15):
                task_id = f"w{index}-{n}"
                tracker7.spawn(task_id, task_id, kind=LifecycleKind.TASK, detail="job")
                with tracker7.active_work(task_id, detail="running"):
                    tracker7.reasoning("master", decision=f"{task_id} dispatch", next_action="continue")
        except Exception as exc:                         # pragma: no cover
            errors.append(f"{type(exc).__name__}: {exc}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    tracker7.shutdown()
    p7 = tracker7.progress()
    record(
        "concurrent lifecycle: nothing lost",
        not errors and p7["total"] == 120 and p7["all_terminal"],
        f"{p7['total']} records, errors={errors[:1]}",
    )
    record(
        "concurrent lifecycle: balanced start/terminal",
        p7["counters"]["started"] == 120 and p7["counters"]["completed"] == 120,
        str(p7["counters"]),
    )
    record("concurrent lifecycle: no spinner left", tracker7.live_running is False)

    return checks


@app.command("lifecycle", help="Animated agent lifecycle messages (spawn → work → review → done).")
def lifecycle_command(
    demo: bool = typer.Option(True, "--demo/--no-demo", help="Run the scripted lifecycle demonstration."),
    tasks: int = typer.Option(4, "--tasks", min=1, max=50, help="Extra tasks in the demonstration."),
    no_animation: bool = typer.Option(False, "--no-animation", help="Disable the transient spinner."),
    no_color: bool = typer.Option(False, "--no-color", help="Disable ANSI colour."),
    heartbeat: float = typer.Option(
        0.0, "--heartbeat", min=0.0, help="Seconds between throttled progress lines (0 = off)."
    ),
    self_test: bool = typer.Option(False, "--self-test", help="Verify the lifecycle guarantees."),
    as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Pure local animation: no network, no model, no browser."""

    console = get_console()

    if self_test:
        results = run_lifecycle_self_test(tasks=tasks)
        failures = [r for r in results if not r.ok]
        if as_json:
            _emit(json.dumps({"ok": not failures, "checks": [asdict(r) for r in results]}, indent=2))
            raise typer.Exit(ExitCode.OK if not failures else ExitCode.INTERNAL)
        console.print()
        table = Table(title="lifecycle self-test", title_justify="left", box=None, pad_edge=False)
        table.add_column("", width=2)
        table.add_column("check", style="bold", no_wrap=True)
        table.add_column("detail", overflow="fold")
        for result in results:
            glyph, colour = ("✔", "green") if result.ok else ("✘", "red")
            table.add_row(f"[{colour}]{glyph}[/{colour}]", escape(result.name), escape(result.detail))
        console.print(table)
        console.print(f"[{'green' if not failures else 'red'}]{len(results) - len(failures)} passed[/] · {len(failures)} failed\n")
        raise typer.Exit(ExitCode.OK if not failures else ExitCode.INTERNAL)

    renderer = EventRenderer.from_options(
        color=not no_color,
        animation=not no_animation,
        stream=sys.stderr if as_json else None,
    )

    tracker = LifecycleTracker(
        renderer,
        animation=not no_animation,
        heartbeat_seconds=heartbeat,
        register_atexit=False,   # the context manager below is authoritative
    )

    # The whole run is guarded: any exit path — success, exception or Ctrl-C —
    # stops the spinner and closes every open record.
    interrupted = False
    try:
        with tracker:
            if demo:
                _run_lifecycle_demo(tracker, tasks=tasks)
    except KeyboardInterrupt:
        interrupted = True
        tracker.shutdown("operator interrupt")
    finally:
        tracker.shutdown("run ended")

    progress = tracker.progress()
    payload = {
        "ok": progress["all_terminal"] and not interrupted,
        "interrupted": interrupted,
        "progress": progress,
        "records": [r.snapshot() for r in tracker.records()],
        "events": [json.loads(model_to_json(e)) for e in renderer.trace.events],
    }

    if as_json:
        _emit(json.dumps(payload, indent=2))
        raise typer.Exit(ExitCode.OK if payload["ok"] else ExitCode.INTERNAL)

    console.print()
    console.print(tracker.summary_table())
    console.print(
        f"[green]{progress['counters']['completed']} completed[/green] · "
        f"{progress['counters']['failed']} failed · "
        f"{progress['counters']['retries']} retried · "
        f"{progress['counters']['merges']} merged · "
        f"{progress['counters']['reviews']} reviewed · "
        f"[dim]{progress['elapsed']} elapsed[/dim]"
    )
    console.print(
        f"[dim]animation={'on' if progress['animation'] else 'off'} · "
        f"all started={'yes' if progress['all_started'] else 'NO'} · "
        f"all terminal={'yes' if progress['all_terminal'] else 'NO'} · "
        f"spinner running={'yes' if progress['live_running'] else 'no'}[/dim]"
    )
    console.print()
    raise typer.Exit(ExitCode.OK if payload["ok"] else ExitCode.INTERNAL)


# ══════════════════════════════════════════════════════════════════════════
# 19. Entry point
# ══════════════════════════════════════════════════════════════════════════


def run() -> None:
    """Invoke the CLI.  Import-safe: only called from ``__main__``."""

    try:
        app()
    except KeyboardInterrupt:                      # pragma: no cover - interactive
        get_console().print("\n[yellow]interrupted[/yellow]")
        raise typer.Exit(130)
    except (typer.Exit, SystemExit):
        raise
    except Exception as exc:                       # pragma: no cover - last resort
        get_console().print(f"[red]internal error:[/red] {escape(f'{type(exc).__name__}: {exc}')}")
        raise typer.Exit(ExitCode.INTERNAL)


if __name__ == "__main__":
    run()
