# ARGUS — single-file autonomous OSINT & digital-forensics agent

Everything ships in one file: **`vedant_osint.py`**.

```bash
python vedant_osint.py --help        # CLI surface
python vedant_osint.py version       # version, build phase, roadmap
python vedant_osint.py config        # interpreter / dependency / env probes
python vedant_osint.py mission -t example.com -o "map the attack surface"
python vedant_osint.py config --settings     # merged config, secrets masked
python vedant_osint.py doctor                # capability health check (CI gate)
python vedant_osint.py resilience --self-test # logging, cancellation, cleanup
python vedant_osint.py adapter --self-test    # structured model output contract
python vedant_osint.py master --self-test     # Master Agent boundaries
python vedant_osint.py subagents --self-test  # runtime Subagent specifications
python vedant_osint.py workers --self-test    # runtime Worker specifications
python vedant_osint.py flow --self-test       # LangGraph execution flow
python vedant_osint.py flow --mock             # the whole graph over mock adapters
python vedant_osint.py sched --self-test      # bounded queues, deadlines, licences
python vedant_osint.py resume --self-test     # checkpointing and resumable missions
python vedant_osint.py router --self-test     # the controlled capability router
python vedant_osint.py browser --self-test    # browser research, guaranteed closure
python vedant_osint.py research --self-test   # source-aware web research
python vedant_osint.py extract --self-test    # bounded, untrusted document extraction
python vedant_osint.py artifacts --self-test  # read-only artifact handling, no writes
python vedant_osint.py timeline --self-test   # source vs derived time, explained links
python vedant_osint.py outcomes --self-test  # Worker statuses, no verdicts
python vedant_osint.py review --self-test    # seven dimensions, pass or revise
python vedant_osint.py retask --self-test    # a revise becomes a specific assignment
python vedant_osint.py aggregate --self-test # reviewed work only, and never early
python vedant_osint.py review-master --self-test # five lenses, five ways to stop
python vedant_osint.py loops --self-test      # repeated work, blocked lines, saturation
python vedant_osint.py synthesis --self-test  # a report that cannot outrun its evidence
python vedant_osint.py report --self-test     # formats, presentation, audit, dry run (283)
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

## Event rendering

`EventRenderer` is line-oriented, never a full-screen TUI (no alternate screen).
It covers Master thinking/planning, spawning, task assignment, browsing,
forensics, reasoning, completion, review, retasking, both synthesis steps,
warnings and completion.

```bash
python vedant_osint.py renderer                  # scripted nested mission
python vedant_osint.py renderer --self-test      # 22 guarantee checks
python vedant_osint.py renderer --record t.jsonl --replay t.jsonl
python vedant_osint.py renderer --from-state case/state.json
```

On a TTY a step animates with Rich's inline spinner; with `--no-animation`, or
when piped, it becomes an explicit `… message` / `✔ message` pair. Piped output
has zero ANSI escapes and zero carriage returns, every event appearing once in
chronological order. Hierarchical indentation shows the agent tree; `--ascii`
swaps all glyphs. `--json` writes JSONL to stdout and prose to stderr; a plain
`--log-file` also captures events the terminal filter hid.

## Agent lifecycle animation

`LifecycleTracker` pairs a **visible start and terminal state** for every agent
and task — spawn, delegate, active work, reasoning, review, retry, merge, done.

```bash
python vedant_osint.py lifecycle               # scripted demonstration
python vedant_osint.py lifecycle --self-test   # 33 guarantee checks
python vedant_osint.py lifecycle --json        # records + counters + events
```

Status text is model-safe: `sanitize_status` refuses deliberation phrasing and
caps every string at 20 words, and reasoning is reported as a `StatusSummary`
(decision · criterion · next action) with no narrative field. All active work
shares one transient line carrying counters and elapsed time, so permanent lines
grow with transitions, not ticks. Ctrl-C, exceptions, cancellation and
`shutdown()` (also via `atexit`) all close open records — an interrupted run
never leaves a spinner running.

## Resilience

`MissionRun` supervises a mission so that Ctrl-C, a budget timeout or an
unexpected exception all end the same way: readable output, a valid checkpoint,
and a partial report that keeps everything already collected.

```bash
python vedant_osint.py resilience --self-test             # 75 guarantee checks
python vedant_osint.py resilience --demo sigint           # Ctrl-C mid-mission
python vedant_osint.py resilience --demo timeout --json   # budget exhaustion
python vedant_osint.py resilience --demo exception        # recursive failure
```

- **Optional JSONL logging** — `MissionLogger` writes one redacted JSON object per
  line, or is cleanly disabled when no path is given. An unwritable path disables
  logging instead of failing the mission; keys that name a secret are replaced
  wholesale.
- **Cancellation** — `CancellationToken` is first-wins, runs cleanups in order,
  and pending work stops at its next `raise_if_cancelled()` checkpoint.
  `CancellationGuard` maps the first SIGINT/SIGTERM to cancellation, the second
  to a hard abort, and restores the previous handlers on exit.
- **Cleanup** — `BrowserReaper` closes pages, contexts and browsers in reverse
  order and is idempotent; `ResourceStack` removes temporary profiles.
- **Partial reports** — completed evidence is preserved verbatim; unfinished
  assignments become explicit gaps and the uncertainty statement is marked
  `PARTIAL`. The checkpoint is written before the report.
- **Attributed errors** — `AgentError` carries agent, assignment and delegation
  chain identifiers and has **no field for prompts or working memory**.

Exit status follows convention: `130` interrupted, `124` timeout, `70` internal
error.

## The Master Agent

`MasterAgent` is the **only** agent defined ahead of time. Its duties are closed:
confirm the scope, plan the mission, design the team, oversee the work, detect
cross-Subagent conflict, synthesise the answer, and decide when to stop. It has
no method that collects, browses or parses — those belong to the agents it
creates.

```bash
python vedant_osint.py master --self-test      # 87 guarantee checks, offline
python vedant_osint.py master --demo compare   # two objectives, two teams
python vedant_osint.py master --prompt         # read the charter
python vedant_osint.py master -t example.com -o "map the attack surface"
```

- **No predetermined roster** — the charter forbids assuming one, and
  `assert_no_fixed_roles` rejects prompt text drifting towards one. A self-test
  asserts no role class such as `NetworkSubagent` exists in the file.
- **The smallest sufficient team** — `design_team` asks for a `TeamDesign`
  (per-Subagent objective, rationale, instructions, tools, Workers, completion
  criteria) and validates it against the mission scope, the limits and the
  capabilities actually available. A team that widens the scope, duplicates an
  agent or exceeds a limit is **refused**, never silently trimmed.
- **Two objectives, two organisations** — the same code produced 2 Subagents /
  3 Workers for a web-exposure objective and 3 Subagents / 4 Workers with
  different tools and completion criteria for a forensic one.
- **Oversight is executable** — a team review returns a concrete change
  (`add-subagent`, `retask-subagent`, `retire-subagent`, `add-worker`,
  `narrow-scope`, `stop`) or `none`.
- **Conflict is reported, not voted on** — incompatible claims on the same topic
  keep both sides and state what would settle the dispute; an unresolved
  conflict pauses the mission rather than letting the Master conclude.
- **Stopping is deterministic** — budget floor, diminishing returns, unresolved
  conflict and "nothing left open", with the most cautious rule winning.

## Dynamic Subagent specifications

No Subagent has a class. A Subagent exists only because the Master returned a
`SubagentSpecDraft` that passed `validate_subagent_specs`, and only
`SubagentFactory` turns a passing draft into a stored `SubagentSpec` with runtime
ids — the self-test parses the file to prove no executable Subagent class and no
roster constant exists.

```bash
python vedant_osint.py subagents --self-test      # 109 guarantee checks, offline
python vedant_osint.py subagents --demo compare   # two objectives, two sets of specs
python vedant_osint.py subagents --show published-advisories
python vedant_osint.py subagents --demo reject    # what the Master is sent back
```

- **Ten task-derived parts** — role *and the basis* it was derived from (source
  family, analytic step, artefact type, verification, integrity, timeline, log
  correlation),
  objective, scope boundaries, required inputs, allowed capabilities, expected
  outputs, evidence requirements, quality rubric, termination criteria.
- **A measurable deliverable** — each `Deliverable` names its format, its fields
  and a `measurable_check`; vague phrasing is refused by the model.
- **A measurable stop condition** — `TerminationCriteria.is_measurable` requires
  a countable or checkable marker ("at least one row per advisory"), plus
  ceilings, abandon conditions and whether a partial report is required.
- **Refusal, not trimming** — out-of-scope entries, unavailable capabilities, job
  titles (`analyst`, `The Analyst`), duplicate roles, duplicate *behaviour* under
  a second name, circular justifications and dangling dependencies are all
  rejected, with a repair instruction per problem.
- **The Master repairs its own plan** — `plan_subagent_specs` sends the problems
  back as a bounded repair brief and raises `SubagentPlanError` (exit `7`) if the
  plan never becomes acceptable.
- **Two objectives, two sets of specs** — exposure produced 2 runtime Subagents
  with different roles, tools, deliverables and stop conditions from forensic's
  3, with no code change.

## Dynamic Worker specifications

No Worker has a class either. Each Subagent plans *its own* Workers from its own
assignment: `SubagentWorkerPlanner` asks for a `WorkerPlan`, `validate_worker_specs`
checks it against the assignment, and `SubagentWorkerFactory` is the only path to
a stored `WorkerSpec` — the self-test parses the file to prove it.

```bash
python vedant_osint.py workers --self-test      # 115 guarantee checks, offline
python vedant_osint.py workers --demo compare   # two objectives, two staffings
python vedant_osint.py workers --role dns-and-archive
python vedant_osint.py workers --demo reject    # what the Subagent is sent back
```

- **Every Worker carries** a narrow objective, the unit of work and what it does
  *not* cover, allowed inputs, a subset of the parent's tools, the evidence it
  must return, an output schema, a `WorkerBudget` (attempts × timeout × tokens)
  and checkable completion criteria.
- **A slice, not the assignment** — a mandate that restates the Subagent's
  objective, or an objective as broad as the assignment, is refused. One Worker
  carrying everything is refused unless the assignment was declared indivisible,
  and the claim has to come from the design rather than from the Worker.
- **No occupational roster** — `analyst`, `researcher`, `The Analyst` are refused
  as Worker names exactly as they are refused as Subagent roles.
- **Independence is computed** — units that read another unit's output are
  chained and the rest are grouped into waves by the code, so "run these in
  parallel" is a checked property rather than a claim.
- **Refusal, then repair** — a bad plan is sent back as a bounded repair brief,
  and `WorkerPlanError` (exit `7`) is raised if the Subagent never complies.
- **Different Subagents, different shapes** — from the same code, one objective
  produced three single-Worker Subagents plus one with two parallel Workers, the
  other one plus two.

## Structured model adapter

One interface between orchestration and every provider. `ModelAdapter` returns a
validated `PlanOutput`, `DecompositionOutput`, `ReviewOutput` or
`SynthesisOutput` — never a string anyone has to interpret.

```bash
python vedant_osint.py adapter --self-test          # 134 guarantee checks, offline
python vedant_osint.py adapter --demo prose         # what a rejection looks like
python vedant_osint.py adapter --demo scope         # a plan that widens the scope
python vedant_osint.py adapter --check              # is the provider usable?
python vedant_osint.py adapter --prompts --task plan
```

- **Invalid JSON never becomes a plan** — the response is parsed, validated
  against the task model, then checked against the mission contract: cited
  evidence must have been supplied, planned scope must sit inside the mission
  scope, the subagent count must respect the limit, and a synthesis may not drop
  evidence without recording a gap.
- **Bounded retries** — attempts *and* elapsed time are capped, with
  deterministic backoff. Malformed answers get a repair turn naming the failing
  field; 4xx schema rejections, refusals and policy violations are not retried.
- **Every prompt demands sources and uncertainty** — a single JSON object, no
  invented ids, every claim citing supplied ids, and a required uncertainty
  field. `ModelClaim` refuses unsourced observations, unreasoned inferences and
  hedging adverbs.
- **Provider setup is isolated** — endpoints, auth headers, JSON modes and
  response envelopes live in `PROVIDER_ADAPTERS`; a self-test proves no dialect
  vocabulary appears above the adapter.

Failures are typed (`malformed`, `policy`, `refused`, `unsupported`,
`transient`, `config`, `cancelled`) and map to exit codes `70`, `7`, `70`, `3`,
`70`, `3`, `130`.

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

## The execution flow

The hierarchy is executed by LangGraph, not by loops in this file.
`HierarchicalFlow` compiles three graphs and reuses each one for every mission:
a **Master** graph (`master-plan` → one `Send` per Subagent → `master-review` →
`master-synthesize`), a **Subagent** child graph (`subagent` → one `Send` per
Worker → `subagent-aggregate`), and a **Worker** child graph (`worker-task` →
`worker-review`, looping while the review asks for a retry).

```bash
python vedant_osint.py flow --self-test        # 77 guarantee checks, offline
python vedant_osint.py flow --demo exposure    # summary + ledger + joins
python vedant_osint.py flow --demo compare     # one structure, two widths
python vedant_osint.py flow --dry-run -t example.com -o "…"   # plan only, nothing executed
python vedant_osint.py flow --mock             # the same graph over mock adapters
python vedant_osint.py flow -t example.com -o "assess the exposure of example.com"
```

- **Width is data, never structure** — both fan-outs are `Send`s built from the
  mission's own team, so a 2-Subagent and a 9-Subagent mission compile to the
  *same* node set. No node is named after a specialist role and no roster
  constant exists; the self-test parses the file to prove it.
- **A join is an edge, then a check** — every Worker branch reaches
  `subagent-aggregate` over a plain edge, so it runs once, after the last branch
  settles; `master-synthesize` waits the same way for every Subagent. Each
  aggregate rebuilds its `JoinBarrier` and raises `PrematureAggregate` if a unit
  is missing, and the barrier travels inside the report as proof the aggregate was
  not premature.
- **Parallelism is bounded, and depends on nothing** — every unit takes a slot
  from the mission's `BoundedScheduler` (see below), because LangGraph's
  `max_concurrency` is per invocation and a child graph does not inherit its
  parent's limit. A unit takes its slot only after its dependencies settle, so
  waiting can never starve the unit being waited for.
- **Everything is observable** — `FlowTrace` is a sequence-ordered ledger of
  stage, unit, dependency wave, thread and monotonic time, and it computes
  concurrency from the ledger alone, so "it ran in parallel" is a measurement.
- **A failure is a gap, never a pass** — retries are bounded by the Worker's own
  budget; when they run out the verdict stands and the gap names the Worker and
  the gate. A mission whose Subagents produced nothing stops with a reason
  instead of synthesising an empty answer.

## Bounded queues, deadlines and fair concurrency

No unit runs unless the scheduler admits it. `BoundedScheduler` is one FIFO
queue per resource — model calls, browser sessions, forensic jobs, Subagents,
Workers — behind one condition variable, and it grants a slot only to the oldest
waiter, so a long unit cannot re-acquire ahead of the queue and starve the tail
of a large plan.

```bash
python vedant_osint.py sched --self-test                  # 80 guarantee checks, offline
python vedant_osint.py sched --demo tight                 # caps below the plan's width
python vedant_osint.py sched --demo roomy                 # the same code, nothing refused
python vedant_osint.py sched --clip forensic --workers 2 --subagents 2
python vedant_osint.py sched --demo tight --json          # the whole snapshot
```

- **Caps are per resource and per mission, and both are enforced.** `ResourceLimits`
  carries a concurrent cap and an optional lifetime cap per kind; `peak` is
  recorded by the scheduler itself, so `peak ≤ cap` in the demo table is the
  scheduler's own measurement, not the runner's guess.
- **A wait that cannot be met fails loudly.** A queue deadline (`QueueTimeout`)
  shortens the wait to what the mission has left, and a caller with an expired
  `Deadline` is refused before it queues. Nothing waits forever.
- **Deadlines nest.** `Deadline.child()` clamps a unit's budget to its parent's,
  `clamp()` reduces a timeout to the time actually left, and an expired mission
  deadline refuses everything below it. Cancellation is checked both before a
  unit queues and while it is parked, so Ctrl-C empties the queues.
- **Only the Master creates Subagents; Workers create nothing.** `SpawnLedger`
  records who may create whom as a licence (`SpawnTier.MASTER` → `SUBAGENT` →
  `WORKER`, depth 2), and every spawn attempt is either licensed or refused with
  a reason — a Worker asking to create a Subagent is refused, not ignored.
- **A plan too large is clipped, deterministically.** `clip_plan()` keeps
  dependency closure first and declaration order second — never thread order —
  drops the Workers that go with a dropped Subagent, and returns a `ClipReport`
  naming every decision. Nothing is clipped silently.
- **Backpressure is a recorded deferral.** A unit refused a slot or a licence
  still produces its report: status `blocked`, the gate that stopped it, and a
  gap naming the unit and the reason. The mission still joins, and a cancelled
  mission stops before synthesis instead of presenting a partial answer.

## Checkpoints and resumable missions

A mission that takes an hour will be interrupted, so the runtime keeps its own
write-ahead record **beside** this file — under the runtime output directory,
`runs/<mission>/` — and a resumed run continues from it. The deliverable stays a
single file; a mission's data never goes into it.

```bash
python vedant_osint.py resume --demo                 # interrupt a real run, then resume it
python vedant_osint.py resume --self-test            # 49 guarantee checks, offline
python vedant_osint.py resume --list                 # missions with a checkpoint
python vedant_osint.py resume --mission flow-a995e   # what a resume would do, and why
python vedant_osint.py flow --demo exposure --checkpoint   # run with persistence on
python vedant_osint.py flow --demo exposure --checkpoint --redo      # do it again anyway
```

- **Written after every major transition.** A Worker attempt is recorded *before*
  the work and its verdict after it; a Subagent's aggregate, the sync thesis and
  the ledger are each a transition of their own. Every write is atomic (temp
  file, `fsync`, `os.replace`), so a crash leaves the previous state, never a
  half-written one.
- **Completed work is not repeated.** A Worker that finished *and* was approved is
  settled; a resumed graph answers it from the record — no slot, no runner call —
  and an adopted Subagent aggregate is returned with its own `JoinBarrier`, so
  the hierarchy (not just the evidence) survives. `--redo` is the only way to ask
  for the work again, and it keeps the record rather than emptying it.
- **Incomplete work is revalidated, not trusted.** An outcome with no review, a
  review that asked for a retry, or a unit that never ran is *stale*: the resume
  re-runs it. `--revalidate-after SECONDS` additionally re-checks settled results
  that are old, and a success whose record holds no evidence is re-run rather than
  believed.
- **Evidence is never duplicated.** Evidence ids are content-addressed and merged
  on id, so re-recording corroborates sources instead of appending a copy — a
  resumed mission ends with exactly the evidence an uninterrupted one would, and
  the self-test compares the two id lists.
- **A finished mission is refused, not replayed.** The live checkpoint becomes
  `archive.json` on completion; resuming it is a usage error that names the archive
  and says how to ask again. A checkpoint from another build, a corrupt file, or a
  job for a *different* plan (fingerprint mismatch) is refused with a reason too.
- **Persistence never becomes the mission's problem.** A store that cannot write
  records the failure and the mission carries on; losing durability is bad,
  losing the run is worse.

## The controlled capability router

A Worker never touches the world directly. It asks for one of **nine**
capabilities — public-web research, browser interaction, document extraction,
local artefact inspection, metadata analysis, hashing, timeline construction,
correlation, synthesis — at a named target. The router either performs it and
returns evidence, or refuses with a structured explanation and moves on.

```bash
python vedant_osint.py router --demo         # seven attempts, six refused
python vedant_osint.py router --self-test    # 98 boundary checks, offline
python vedant_osint.py router --demo --json  # grants, attempts, dispatch
```

- **The vocabulary is closed.** `Capability` is nine values and `TOOL_REGISTRY`
  is a fixed table binding each tool to one of them. `shell.exec`, `worker.spawn`
  or anything else is refused as `unknown-capability`: the router executes
  nothing and has no field for a command line, so no Worker reaches a process.
  A URL that legitimately contains `&` is not mistaken for a shell command, and
  a *literal* command line is refused however it is dressed up.
- **The grant is derived, never granted.** `grant_for_worker` reads the Worker's
  own declared tools and produces the only capabilities it can hold;
  `CapabilityGrant` is frozen, so nothing can add one at runtime. A request for a
  tool the Worker was not assigned is `not-granted`, and a capability its
  assignment does not name is `not-granted` before any handler is reached.
- **Scope cannot be widened from inside.** A target is checked against the
  mission's `Scope` for hosts and against the approved roots for files, both
  *before* any effect. A symlink out of an approved root, a sibling directory, a
  `..` traversal or `/etc/shadow` is `path-not-approved`; `evil.example.org` is
  `out-of-scope`. An offline mission refuses a network capability as
  `network-off` even when the grant holds it.
- **Admission has an order, and it is the order of the reasons a Worker sees.**
  Shell refusal → capability in the closed set → held by the grant → tool bound,
  assigned and installed → network switch → path or scope → budget. A refusal
  consumes no budget, and it never runs part of a request.
- **Derived capabilities cannot import the world.** Correlation and synthesis
  may cite only evidence *this* mission already produced — an invented id is
  `out-of-scope` — and their revisions live in a `DerivationJournal` a rejected
  review can roll back.
- **A refusal is visible, not silent.** The router keeps every refusal, turns it
  into an `UnknownValue` gap, and the flow asks the router before taking a
  concurrency slot: a Worker with nothing it may do is reported as blocked
  instead of consuming capacity a working Worker needs.

## Browser research

The ninth capability has a real engine behind it: Playwright for a fetch,
browser-use when the run asks for an agent, both configured from one policy and
both closed by the same guard.

```bash
python vedant_osint.py browser --self-test                                  # 113 closure checks
python vedant_osint.py browser --demo                                       # 3 captures, 4 refusals
python vedant_osint.py browser --url https://example.com/ --scope example.com
python vedant_osint.py browser --url https://example.com/ --scope example.com --live
python vedant_osint.py flow --demo exposure --browser                        # through the router
```

- **Scope is checked before a browser exists.** A URL outside the mission's
  `Scope` is refused with no process started, no profile written and no request
  made. A page that *redirects* off-scope is refused rather than followed, so a
  redirect cannot widen the mission, and requests are filtered at the browser
  too — an off-scope document is aborted before it renders.
- **Not-public-web is not browsable.** Loopback, RFC 1918, link-local, `.local`
  and the cloud metadata names are refused *statically*, without DNS, so the
  browser cannot become a pivot into an internal network.
- **Each visit gets its own context.** Cookie-less, ephemeral and closed in a
  `finally`; there is no persistent profile, so nothing survives from one visit
  into the next or from one run into the next.
- **Five prohibitions, as values not prose.** Credential use, access-control
  bypass, CAPTCHA solving, unauthorised automation and form submission each have
  a `BrowserRefusal`; an action that names one is refused with a reason while
  the rest of the visit still runs — the page is read, the login is not.
- **Headless, bounded, and configured from one object.** `BrowserPolicy` carries
  headless mode, navigation and action timeouts, the viewport, the download
  policy, the navigation ceiling and the text cap; `browser --demo` prints it.
- **Closure is the acceptance criterion, so it is not a `finally: pass`.** A
  session owns one browser for one visit and retires itself when the visit ends
  — on success, on an engine exception, on a deadline, and on a cancellation that
  arrives *while* the visit is running. The capture reports whether a browser was
  launched and whether it was closed, `flow --browser` closes again on its own
  exit path, and the demo prints `0 resource(s) left open`.
- **The capture is evidence.** Final URL, title, retrieval time, the relevant
  text and the errors all reach the router's evidence, so "the page did not load"
  becomes a reported finding instead of an empty result.

## Source-aware web research

Reading a page is not the same as being entitled to report it. Research Workers
get a `ResearchBrief` — six fixed rules plus primary-first queries — and what
they return is audited before it can reach synthesis.

```bash
python vedant_osint.py research --self-test     # 96 source-aware checks, offline
python vedant_osint.py research --demo          # what is corroborated, labelled, omitted
python vedant_osint.py research --normalize "https://WWW.Example.com:443/a/?utm_source=x"
python vedant_osint.py research --subject "example.com proxy flaw" --url https://example.com/a
```

- **Primary sources first.** Every source is graded from its *host* by a fixed
  rule table — first-party advisories, CVE records and standards are `primary`;
  independent reporting is `secondary`; aggregators and archives `tertiary`; a
  search engine is `search-result` and never citable. The grade is *assigned*,
  not accepted, so a Worker cannot promote its own source.
- **Corroboration counts origins, not pages.** Two observations on one
  registrable domain are one origin, and an archive copy is a copy of the page it
  archived. A material claim needs two independent origins to be called
  `corroborated`; with one, it is published as `single-source` and labelled.
- **Quotes are checked, not trusted.** Every observation carries the exact span
  it rests on, located in the fetched text — a paraphrase fails, a fabricated
  quote cannot be cited, and the body's sha256 travels with it.
- **Publication is not retrieval.** `published_at` comes from the page's own
  markers or printed date — never from the fetch time, never from a *modified*
  marker, never from a date in the future. A page that states nothing is reported
  `undated` rather than backfilled.
- **URL normalisation preserves the original.** Tracking parameters, fragments,
  default ports, `www.` and alternate views are dropped for *comparison*; the
  citation keeps the original string and every normalisation is listed. Shortener
  links are dropped rather than followed, and `http`/`https` forms of one page
  count as one source so a redirect cannot manufacture corroboration.
- **Failures and contradictions are reported.** An unreadable source becomes an
  `AccessFailure` and a gap; a disagreement becomes a `Contradiction` carrying
  both sides — plus a note when the difference is explained by time.
- **The criterion is a pass, not a hope.** `audit_web_report` re-assesses each
  claim from its evidence and then *labels or omits* anything with nothing
  retrievable behind it. `flow` runs that audit and the six-rule review on every
  research report (`research_first`, on by default) and sends a failing Worker
  back with the remedy.

## Safe document and page extraction

A document read during a mission is evidence, and evidence is not an order.
`extract` reads HTML, plain text, PDF, `.docx`, `.xlsx` and RTF — the standard
library plus `pypdf` for PDFs — under hard ceilings, and everything it returns
is treated as a third party's claim:

```bash
python vedant_osint.py extract --self-test      # 128 extraction checks, offline
python vedant_osint.py extract --demo           # a hostile page, quoted and refused
python vedant_osint.py extract --file review.docx --json
python vedant_osint.py extract --url https://example.com/advisory --scope example.com
python vedant_osint.py extract --limits         # the size, time and text ceilings
```

- **Bounded before parsing.** Empty, oversize and unsupported input is refused
  before a parser sees a byte; the parse runs on its own thread against a
  wall-clock deadline; text is truncated at a stated ceiling; a zip that expands
  past four times the byte cap is refused before a member is read. A source
  outside the approved scope is never read at all (`--scope`, or `Scope` in code).
- **Identified by content.** Magic number, then file name, then the declared
  content type — a `.txt` starting `%PDF-` is a PDF, and a spreadsheet renamed
  `.docx` is still read as a spreadsheet, because the archive's entries decide.
- **Nothing executable is opened.** `<script>`, forms and embedded objects are
  skipped and recorded; macro projects, embedded files and external links are
  refused by name; an encrypted PDF is never guessed at (`encrypted`, no
  password attempted); an RTF object is never decoded.
- **Instructions are quoted, never obeyed.** A scanner finds override,
  scope-change, secret-request, tool-trigger, role-switch, exfiltration and forged
  delimiter patterns, plus eleven kinds of concealment (`display:none`,
  white-on-white, zero font, off-screen positioning, `aria-hidden`, comments…).
  Every line carrying one is wrapped whole in quarantine markers, and any
  remaining line that reads as an imperative is quoted too — so a phrasing nobody
  wrote a pattern for is still data. `InjectionFinding.span` keeps the hostile
  text verbatim, so the report *shows* what the page tried.
- **There is nothing to obey with.** `ExtractedDocument` has no field for a tool,
  a capability, a scope entry, a router or a browser: an extraction cannot reach
  one and an embedded instruction cannot become one. What it offers instead is
  `untrusted_block` — the text fenced and labelled **DATA ONLY**, with the three
  prohibitions spelled out — and `document_claims`, which cites a hostile page for
  its *hostility* rather than for its demands.

## Read-only forensic artifacts

`artifacts` describes local evidence the operator explicitly names — and never
changes it. No disk images, no memory captures, no deleted-file recovery: those
are named as *not implemented* in every manifest, so no reader can infer a
capability this build does not have.

```bash
python vedant_osint.py artifacts --self-test            # 167 read-only checks, offline
python vedant_osint.py artifacts --demo                 # a small case, end to end
python vedant_osint.py artifacts --path ~/evidence --verify
python vedant_osint.py artifacts --path report.docx --copy --json
python vedant_osint.py artifacts --limits               # ceilings, and what is not done
```

- **Only what was named, only under the root it named.** The case is opened with
  the supplied paths resolved once; anything outside them is refused with the
  reason and recorded as a refusal. `..` that escapes, a control character in a
  path, a fifo, a socket or a device is refused before a byte is read.
- **Never modified.** Directories are walked without following symlinks (a
  symlink out of the root is a reported limit, not a silent skip), sources are
  opened read-only, and analysis happens on a copy under the case directory whose
  digest is verified before it is used. The self-test parses the section's own
  source to prove it contains no mutating filesystem call, and that the only
  `mkdir` targets the case directory.
- **Hashes and paths recorded, always.** Every file gets sha256, sha1 and md5,
  its size, mode, owner, inode, link count, its supplied *and* resolved path, and
  an entry id derived from path and content. Readable artefacts also get the
  metadata their format advertises (title, author, pages, language) and a count of
  the instructions their text carried, read once from a bounded prefix. A file
  larger than the hash ceiling is *sampled* — and the digest records the window it
  used, so a reviewer can recompute the identical value instead of a whole-file
  hash that would fail for the wrong reason.
- **Every access is a ledger row.** `stat`, `read`, `hash`, `copy`, `extract`,
  `verify`, `refused` — with the time, the byte count, the digest before and
  after, and whether the access left the source unchanged.
- **Timestamps carry their caveats.** `mtime` is what the filesystem says, not
  what the file says; `ctime` is an inode change, not a creation; `atime` may be
  disabled by a mount option. A future or pre-1980 `mtime` is marked unreliable
  rather than quietly quoted.
- **Unsupported formats return clear partial results.** Identification is by
  magic number first, suffix second, content last — a `.pdf` that holds plain
  text is reported as text *with the suffix disagreement named*. A binary blob is
  identified, sized, timestamped and hashed, then explicitly labelled: identified
  and hashed only, with no reader in this build.
- **Tampering is detected, not assumed away.** `--verify` recomputes every digest
  after ingestion and reports drift; a file that was removed is a finding, not a
  skip. Previews of text artefacts go through the Task 20 scanner and defanger,
  so a file whose first line is an instruction appears in the record quoted.

## Forensic timeline and correlation

A timeline is a list sorted by a rule, not evidence of order; a correlation is a
statement about observables, not about a person. `timeline` keeps both distinctions
visible in the schema itself.

```bash
python vedant_osint.py timeline --self-test        # 146 forensic-time checks, offline
python vedant_osint.py timeline --demo             # order, links, duplicates
python vedant_osint.py timeline --timestamp "04/05/2026 12:00" "2026-05-04T12:00:00+02:00"
python vedant_osint.py timeline --record "a:domain=evil.example.org;hash=<sha256>"
python vedant_osint.py timeline --path ~/evidence  # a case, ordered
```

- **The source's timestamp and this build's reading are different fields.**
  `NormalisedTimestamp` keeps `original` verbatim, `wall_clock` as written,
  `offset_minutes` as stated, and `utc` as the normalisation — plus a `certainty`.
  Only `exact` may be quoted as the time of an event; `approximate`, `reduced` (a
  date with no time), `ambiguous` (no offset, or a day/month order that could
  differ) and `unverified` each carry the reason. The original zone is preserved,
  so the local time can be reconstructed exactly, and an ambiguous `04/05/2026`
  keeps the other reading in `alternatives`.
- **The order states its own provenance.** Every event carries an
  `ordering_basis`: `source-timestamp`, `tie-break` (both members of a tie, since
  neither can be shown to have happened first), `derived` (a time this tool wrote),
  or `undated` — listed last and never interleaved. `order_is_derived` is true when
  nothing was placed by a source.
- **Every link is explained in a sentence** naming the shared indicators and the
  strength: identical content is strong, two independent observables moderate, one
  weak. `CorrelationLink` has no field for a person, an actor or an identity.
- **A coincidence is not a match.** A free mail provider, a default file name, a
  private or documentation address, a stock user agent or a four-letter username
  never links two records alone — the pair is reported as a near-miss *with the
  reason*, so a reader sees what was excluded, not only what survived.
- **Duplicates are content, never names.** Same evidence means same sha256 *and*
  same size; a shared name or a shared size is a look-alike kept distinct, and the
  canonical member is chosen by path so a re-run makes the same choice. Neither
  copy is deleted: both paths stay on the record.

## Worker outcomes

Every Worker returns the same record: one of **four statuses**, findings, structured
evidence, source references, limitations and suggested follow-up. It may not reach a
mission-level conclusion, and it may not contact another team — both are refused at
the boundary rather than requested in a prompt.

```bash
python vedant_osint.py outcomes --self-test         # 144 contract checks, offline
python vedant_osint.py outcomes --demo              # four statuses, refusals, failures
python vedant_osint.py outcomes --check report.json # validate a report ('-' = stdin)
```

- **Four statuses, and the status is a claim about the contents.** `completed` needs
  findings *and* sourced evidence and may carry no limitations; `partial` needs
  findings, sourced evidence *and* a named limitation; `blocked` needs a reason and
  may be empty; `failed` needs its error. A completed report that still hedges is
  refused as a partial one wearing the wrong label.
- **The prohibition is structural.** `WorkerReport` has no conclusion, verdict,
  identity or recipient field, and a nested `attribution`/`peer_id` key is refused
  with its dotted path. Phrases such as "the mission is complete" or "delegated to
  the archive team" are refused in whichever prose field they appear — summary,
  finding, limitation, follow-up — while an artefact path containing the same word is
  left alone, because a locator is data, not a claim.
- **A failed tool does not crash the mission.** `survive_tool_failure` turns a raising
  call into a `ToolCallResult` with a status and a redacted error, and
  `report_from_tool_results` folds several calls into one report whose status is
  never better than the worst call. Evidence the tool had already produced is kept
  with its source; cancellation is re-raised, because that is an operator's decision.
- **Partial results retain usable provenance.** Findings must cite evidence the
  report actually contains, every evidence item of a usable report must carry a
  source reference, and `OutcomeLedger.provenance_intact` checks that across the
  whole team. A `blocked` Worker states nothing rather than guessing.
- **The graph is unchanged, and the contract crosses into it.** `outcome_from_report`
  and `report_from_outcome` convert both ways (a partial Worker maps to the graph's
  `blocked`, never to `succeeded`), each settled `WorkerOutcome` carries its report,
  and the gaps a Worker declares reach the Subagent's aggregate instead of being
  re-invented there.

## Subagent quality review

After every Worker result — including a failed, blocked, deferred or resumed one —
its parent Subagent judges it on seven dimensions and records a **pass** or a
**revise**, with the concrete deficiency and what to change. Nothing reaches the
Subagent's aggregate unreviewed.

```bash
python vedant_osint.py review --self-test        # 100 review checks, offline
python vedant_osint.py review --demo             # six results, four decisions
python vedant_osint.py review --check report.json --schema EvidenceSet --scope example.com
```

- **Seven dimensions, each able to bite.** `completeness` (criteria and expected
  volume), `relevance` (the finding is about *this* unit's slice), `source-quality`
  (a secondary source cannot carry the claim; two-source confidence checked),
  `provenance` (every item locatable, every finding citing evidence the report
  holds), `consistency` (status vs error vs limitations, duplicated statements),
  `scope` (every cited source inside the authorised entries) and `schema` (the shape
  the assignment named — `EvidenceSet`, `TimelineTable`, `HashManifest`, …).
- **A pass cannot carry a blocking deficiency, and a revise cannot omit one.** A
  revise with no deficiency, no guidance, or no retry is refused at construction, so
  "needs work" always arrives with the dimension, the detail and the fix.
- **A failed tool call and a poor successful call take different paths.** A failed
  call is `fault: tool` — retried while the budget allows, told to *try again*, and
  its deficiencies limited to the cause, not to the schema it could not fill. Poor
  work on a call that worked is `fault: worker` — revised with the specific
  deficiency and a different instruction, because re-running it unchanged would fail
  the same way. A blocked unit is neither: it stops with its reason.
- **Nothing is forwarded unreviewed.** The review sits inside the Worker's branch
  before the join: `HierarchicalFlow._judge` is the only exit, a bare outcome is
  refused by `require_review`, and the aggregate takes evidence only from results
  that passed — withheld units are named in `SubagentOutcome.withheld`, in the
  aggregate's own payload, and in the `flow --demo` summary.
- **The review is deterministic and offline.** It reads the record (status, evidence,
  limitations, schema) and never asks a model to grade a model: a grader that can be
  argued into a pass is not a control. The same result reviews identically twice.

## Targeted retasking

A review that says *revise* no longer buys the same prompt again. When retries remain,
the Worker's next assignment is rebuilt from the review — its own objective, the exact
deficiencies, the correction each implies, and the evidence already collected — and the
previous attempt is kept in history until the configured retry limit is reached.

```bash
python vedant_osint.py retask --self-test   # 82 retasking checks, offline
python vedant_osint.py retask --demo        # one retask, one repeat, one spent budget
python vedant_osint.py retask --next report.json --schema EvidenceSet --objective "…"
```

- **A retry is a retask.** `RetaskedWorker` carries the objective *unchanged*, the
  criteria, the output shape, one `RetaskItem` per dimension quoted from the review
  with its correction, and a `prompt` that restates all of it. A retask with no
  correction is refused at construction: repeating the instruction is exactly the
  behaviour the section exists to prevent.
- **"Specific" is a field, not a claim.** `retask_specificity` scores six signals —
  objective restated, deficiency quoted, correction given, evidence in hand stated,
  output shape named, not vague-only — and the flow's demo shows a 65-character
  directive beside the ~1.3 kB assignment it becomes.
- **The count is read, not re-derived.** `RetryBudget` records the Worker's own
  `max_attempts` and the Subagent's `ReviewPolicy`, the smaller binds, and the source
  of the ceiling is on the record. At the limit the unit returns `RETRY_EXHAUSTED` with
  a partial report naming every unresolved deficiency — the evidence its attempts did
  produce, at the status that admits what is missing.
- **Evidence is carried, not collected twice.** `carryable_evidence` forwards only
  items the review did not fault, only observations (never an inference), and never
  what the attempt itself inherited. The prompt lists them with their ids under
  *do not collect it again*; the history records what each attempt actually produced.
- **History is append-only.** `RetaskLedger` holds every attempt (status, decision,
  deficiencies, new evidence, the instruction it received) and every retask.
  `retask_fingerprint` digests the substance of an instruction, so a repeated prompt is
  detected even when re-worded — the demo shows one being caught.

## Subagent aggregation and readiness

A Subagent's report is a judgement of its team. It may not start until every Worker it
required has reached a terminal state, it may use only what the reviews forwarded, and
it must answer four questions in the record it writes: what was the same, what
disagreed, what failed, and whether its own completion criteria were met.

```bash
python vedant_osint.py aggregate --self-test   # 87 aggregation checks, offline
python vedant_osint.py aggregate --demo        # a merge, a disagreement, a bounded stop
python vedant_osint.py aggregate --next team.json   # aggregate reviewed results
```

- **Aggregation never begins early.** `check_ready` requires two independent facts per
  Worker — the branch reported settled *and* its outcome is in `terminal_states` — and
  raises `EarlyAggregate` naming the outstanding ids, so a mis-wired join fails loudly
  instead of summarising half a mission. The barrier travels in the report as
  `aggregate_basis`, so the aggregate carries the proof that it was not premature.
- **Duplicates are reconciled; corroboration is kept.** Rows whose claims normalise to
  the same statement collapse to one canonical row, the copies' ids move into its
  `supports`, and `Reconciliation` names which Worker also found it. Nothing is deleted:
  two Workers independently finding one thing is worth more than one of them.
- **Disagreements are preserved, never settled.** A `Disagreement` records both sides,
  the evidence each cites, and what would settle it. Picking the more confident side
  would delete the other Worker's finding, which is the failure this record prevents.
- **Failed subtasks stay visible.** Every withheld review becomes a `FailedSubtask` —
  status, gate, reason, attempts, and *what the mission loses* — and becomes a gap on
  the report. A failed unit is named, not merely absent from the evidence.
- **The Subagent judges its own criteria mechanically.** `assess_criteria` applies four
  tests (`at least N`, `every`/`each`, `integrity`/`hash`, `attributed`/`named`); a
  criterion it cannot test is reported unmet-but-checkable rather than silently met, and
  a met one must cite the evidence that met it.
- **One more Worker, bounded twice.** With a critical gap and budget it plans exactly
  one runtime Worker — narrow, one gap, one completion criterion — which runs through
  the *same* planning, review and retask path as the planned ones. Its number is capped
  by `FlowPolicy.max_runtime_workers_per_subagent` and by a `SpawnLedger` seat that
  cannot be topped up; with either exhausted the Subagent returns a bounded partial
  report naming what it could not get and why it stopped asking.

## Master review and bounded replanning

A Subagent judges its own team; the Master judges the mission. After the join it applies
five lenses to every report and then either finishes, stops, or opens one *bounded*
follow-up round.

```bash
python vedant_osint.py review-master --self-test   # 70 bounded-loop checks, offline
python vedant_osint.py review-master --demo        # five lenses, four endings
python vedant_osint.py review-master --next mission.json --objective "…"
```

- **Five lenses, each able to bite.** `relevance` (does what the report asserts or was
  assigned share subject matter with the objective?), `sufficiency` (evidence, a met
  join, and a stated consequence for everything it withheld), `contradictions` (does it
  disagree with another report *without recording it*?), `duplication` (does it restate
  another report that the aggregate never reconciled?) and `coverage` (which mission
  question or criterion does nobody satisfy?). Each lens answers for every report —
  including `not-applicable`, which is how "nothing to judge" stays distinguishable from
  "judged and fine".
- **A follow-up has two routes and both go through the gates.** An `existing` follow-up
  is one more runtime Worker for a Subagent that is already running, spent against
  `max_follow_up_workers_per_subagent` and the Subagent's own `SpawnLedger` licence — it
  never bypasses §36's gates because it *is* §36's path with a Master-chosen gap. A `new`
  follow-up spends a Master licence seat and its draft passes the same
  `validate_subagent_specs` that a plan does, so an unjustified follow-up is refused by
  the same code that refuses a bad plan.
- **The loop cannot run indefinitely.** Five independent bounds, each reported when it
  bites: `max_replan_rounds` (follow-up rounds), `max_master_reviews` (reviews — a
  separate number, because the *last* review is the `final`/`stop` decision), the Master's
  licence, the mission deadline, and saturation. Saturation is measured in claims, not
  rows: a round that produced only re-worded evidence has added nothing, whatever its
  row count says.
- **Every mission reaches a final or partial report.** `final` means the mission met its
  own stated completion criteria — judged by the same four mechanical rules the aggregate
  uses, applied to the whole mission's evidence. `stop` names the bound (`budget`,
  `deadline`, `blocked`, `saturation`) and lists every refusal, so a reader can see why it
  stopped asking instead of inferring it. A mission that finished never reports itself as
  cut short, and one that was cut short never claims to be finished.
- **The record is the evidence.** `FlowResult.master_reviews`, `.master_decisions` and
  `.follow_ups` carry the whole loop, and `master_rounds()` pairs each review with the
  round it opened and the evidence that round added — so "it was bounded" is a number a
  reader can check rather than a property the code claims about itself.

## Loop detection and saturation stopping

Retry budgets and round caps decide how long a cycle *may* run; this section decides
whether it is a cycle at all, and what to do about it. It reads the record, detects the
loop in four forms, and escalates in the order the remedy implies.

- **Four detectors, one question each.** A **repeated query** (the same retrieval, in
  different words, adding nothing), a **repeated plan** (the same target and tools under a
  re-worded objective), a **repeated retask** (two attempts handed one instruction) and
  **diminishing returns** (different-looking attempts, no new claims). A **stalled round**
  is the mission-level form: a round that ran work and added no claim the mission did not
  already hold.
- **Repetition is judged on substance.** Queries are fingerprinted over normalised,
  sorted tokens, so "shodan search for example.com" and "search example.com on shodan" are
  one query; plans are fingerprinted over target, tools and work unit, so re-wording a
  retry cannot hide a repeat. Progress is counted in *new claims*, never in rows.
- **The escalation is a ladder, not a choice.** A first detection requires the responsible
  agent to change strategy: the correction is carried by the retask itself, and a retask
  whose fingerprint would not move is refused rather than issued. A unit that repeats
  after its correction has its line of inquiry **blocked** — it stops being asked, the
  record says what would unblock it, and the block travels into the report as a gap and a
  limitation. A mission whose rounds stop adding claims **stops**, with the series it
  judged on the record.
- **No instruction may be unbounded.** "Continue until…", "keep searching", "exhaust
  every source" are refused wherever this build accepts an instruction — a runtime
  Worker's objective, a follow-up — because a loop detector cannot catch an instruction
  that has no end condition for the mission to test.
- **The reason is a finding, not a log line.** `FlowResult.loops` carries every
  correction (with whether any attempt carried it), every blocked line, the claims added
  per round, and the stop condition it justified; `loop_summary` is the same in counts.

```
python vedant_osint.py loops --self-test                # 52 loop-detection checks
python vedant_osint.py loops --demo                     # correct, block, stop
python vedant_osint.py loops --reports mission.json --evidence 4,0,0
```

## Evidence-based Master synthesis

The mission produces one document, and the thing it must not do is conclude more than it
can show. The report is assembled from the reviewed record — not written freehand — in ten
sections: executive summary, scope and methods, key findings, corroborated indicators,
competing hypotheses, contradictions, confidence levels, evidence gaps, limitations and
recommended lawful next steps.

- **Every key finding links to evidence IDs.** A `KeyFinding` cannot be constructed without
  them, and every id must exist in the mission's own evidence; an id nobody collected is
  refused at assembly. Findings are deduplicated by claim, so two Workers that retrieved the
  same fact are one finding with two citations rather than two findings.
- **No conclusion exceeds its supporting evidence.** Confidence is derived twice: from the
  number of independent origins (one → single-source, two → corroborated, three or more →
  well-corroborated, counted the way the research audit counts them) and then capped by the
  claim's epistemic kind — an allegation can never be more than corroborated, because a
  third party repeating a claim does not establish it, and an inference is capped at
  corroborated, because reasoning over good evidence is still reasoning. A stated level
  above the derived band is refused. The report's overall confidence is the *weakest*
  finding that carries the answer, never an average and never the strongest.
- **Contradictions are preserved, not settled.** Two statements whose subjects overlap and
  whose polarity differs are recorded with both sides, the rule that found the conflict, and
  what would resolve it. Picking a side without new evidence would delete a finding.
- **No declarations of guilt, no certain identity attribution.** "Guilty", "the attacker",
  "is the person who" are refused wherever a report states anything; an identity claim
  survives only as a hypothesis with its basis and the test that would decide it. There is
  no field for a verdict, because a document with such a field acquires an answer to it.
- **What the mission could not establish is a section, not silence.** Gaps carry the
  reason, the consequence (*what the report therefore cannot say*) and what would close
  them; hypotheses the mission could not test are listed as untested; blocked lines from
  loop detection arrive as withheld lines.
- **Recommended next steps are lawful by construction.** Each names the gap it addresses,
  asserts it stays inside the mission's scope and authorisation, and must be passive — this
  build plans passive collection, and a recommendation is a plan.

The document is assembled, asserted against its own acceptance clause, and only then
returned: a report that cannot show a citation for a finding, or that states a level above
what its origins and its claim's kind allow, is refused rather than printed. The executive
summary is written last and may count what is still open — it may never claim to have
excluded the alternatives, because excluding one takes evidence, not silence.

```
python vedant_osint.py synthesis --self-test              # 50 calibration checks
python vedant_osint.py synthesis --demo                   # one claim, three evidence bases
python vedant_osint.py synthesis --reports mission.json   # assemble the document
```

## Output formats

A finished mission is written three ways, and they cannot disagree: Markdown for a person,
JSON for a machine, and a bounded terminal summary for the screen. All three are views of
one `MissionDossier` assembled from the reviewed record, so a fact that is not in the JSON
is not in the Markdown either — the JSON is the authority and the other two are renderings.

```
python vedant_osint.py report --self-test                    # 283 checks: formats, presentation, audit, dry run/mock
python vedant_osint.py report --demo                         # one mission, three formats
python vedant_osint.py flow --demo exposure --json > m.json
python vedant_osint.py report --mission m.json --out-dir out/ # writes m.md and m.json
python vedant_osint.py report --reports mission.json -o "…"   # no graph run needed
python vedant_osint.py report --mission m.json --summary      # screen only
```

- **Reports open correctly.** The Markdown is a real document: one title, twenty sections
  in reading order, pipe tables whose rows are padded and whose cells escape `|`, and text
  that cannot start a Markdown construct — an evidence statement is quoted input, and
  quoted input must not be able to rewrite the report's structure.
- **The JSON validates against the report model.** `MissionDossier.load` re-parses every
  written record and refuses one that has drifted (`format_version`, a missing report, a
  finding with no citation), and `MissionDossier.json_schema()` publishes the contract. A
  file that is merely well-formed JSON is not a mission record.
- **The terminal output stays concise.** The summary answers six questions and stops: what
  was asked, what was found, how sure, what is missing, what it cost, why it ended. It has
  a line budget and a width budget, both checked, and it never prints the evidence table.
- **The sections behind the answer are sections.** Source register (one row per origin,
  with its digest or an explicit "not hashed"), evidence table (every item, its weight, and
  which findings cite it — uncited items are listed rather than removed), agent and task
  execution (every Worker that ran, including runtime and follow-up Workers the plan never
  knew about), errors, retry history (with a computed "changed / repeated" column), time
  usage (both clocks, reconciled), and the stopping reason.
- **Hashes and custody survive.** Every forensic artefact reaches the chain-of-custody
  sheet with its algorithm and digest, who handled it, how, when, whether it was preserved
  and its custody events. An artefact with no digest, or one that was only read, is listed
  with that fact rather than omitted: a table that only showed the well-preserved artefact
  would be the one thing a forensic report must not be.

## Mission presentation

`flow` ends on one screen: what the mission produced, in the shape a reader needs before
they open anything. It is rendered from the same dossier the report is written from, so the
screen and the document cannot disagree about what happened.

```
python vedant_osint.py flow --demo exposure                    # presentation + flow detail
python vedant_osint.py report --mission m.json --present       # the same screen, for a saved mission
python vedant_osint.py report --present-demo                   # all four outcomes, from real runs
python vedant_osint.py report --present-demo --outcome blocked  # just one
```

- **Four outcomes, one vocabulary.** `completed` (green ✔), `partial` (yellow ◐), `blocked`
  (cyan ⊘), `failed` (red ✘). The words and colours are the ones the report already uses for
  a task's status, so a reader learns them once; `partial` exits `0` because it is a result,
  `blocked` exits `POLICY`, `failed` exits `INTERNAL`.
- **The outcome is derived, not chosen.** It is read from the record: no finding that
  survived review is `failed`; a mission stopped before it could synthesise, or whose
  Subagents all came back blocked, is `blocked`; anything withheld, failed, deferred or left
  as a gap — or a mission that ended on a bound instead of a finish — is `partial`. A
  `SEVERE` warning raises the outcome to `partial`, a `FATAL` one to `failed`.
- **One screen answers the question.** Mission, objective, duration, confidence and its
  basis; the counts of Subagents and Workers (planned, runtime, follow-up) with completed,
  failed, blocked and withheld; the evidence totals that matter (items, cited, origins,
  corroborated, gaps); the strongest findings, each with its evidence band; the risks worth
  naming; the units that did not arrive, by name; and where the report and log are.
- **The screen is not the record.** Findings are shortened to a sentence — at a word
  boundary, marked with an ellipsis — and the footer says the full evidence,
  contradictions and custody are in the report. Nothing the presentation prints is a claim
  the report does not make.
- **A finding's mark is its evidence, not the mission's outcome.** A single-source finding
  inside a successful mission shows ◐, never ✔: the outcome's styling describes the mission,
  and borrowing it for a weak claim is how a report starts flattering itself.
- **Warnings say what they cost.** Every warning names its cause, its consequence and where
  it applies, graded `info` · `notice` ! `severe` ▲ `fatal` ✘.

## Reproducibility and audit metadata

Every report carries an audit block, so a second operator can see what was run and run it
again — without being handed a secret.

```
python vedant_osint.py report --mission m.json --audit   # the block, and its clause
python vedant_osint.py flow --demo exposure              # the screen names it and the retention note
```

The Markdown gains eleven headings under `## Audit and reproducibility` and the
JSON an `audit` object:

