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
Model access (needed once orchestration lands in Phase 3)::

    ARGUS_LLM_MODEL           Model id, e.g. "gpt-4.1-mini" or "claude-sonnet-4".
    ARGUS_LLM_PROVIDER        Provider hint: openai | anthropic | google | local.
    OPENAI_API_KEY            Used when the provider is openai.
    ANTHROPIC_API_KEY         Used when the provider is anthropic.
    GOOGLE_API_KEY            Used when the provider is google.
    ARGUS_LLM_BASE_URL        Optional OpenAI-compatible endpoint override.

Runtime behaviour::

    ARGUS_HOME                Root for case data (default: ./argus_home).
    ARGUS_CASE_DIR            Directory for the current mission's artefacts.
    ARGUS_LOG_LEVEL           DEBUG | INFO | WARNING | ERROR (default: INFO).
    ARGUS_OPERATOR            Operator name recorded in the audit trail.
    ARGUS_MAX_WORKERS         Hard ceiling on concurrent Workers (default: 8).
    ARGUS_MAX_SUBAGENTS       Hard ceiling on live Subagents (default: 5).
    ARGUS_HTTP_TIMEOUT        Per-request timeout in seconds (default: 30).
    ARGUS_USER_AGENT          User-Agent presented to remote hosts.

Browser and network switches::

    ARGUS_BROWSER_HEADLESS    "1"/"0" — run Chromium headless (default: 1).
    ARGUS_BROWSER_PROFILE_DIR Persistent browser profile directory.
    ARGUS_ALLOW_NETWORK       "0" to force an offline / dry mission (default: 1).
    ARGUS_RESPECT_ROBOTS      "0" to ignore robots.txt (default: 1 — respected).

Usage
-----
::

    python vedant_osint.py --help
    python vedant_osint.py version
    python vedant_osint.py config
    python vedant_osint.py mission --target example.com -o "map the attack surface"

Exit codes
----------
See :class:`ExitCode`.  ``config`` returns a non-zero code when a *required*
capability is missing, which makes it usable as a CI/installation gate.

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
import json
import os
import platform
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any, Iterable

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
VERSION_MINOR: int = 1
VERSION_PATCH: int = 0
VERSION_STAGE: str = "skeleton"          # skeleton → alpha → beta → stable
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
DEFAULT_MAX_SUBAGENTS: int = 5
DEFAULT_MAX_WORKERS: int = 8
DEFAULT_HTTP_TIMEOUT: float = 30.0
DEFAULT_USER_AGENT: str = f"{APP_TITLE}/{__version__} (+authorised-security-research)"
DEFAULT_LOG_LEVEL: str = "INFO"

#: Build phase currently implemented.  Later tasks advance this number.
BUILD_PHASE: int = 1
BUILD_PHASE_NAME: str = "Foundation"

