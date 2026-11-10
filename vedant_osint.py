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

    pip install typer rich pydantic python-dotenv

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

Usage
-----
::

    python vedant_osint.py --help
    python vedant_osint.py version
    python vedant_osint.py config
    python vedant_osint.py config --settings            # merged, redacted view
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
import importlib.util
import ipaddress
import json
import os
import platform
import re
import shutil
import sys
import tempfile
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

# --- third party: CLI surface -------------------------------------------------
# Typer + Rich are the only hard imports.  They are imported at module level
# because the CLI cannot exist without them, and importing them performs no
# I/O.  Everything heavier (LangGraph, browser-use, Playwright, HTTP clients)
# is imported lazily inside the functions that need it.
import typer
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
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
VERSION_MINOR: int = 4
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
    (2, "Contracts", "Strict settings, capability doctor, safety & scope preflight"),
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
        """Stable, human-readable mission id derived from its content."""

        import hashlib

        payload = json.dumps(
            {"targets": sorted(self.targets), "objective": self.objective, "mode": self.mode.value},
            sort_keys=True,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:10]
        return f"mission-{digest}"


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
    request: MissionRequest, settings: Settings, preflight: PreflightReport | None = None
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
        render_mission_plan(request, settings, preflight)
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
# 15. Entry point
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