- **Environment** — application version and label, build phase, record format, Python and
  platform, machine, user agent, the command that produced the file, the operator's chosen
  name, and whether the process looked like CI. Nothing here is read at render time: a
  dossier rendered tomorrow still describes the machine the mission ran on.
- **Configuration** — the non-secret settings that shaped the run, each with where its value
  came from (`cli` / environment / default). Driven by the *name* of every setting, so a
  field added later is captured automatically and a secret-shaped one is redacted
  automatically: a credential is recorded as `<redacted: set, value not recorded>`, because
  *set* and *unset* are different facts.
- **Models** — provider, model id, base URL, and the credential's *state* ("configured",
  "absent (looked in …)"), never its value.
- **Mission scope and limits** — the objective, mode, authorised scope and exclusions, the
  tools available, the completion criteria and questions, and the limits the mission was
  admitted under. Read from the admission context, not inferred from the objective sentence.
- **Timestamps** — mission start and end (wall-clock, carried from the run), the recording
  time, the measured duration, and per-stage spans from the ledger.
- **Dynamic hierarchy** — every unit that ran, with its parent, status, attempts and origin,
  as a tree. `runtime` and `follow-up` origins are the units the mission invented after its
  plan was made; a record that showed only the plan would describe a mission that did not
  happen.