#: Section banners shared by the banner panel and ``version --json``.
PHASE_ROADMAP: tuple[tuple[int, str, str], ...] = (
    (1, "Foundation", "CLI skeleton, config probing, version reporting"),
    (2, "Contracts", "Mission/evidence models, case workspace layout"),
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
    INTERNAL = 70             # unexpected failure


class MissionMode(str, Enum):
    """Collection intensity for a mission."""

    PASSIVE = "passive"       # public sources only, no packets to the target
    ACTIVE = "active"         # direct interaction with the target (needs consent)
    FORENSIC = "forensic"     # local artefacts only, no remote collection


# ══════════════════════════════════════════════════════════════════════════
# 3. Capability registry (dependencies + environment)
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
    Dependency("langgraph", "langgraph", "Master Agent state machine", 3),
    Dependency("browser_use", "browser-use", "agentic browser sessions", 4),
    Dependency("playwright", "playwright", "deterministic browsing & screenshots", 4),
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


ENV_SPECS: tuple[EnvSpec, ...] = (
    EnvSpec("ARGUS_LLM_MODEL", EnvKind.REQUIRED, "model id driving all agents", 3),
    EnvSpec("ARGUS_LLM_PROVIDER", EnvKind.OPTIONAL, "openai | anthropic | google | local", 3, "openai"),
    EnvSpec("ARGUS_LLM_BASE_URL", EnvKind.OPTIONAL, "OpenAI-compatible endpoint override", 3),
    EnvSpec("OPENAI_API_KEY", EnvKind.SECRET, "credential for the OpenAI provider", 3),
    EnvSpec("ANTHROPIC_API_KEY", EnvKind.SECRET, "credential for the Anthropic provider", 3),
    EnvSpec("GOOGLE_API_KEY", EnvKind.SECRET, "credential for the Google provider", 3),
    EnvSpec("ARGUS_HOME", EnvKind.OPTIONAL, "root directory for case data", 2, DEFAULT_HOME_DIRNAME),
    EnvSpec("ARGUS_CASE_DIR", EnvKind.OPTIONAL, "artefact directory for this mission", 2),
    EnvSpec("ARGUS_LOG_LEVEL", EnvKind.OPTIONAL, "DEBUG | INFO | WARNING | ERROR", 1, DEFAULT_LOG_LEVEL),
    EnvSpec("ARGUS_OPERATOR", EnvKind.OPTIONAL, "operator name for the audit trail", 1),
    EnvSpec("ARGUS_MAX_SUBAGENTS", EnvKind.OPTIONAL, "ceiling on live Subagents", 3, str(DEFAULT_MAX_SUBAGENTS)),
    EnvSpec("ARGUS_MAX_WORKERS", EnvKind.OPTIONAL, "ceiling on concurrent Workers", 3, str(DEFAULT_MAX_WORKERS)),
    EnvSpec("ARGUS_HTTP_TIMEOUT", EnvKind.OPTIONAL, "per-request timeout (seconds)", 5, str(int(DEFAULT_HTTP_TIMEOUT))),
    EnvSpec("ARGUS_USER_AGENT", EnvKind.OPTIONAL, "User-Agent sent to remote hosts", 4, DEFAULT_USER_AGENT),
    EnvSpec("ARGUS_BROWSER_HEADLESS", EnvKind.OPTIONAL, "1 = headless Chromium", 4, "1"),
    EnvSpec("ARGUS_BROWSER_PROFILE_DIR", EnvKind.OPTIONAL, "persistent browser profile path", 4),
    EnvSpec("ARGUS_ALLOW_NETWORK", EnvKind.OPTIONAL, "0 = offline/dry mission", 5, "1"),
    EnvSpec("ARGUS_RESPECT_ROBOTS", EnvKind.OPTIONAL, "1 = honour robots.txt", 5, "1"),
)

# ══════════════════════════════════════════════════════════════════════════
# 4. Runtime value objects
# ══════════════════════════════════════════════════════════════════════════


@dataclass
class MissionRequest:
    """Everything the Master Agent needs to plan a mission.

    Phase 2 turns this into a validated Pydantic model; Phase 3 feeds it to the
    Master Agent graph.  For now it is a plain, serialisable value object.
    """

    targets: list[str]
    objective: str
    mode: MissionMode = MissionMode.PASSIVE
    authorised: bool = False
    max_subagents: int = DEFAULT_MAX_SUBAGENTS
    max_workers: int = DEFAULT_MAX_WORKERS
    home_dir: str = field(default_factory=lambda: os.environ.get("ARGUS_HOME", DEFAULT_HOME_DIRNAME))
    operator: str | None = field(default_factory=lambda: os.environ.get("ARGUS_OPERATOR") or None)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

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
# 5. Console + formatting helpers
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
# 6. Configuration probing
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


def directory_writable(path: Path) -> bool:
    """Check writability without creating anything outside the temp sandbox."""

    probe_root = path if path.exists() else path.parent if path.parent.exists() else Path(tempfile.gettempdir())
    if not path.exists():
        # Report on where writing *would* land; never create the real directory.
        probe_root = path.parent if path.parent.exists() else probe_root
    try:
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
# 7. Typer application
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
# 8. Command: version
# ══════════════════════════════════════════════════════════════════════════


@app.command("version", help="Show version, build phase and schema metadata.")
def version_command(
    as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Print version information.  Performs no I/O beyond stdout."""

    print_version(as_json=as_json)


# ══════════════════════════════════════════════════════════════════════════
# 9. Command: config
# ══════════════════════════════════════════════════════════════════════════


@app.command("config", help="Check interpreter, dependencies, environment and workspace.")
def config_command(
    as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
    strict: bool = typer.Option(False, "--strict", help="Treat warnings as failures."),
    show_all: bool = typer.Option(
        True,
        "--all/--problems-only",
        help="List every probe, or only warnings and failures.",
    ),
) -> None:
    """Diagnose the environment.  Exits non-zero when a hard requirement fails."""

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
                    "ok": not failures and not (strict and warnings),
                    "failures": len(failures),
                    "warnings": len(warnings),
                    "checks": [asdict(r) for r in results],
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
        console.print()

    if failures or (strict and warnings):
        if strict and warnings and not failures:
            if not as_json:
                get_console().print(
                    f"[yellow]--strict:[/yellow] exiting {int(ExitCode.CONFIG)} because "
                    f"{len(warnings)} warning(s) were reported."
                )
        raise typer.Exit(ExitCode.CONFIG)
    raise typer.Exit(ExitCode.OK)


# ══════════════════════════════════════════════════════════════════════════
# 10. Command: mission (placeholder — orchestration arrives in Phase 3)
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
    """Reject obviously unusable missions before any planning happens."""

    if not request.targets:
        raise typer.BadParameter("at least one --target is required")
    if not request.objective.strip():
        raise typer.BadParameter("--objective must not be empty")
    if request.mode is MissionMode.ACTIVE and not request.authorised:
        raise typer.BadParameter(
            "active mode interacts with the target; pass --i-authorize to assert permission"
        )
    if request.max_subagents < 1 or request.max_workers < 1:
        raise typer.BadParameter("--max-subagents and --max-workers must be >= 1")


def render_mission_plan(request: MissionRequest) -> None:
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
    table.add_row("authorised", "yes" if request.authorised else "no (passive collection only)")
    table.add_row("targets", f"{len(request.targets)}")
    for index, target in enumerate(request.targets, start=1):
        table.add_row("", f"[bold]{index}.[/bold] {escape(target)}")
    table.add_row("subagents", f"up to {request.max_subagents} (runtime-created)")
    table.add_row("workers", f"up to {request.max_workers} per subagent (runtime-created)")
    table.add_row("case root", escape(str(resolve_home_dir())))
    table.add_row("operator", escape(request.operator or "unset (ARGUS_OPERATOR)"))
    table.add_row("created", request.created_at)
    console.print(table)
    console.print()


@app.command("mission", help="Plan an OSINT/forensics mission (planning scaffold).")
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
    max_subagents: int = typer.Option(
        DEFAULT_MAX_SUBAGENTS,
        "--max-subagents",
        min=1,
        max=25,
        help="Ceiling on Subagents the Master Agent may spawn.",
    ),
    max_workers: int = typer.Option(
        DEFAULT_MAX_WORKERS,
        "--max-workers",
        min=1,
        max=64,
        help="Ceiling on concurrent Workers per Subagent.",
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--execute",
        help="Plan only (default). --execute is rejected until Phase 3.",
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit the plan as JSON."),
) -> None:
    """Validate a mission request and print the plan.  Never performs collection."""

    request = MissionRequest(
        targets=_normalise_targets(target),
        objective=objective,
        mode=mode,
        authorised=i_authorize,
        max_subagents=max_subagents,
        max_workers=max_workers,
    )

    try:
        _validate_request(request)
    except typer.BadParameter as exc:
        get_console().print(f"[red]invalid mission:[/red] {escape(str(exc))}")
        raise typer.Exit(ExitCode.USAGE) from exc

    if request.mode is MissionMode.ACTIVE and not request.authorised:
        get_console().print(
            "[red]refusing mission:[/red] active mode requires --i-authorize (authorised use only)."
        )
        raise typer.Exit(ExitCode.AUTHORIZATION)

    if as_json:
        _emit(
            json.dumps(
                {
                    "mission_id": request.fingerprint(),
                    "build_phase": BUILD_PHASE,
                    "executed": False,
                    "request": request.to_dict(),
                    "plan": {
                        "subagents": f"runtime-created, max {request.max_subagents}",
                        "workers": f"runtime-created, max {request.max_workers}",
                        "orchestrator": "langgraph (phase 3)",
                    },
                },
                indent=2,
            )
        )
    else:
        render_mission_plan(request)

    if not dry_run:
        get_console().print(
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
# 11. Entry point
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
