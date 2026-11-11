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
python vedant_osint.py sched --self-test      # bounded queues, deadlines, licences
python vedant_osint.py resume --self-test     # checkpointing and resumable missions
python vedant_osint.py router --self-test     # the controlled capability router
python vedant_osint.py browser --self-test    # browser research, guaranteed closure
python vedant_osint.py research --self-test   # source-aware web research
python vedant_osint.py extract --self-test    # bounded, untrusted document extraction
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
python vedant_osint.py flow --self-test        # 60 guarantee checks, offline
python vedant_osint.py flow --demo exposure    # summary + ledger + joins
python vedant_osint.py flow --demo compare     # one structure, two widths
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

## Status

| Phase | Scope | State |
|-------|-------|-------|
| 1 | Foundation — CLI skeleton, config probing, version reporting | ✅ done |
| 2 | Contracts — settings, `doctor`, preflight, models, state, renderer, lifecycle, resilience, model adapter | ✅ done |
| 3 | Orchestration — Master Agent (only fixed agent), runtime Subagent/Worker factories, LangGraph execution flow, bounded concurrency and budgets | 🟡 started (Master Agent, Subagent and Worker specifications, execution flow, admission control) |
| 4 | Browser — browser-use / Playwright sessions and capture | 🟡 started (policy, scope, capture, guarded closure, agent mode) |
| 5 | Collection — passive OSINT sources, artefact hashing | 🟡 started (source-aware web research; safe document/page extraction with injection defence) |
| 6 | Synthesis — cross-source correlation and reporting | ⬜ |
| 7 | Operations — resume, budgets, audit trail, hardening | 🟡 started (checkpoints, resumable missions, capability router, budgets) |

## Install

```bash
pip install typer rich pydantic langgraph browser-use playwright httpx python-dotenv
python -m playwright install chromium
```

Required environment: `ARGUS_LLM_MODEL` (from Phase 3), plus the API key for the
chosen provider. See the module docstring in `vedant_osint.py` for the full list.