- **Tool failures** — every failure that names a tool, with the tool, the unit, the fault,
  the attempt and what the graph did about it (retried, retasked, withheld, blocked).
- **Stopping reason (audit)** — the same wording as the stopping section, pointed at it
  rather than copied, so the two cannot disagree.
- **Reproduction** — numbered commands that rebuild the mission's setup. They reproduce the
  *procedure*, not the answer: a re-run collects whatever the world says now.
- **What is deliberately not recorded** — the omissions and why: API keys, cookies and
  browser session state, browser profile contents, page content beyond the cited findings,
  prompts and raw completions, and the operator's home directory.
- **Retention** — the note that travels *in* the document: this is investigation data, it can
  contain personal data and third-party material, keep it on access-controlled storage, keep
  the custody sheet with its artefacts, and delete it on your own schedule. The tool records
  what happened and does not decide how long the record may be kept.
- **Audit clause** — the acceptance clause evaluated and carried: reproducible, no secrets,
  retention stated, and every claim the record makes about itself, with what could not be
  confirmed named rather than rounded up.

**The scan is not a promise.** `write_dossier` renders the exact text it is about to write
and searches it for the credential values this process can see, the credential *shapes*
anything could carry (provider prefixes, bearer tokens, cookies, private keys, connection
strings, JSON or `key=value` credential fields), and the *structure* of a credential store.
A match raises `OutputError` and **nothing is written** — a file that names a leak and is
written anyway has documented the leak instead of preventing it. The scan's result, and the
clause it produced, are recorded in the file that passed it. Findings name a location, never
a value: a scan report that quoted the secret it found would be the leak it was checking for.

## Dry run and mock mode

Two modes, one purpose: see what a mission would do before it does anything, and exercise the
whole orchestration — hierarchy, review loops, retries, reports — with nothing switched on.

```bash
python vedant_osint.py flow --dry-run -t example.com -o "…"   # validate, plan, execute nothing
python vedant_osint.py flow --dry-run -t example.com -o "…" --json > plan.json
python vedant_osint.py flow --mock                            # the real graph, mock adapters
python vedant_osint.py flow --mock --mock-scenario revise      # pass | revise | flaky | break
python vedant_osint.py flow --mock --out-dir out/ --allow-mock-output   # and write the report
```

- **A dry run validates and plans, and cannot execute.** It runs the same gate a real mission
  runs — objective, scope, authorisation, limits — builds the real hierarchy and the compiled
  node set, and predicts the bounds the policy implies: attempts per unit, the worst-case
  number of Worker runs, review rounds, Master reviews, replan rounds and dependency waves.
  The plan is a `PlanReport`, deliberately *not* a `FlowResult`: a type that could be mistaken
  for a run would let a report be written about a mission that never happened.
- **The refusal is a guard, not a convention.** `effect_boundary` closes the four ways a
  mission reaches the world — model, network, browser, forensic — for the duration of a dry
  run, and `require_effect` raises `DryRunViolation` at the boundary rather than at each call
  site. `DryRunRunner` is the last line: every method refuses, so a caller that built a flow
  anyway cannot collect by accident.
- **A dry run says where its plan came from.** Without a Master there is no decomposition to
  show, so the structure is a scripted team shape — and the plan says so, in the screen, in
  the JSON (`structure_source`), and in the plan file, which also records `executed: false`
  and no reports at all. The gate's verdict travels with it: a refused objective produces a
  plan with `cleared: false`, the gate's reasons under `refusals`, and the gate's exit code.
- **A mock run executes the real graph over deterministic adapters.** `--mock` keeps
  everything above the runner — fan-out, Worker review, retasking, aggregation, Master review
  and replanning, synthesis, the dossier — and replaces only the two things that would reach
  the world: a model that answers from a table, and a tool layer that returns a scripted row
  per capability and can be told to fail. `--mock-scenario revise` makes every first review
  ask for another attempt, `flaky` fails one tool once and recovers, `break` never recovers
  and stops the mission with a gap it reports.
- **Determinism is a property, not an intention.** The clock is logical (ten milliseconds per
  attempt, not a measured elapsed time), the tool answer is derived from the capability and
  the subject, and the model answer from role and attempt. Two runs of the same scenario
  produce the same mission id, the same evidence ids, the same statuses, the same retries and
  the same cost — which is what makes the mode usable in a test that asserts them.
- **Mock output is labelled where a reader will look.** Every evidence item carries the
  `mock-evidence` tag, the `MOCK OUTPUT — … not collected from any source` confidence basis,
  and a `MOCK:example.com` locator in the source register — three places, because a reader
  may look at any one of them, and the locator is the one a later edit cannot quietly drop.
  The report's own voice says it too: a `[MOCK]` summary and claims, unknown confidence, the
  limitation first in the list, a `MOCK-MISSION — NOT EVIDENCE` note above the title's
  metadata, and `run mode: mock` in the header. The audit record's `environment.mode` says
  `mock`, and the terminal banner repeats it.
- **A mock report cannot be written as if it were real.** `write_dossier` asks whether the
  record says it is mock output; if it does, the write is refused with `MockAsReal` unless
  the operator passed `--allow-mock-output` (exit `POLICY`, exit code 7, nothing written).
  The same check runs when a written record is re-rendered through `report --mission`, so a
  record that was rebuilt from a file gets the same answer as the run that wrote it.
- **What a run cost is modelled, not billed.** `offline_cost` reads the spend off the record
  — Worker runs, scripted tool calls, model calls — and sets it against the plan's worst case,
  with the caveat printed beside it. An offline run spends nothing, and a cost report that
  implied otherwise would be the same kind of lie as unlabelled evidence.
- **A stopped mission still has a screen.** A mock scenario that fails has no synthesis and
  therefore no dossier; `build_stopped_presentation` presents its record — outcome, counts,
  the reason it stopped, the evidence it did collect — so the failure is visible rather than
  turning into an error message.

`report --self-test` covers the acceptance clause in 66 checks of its own (283 in total):
the dry run plans and refuses to execute, the mock run exercises the hierarchy, the review
loops, the retries and the reports, a scoped tool failure changes what the plan predicted,
the labels survive into the Markdown, the JSON, the audit record and the presentation, and a
second run is identical to the first.

## Status

| Phase | Scope | State |
|-------|-------|-------|
| 1 | Foundation — CLI skeleton, config probing, version reporting | ✅ done |
| 2 | Contracts — settings, `doctor`, preflight, models, state, renderer, lifecycle, resilience, model adapter | ✅ done |
| 3 | Orchestration — Master Agent (only fixed agent), runtime Subagent/Worker factories, LangGraph execution flow, bounded concurrency and budgets | 🟡 started (Master Agent, Subagent and Worker specifications, execution flow, admission control, Worker outcome contract, Subagent quality review, targeted Worker retasking, Subagent aggregation with bounded runtime Workers, Master review with bounded replanning, loop detection with strategy change, blocked lines and saturation stops, evidence-based Master synthesis with cited findings and calibrated confidence) |
| 4 | Browser — browser-use / Playwright sessions and capture | 🟡 started (policy, scope, capture, guarded closure, agent mode) |
| 5 | Collection — passive OSINT sources, artefact hashing | 🟡 started (source-aware web research; safe document/page extraction with injection defence; read-only artifact manifests, hashing and access ledger) |
| 6 | Synthesis — cross-source correlation and reporting | 🟡 started (deterministic timelines, explained indicator correlation, content de-duplication, the evidence-based Master report with citations and calibrated confidence, Markdown/JSON/terminal output formats with a source register, execution summary and chain of custody, the Rich mission presentation with four derived outcomes) |
| 7 | Operations — resume, budgets, audit trail, hardening | 🟡 started (checkpoints, resumable missions, capability router, budgets, reproducibility and audit metadata with a secret-refusing write, deterministic dry-run planning and a labelled mock mode) |

## Install

```bash
pip install typer rich pydantic langgraph browser-use playwright httpx python-dotenv
python -m playwright install chromium
```

Required environment: `ARGUS_LLM_MODEL` (from Phase 3), plus the API key for the
chosen provider. See the module docstring in `vedant_osint.py` for the full list.
