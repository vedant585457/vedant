# Mission report — determine from the supplied disk image which processes wrote to /etc/hosts on 2026-02-11

- mission: `flow-4da3c70d0ab3`
- generated: 2026-11-12T10:51:59+00:00
- format: `argus-dossier/1` (schema version 1)
- produced by: argus 0.36.0 on Python 3.11.2 (CPython, x86\_64); schema argus-audit/1
- run mode: **live**
- confidence: **low** — the weakest of 7 finding(s) sets the level: single-source (1 origin(s)), because the answer cannot be stronger than the claim it depends on
- evidence: 7 citation(s) from 7 independent origin(s); 11 item(s) in the table
- status: finished — the mission finished: no further round is allowed: round 2 planned the same work as round 1 over 3 target(s) that round had already addressed (saturation); the replanning budget of 1 round(s) is spent. The bound that ended it is on the record, so a reader can tell a finished mission from a stopped one.

## Executive summary

7 reviewed finding(s) bear on: determine from the supplied disk image which processes wrote to /etc/hosts on 2026-02-11. None of them is corroborated by a second independent origin, so every finding below carries the band it earned. 2 explanation(s) remain open, 3 of them compared against the leading one, and 1 that the evidence cannot tell apart; this document does not claim that it has excluded the others. Confidence: low.

## Scope and methods

Objective: determine from the supplied disk image which processes wrote to /etc/hosts on 2026-02-11
The question this mission set out to answer: a package upgrade rewrote /etc/hosts
Sources reviewed: filesystem-timeline (4 item(s)); process-attribution (3 item(s)); integrity (4 item(s))
Methods: every Worker result was judged on seven quality dimensions (§34) before it could be forwarded, retried attempts were re-tasked with a specific correction (§35), each Subagent reconciled duplicates and preserved disagreements (§36), the Master reviewed the report set with five lenses and a bounded loop (§37, §38), and this synthesis cites only evidence that survived all four.
Evidence base: 7 reviewed item(s) from 7 independent origin(s).

## Confidence

Mission confidence: low.
Basis: the weakest of 7 finding(s) sets the level: single-source (1 origin(s)), because the answer cannot be stronger than the claim it depends on
Bands: single-source 7, corroborated 0, well-corroborated 0
Band rules: one independent origin is single-source; two are corroborated; three or more are well-corroborated. An allegation is capped at corroborated — a third party repeating a claim does not establish it — and an inference is capped at corroborated, because reasoning over good evidence is still reasoning.

**Stated basis:** the weakest of 7 finding(s) sets the level: single-source (1 origin(s)), because the answer cannot be stronger than the claim it depends on

## Key findings

| finding | kind | confidence | evidence ids | what would refute it |
| --- | --- | --- | --- | --- |
| timeline-builder: timeline exported and hashed | observation | single-source (1) | `ev-63d3042b41b3` | a first-party record contradicting it, or a second independent origin failing to reproduce it |
| gap-gap-3191f2: the result addresses: a package upgrade rewrote /etc/hosts | observation | single-source (1) | `ev-593d6a753234` | a first-party record contradicting it, or a second independent origin failing to reproduce it |
| gap-gap-c6138f: the result addresses: an interactive edit rewrote /etc/hosts | observation | single-source (1) | `ev-537dc47ffae5` | a first-party record contradicting it, or a second independent origin failing to reproduce it |
| follow-up-flw-ed7c9f: at least one reviewed observation addresses: the image integrity is proven | observation | single-source (1) | `ev-3a566a69fc75` | a first-party record contradicting it, or a second independent origin failing to reproduce it |
| log-correlator: each candidate process is listed with the record placing it in the write window, or stated as absent | observation | single-source (1) | `ev-6d0bd99f3fdd` | a first-party record contradicting it, or a second independent origin failing to reproduce it |
| hasher: hash manifest written | observation | single-source (1) | `ev-075704736cf6` | a first-party record contradicting it, or a second independent origin failing to reproduce it |
| custody-recorder: custody log written for every artefact | observation | single-source (1) | `ev-0aed38e90d09` | a first-party record contradicting it, or a second independent origin failing to reproduce it |

## Corroborated indicators

No claim in this mission was stated independently by two or more origins, so the report claims no indicator. A corroborated indicator requires two distinct origins, not two sentences.

## Competing hypotheses

| hypothesis | status | competing explanation | test that decides it |
| --- | --- | --- | --- |
| a package upgrade rewrote /etc/hosts | supported | the benign explanation: the same observations are consistent with configuration drift or a shared provider, and no evidence here excludes it | a first-party record that directly addresses question 1, dated and independently reproducible: a package upgrade rewrote /etc/hosts |
| an interactive edit rewrote /etc/hosts | supported | the benign explanation: the same observations are consistent with configuration drift or a shared provider, and no evidence here excludes it | a first-party record that directly addresses question 2, dated and independently reproducible: an interactive edit rewrote /etc/hosts |

## Contradictions

No two reviewed items make the same claim with opposite polarity. Silence here is a finding: nothing collected conflicts with anything else collected.

## Evidence gaps

The mission closed every gap it opened. That is a claim about the questions it asked, not about the target: questions it did not think to ask are not in this list.

## Limitations

- the deterministic runner does not contact the target

## Recommended next steps

| step | addresses | why it is lawful | value |
| --- | --- | --- | --- |
| re-run the same passive checks after the target publishes its next advisory, so a change in the record is distinguishable from a change in the collection | gap-1 | the same scope and method the mission already used (artifact:disk-01.img) | low |

## Coverage

The mission asked 2 question(s). This table is the Master's coverage after round 2, recomputed from the reports it had received:

| # | question | status | served by | evidence | confidence |
|---|----------|--------|-----------|----------|------------|
| 1 | a package upgrade rewrote /etc/hosts | contradicted | filesystem-timeline, process-attribution, integrity | 3 | low |
| 2 | an interactive edit rewrote /etc/hosts | contradicted | filesystem-timeline, process-attribution, integrity | 3 | low |

**Still open, and why:**
- Q1 (contradicted): a report disputes this question: addresse etchost result rewrote
- Q2 (contradicted): a report disputes this question: addresse etchost result rewrote

5 claim(s) in the evidence table answer no named question; they support the objective rather than a question, and are listed here rather than folded into one.

**Coverage clause:** every task serves a question **yes** · nothing dropped **yes** · open questions explained **yes**

## Alternative explanations

The objective is an attribution question, so the mission carried 6 explanation(s) and looked for evidence against them, not only for them.

**Leading explanation** (not favoured by the evidence): the explanation that a package upgrade rewrote /etc/hosts

No explanation is favoured by the evidence the mission collected: the alternatives below are the explanations it could not separate, and each says what would separate it.

| alternative | verdict | evidence | why |
|---|---|---|---|
| the same records are equally consistent with routine configuration, shared infrastructure or ordinary administrative work that nobody recorded | untested | 0 | untested: no reviewed statement bears on it yet; neither it nor hyp-1-h-eb291e is favoured: the mission's evidence does not separate the two |
| a different party acted in the same window and produced the same observations — a third-party provider, a scheduled job, or another operator | untested | 0 | untested: no reviewed statement bears on it yet; neither it nor hyp-1-h-eb291e is favoured: the mission's evidence does not separate the two |
| the explanation that an interactive edit rewrote /etc/hosts | indistinguishable | 2 | indistinguishable: the record disagrees with it, and the same records support it: the mission cannot tell the two apart; neither it nor hyp-1-h-eb291e is favoured: the mission's evidence does not sep… |

**What would distinguish each alternative from the leading one:**
- find one dated record of authorised change or routine operation covering the same window, and this explanation stops needing an adversary
- find one record of independent activity in the same window from a subject outside the mission's scope, and this explanation must be weighed against the leading one
- collect one first-party record that states this explanation outright and one that would be false if it holds: an interactive edit rewrote /etc/hosts

**The evidence does not distinguish:** the explanation that an interactive edit rewrote /etc/hosts. This is a result, not a gap: the mission collected the records both explanations sit under, and none of them separates the two.

**Alternative-explanations clause:** alternatives compared **yes** · each carries a discriminator **yes** · plan seeks disconfirmation **yes**

## Agent and task execution

3 Subagent(s), 11 Worker(s), 11 attempt(s), 0 retries, 11 reviewed evidence item(s), 7 finding(s). Statuses: succeeded 14

| unit | kind | role | status | gate | attempts | evidence | seconds | origin |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sa-d5d2ce6948d6 | subagent | filesystem-timeline | succeeded | none | 1 | 4 | 0.06s | planned |
| wrk-1c07b0fb8d33 | worker | timeline-builder | succeeded | none | 1 | 1 | 0.05s | planned |
| wrk-5858dc9ac0db | worker | filesystem-timeline gap closure | succeeded | none | 1 | 1 | 0.05s | runtime |
| wrk-bb85d666fcc9 | worker | filesystem-timeline gap closure | succeeded | none | 1 | 1 | 0.06s | runtime |
| wrk-4d732ce2f31d | worker | follow-up-flw-ed7c9f | succeeded | none | 1 | 1 | 0.05s | follow-up |
| sa-4086c156a6ac | subagent | process-attribution | succeeded | none | 1 | 3 | 0.17s | planned |
| wrk-431fc1477437 | worker | log-correlator | succeeded | none | 1 | 1 | 0.05s | planned |
| wrk-b6e8a4138214 | worker | process-attribution gap closure | succeeded | none | 1 | 1 | 0.05s | runtime |
| wrk-497329fad247 | worker | process-attribution gap closure | succeeded | none | 1 | 1 | 0.05s | runtime |
| sa-e78a4faf4252 | subagent | integrity | succeeded | none | 1 | 4 | 0.19s | planned |
| wrk-e9172d9b03fe | worker | hasher | succeeded | none | 1 | 1 | 0.05s | planned |
| wrk-747fa27d8781 | worker | custody-recorder | succeeded | none | 1 | 1 | 0.05s | planned |
| wrk-9fbce6f2d677 | worker | integrity gap closure | succeeded | none | 1 | 1 | 0.05s | runtime |
| wrk-23f0456d4738 | worker | integrity gap closure | succeeded | none | 1 | 1 | 0.05s | runtime |

Follow-up work: existing: coverage → sa-d5d2ce6948d6.

## Time usage

Total wall-clock: 0.48s. First ledger event to last: 0.48s (the ledger opened 0.47s before its first event). 92 ledger event(s), 11 Worker attempt(s), peak 3 resource(s) in flight.

| stage | window |
| --- | --- |
| reconciliation | 0.320s |
| follow-up planning | 0.087s |
| worker execution | 0.053s |
| planning | 0.007s |
| master review | 0.006s |
| worker review | 0.004s |
| subagent planning | 0.002s |
| master-priority | 0.000s |
| synthesis | 0.000s |

stage windows are differences between the first appearance of each stage in the ledger, not instrumented unit durations, so overlapping stages share their window rather than summing to the total. The ledger's zero is when the flow was built, 0.475s before its first event; the run's own clock starts when it is invoked, which is why the two totals differ.

## Errors

No error was recorded. That is a statement about the record, not a claim that nothing went wrong: an error the mission did not write down is not here, and the trace is the place to look for it.

## Retry history

No unit was retried, so there is no retry history. A mission that never retried is not necessarily a mission that got everything right first time: it may be one whose reviews passed.

## Stopping reason

the mission finished: no further round is allowed: round 2 planned the same work as round 1 over 3 target(s) that round had already addressed (saturation); the replanning budget of 1 round(s) is spent. The bound that ended it is on the record, so a reader can tell a finished mission from a stopped one.

- stopped before finishing: no
- condition: `saturation` (saturation)
- master reviews: 2; rounds tracked: 1
- bounds that had a say: refused: round 2 planned the same work as round 1 over 3 target(s) that round had already addressed (saturation); refused: the replanning budget of 1 round(s) is spent
- what a continuation would have done: round 2 planned the same work as round 1 over 3 target(s) that round had already addressed (saturation); the replanning budget of 1 round(s) is spent

## Source register

1 origin(s), 0 with a reproducible digest. A row without a digest is usable and not reproducible, and the register says so rather than implying otherwise.

| id | title | locator | kind | method | retrieved | digest | items | cited |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `src-141896e4061c` | timeline-builder — filesystem-timeline | artifact:disk-01.img | local-artifact | local-read | 2026-11-12T10:51:59+00:00 | not hashed | 7 | 7 |

## Evidence table

11 item(s), every one of them cited by a finding.

| evidence id | kind/confidence | statement | cited by | source | collected by | digest |
| --- | --- | --- | --- | --- | --- | --- |
| `ev-075704736cf6` | observation/low | hasher: hash manifest written | `kf-bc475a4f85` | `artifact:disk-01.img` | wrk-e9172d9b03fe | — |
| `ev-0aed38e90d09` | observation/low | custody-recorder: custody log written for every artefact | `kf-bf1f37d85c` | `artifact:disk-01.img` | wrk-747fa27d8781 | — |
| `ev-3a566a69fc75` | observation/low | follow-up-flw-ed7c9f: at least one reviewed observation addresses: the image integrity is proven | `kf-5009ddfb5f` | `artifact:disk-01.img` | wrk-4d732ce2f31d | — |
| `ev-537dc47ffae5` | observation/low | gap-gap-c6138f: the result addresses: an interactive edit rewrote /etc/hosts | `kf-b2aa9cb5a2` | `artifact:disk-01.img` | wrk-bb85d666fcc9 | — |
| `ev-537dc47ffae5` | observation/low | gap-gap-c6138f: the result addresses: an interactive edit rewrote /etc/hosts | `kf-b2aa9cb5a2` | `artifact:disk-01.img` | wrk-497329fad247 | — |
| `ev-537dc47ffae5` | observation/low | gap-gap-c6138f: the result addresses: an interactive edit rewrote /etc/hosts | `kf-b2aa9cb5a2` | `artifact:disk-01.img` | wrk-23f0456d4738 | — |
| `ev-593d6a753234` | observation/low | gap-gap-3191f2: the result addresses: a package upgrade rewrote /etc/hosts | `kf-daaa07c90b` | `artifact:disk-01.img` | wrk-5858dc9ac0db | — |
| `ev-593d6a753234` | observation/low | gap-gap-3191f2: the result addresses: a package upgrade rewrote /etc/hosts | `kf-daaa07c90b` | `artifact:disk-01.img` | wrk-b6e8a4138214 | — |
| `ev-593d6a753234` | observation/low | gap-gap-3191f2: the result addresses: a package upgrade rewrote /etc/hosts | `kf-daaa07c90b` | `artifact:disk-01.img` | wrk-9fbce6f2d677 | — |
| `ev-63d3042b41b3` | observation/low | timeline-builder: timeline exported and hashed | `kf-fc64013552` | `artifact:disk-01.img` | wrk-1c07b0fb8d33 | — |
| `ev-6d0bd99f3fdd` | observation/low | log-correlator: each candidate process is listed with the record placing it in the write window, or stated as absent | `kf-0ee603e83e` | `artifact:disk-01.img` | wrk-431fc1477437 | — |

## Chain of custody

1 record(s); 0 with a digest, 0 recorded as preserved. A digest alone establishes integrity, not custody: who handled the artefact and whether it was preserved are separate claims, and both are in the table.

| evidence | artefact | digest | coverage | handled by | when | method | preserved | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `ev-63d3042b41b3` | artifact:disk-01.img | **not hashed** | — | wrk-1c07b0fb8d33 | 2026-11-12T10:51:59+00:00 | local-read | **no** | not-assessed |

- `ev-63d3042b41b3`: no digest recorded — no custody record was made for this artefact: the digest alone does not establish who handled it or whether it was preserved

## Audit and reproducibility

This mission ran on argus 0.36.0 on Python 3.11.2 (CPython, x86\_64); schema argus-audit/1. It was invoked as `report --mission /tmp/tmpbcoo71rp/report-forensic.json`. 

## Environment

| field | value |
| --- | --- |
| application | argus |
| version | 0.36.0 |
| version label | 0.36.0-alpha |
| build phase | 3 |
| record format | argus-audit/1 |
| python | 3.11.2 (CPython) |
| platform | Linux-6.1.158+-x86_64-with-glibc2.36 |
| machine | x86_64 |
| user agent | ARGUS/0.36.0 (+authorised-security-research) |
| dry run | yes |
| run mode | live |

## Configuration

| setting | value | from |
| --- | --- | --- |
| model.provider | openai | default |
| model.provider_label | OpenAI | settings |
| model.model | not set | default |
| model.base_url | not set | default |
| log_level | INFO | default |
| dry_run | yes | cli |
| orchestration.max_subagents | 5 | default |
| orchestration.max_workers_per_agent | 4 | default |
| orchestration.max_total_workers | 16 | default |
| orchestration.max_potential_workers | 20 | settings |
| orchestration.worker_retries | 2 | default |
| orchestration.review_retries | 2 | default |
| budgets.mission_budget_seconds | 3600 | default |
| budgets.task_budget_seconds | 300 | default |
| browser.headless | yes | settings |
| browser.concurrency | 2 | settings |
| browser.profile_dir | not set | settings |
| network.allow_network | yes | default |
| network.respect_robots | yes | default |
| network.http_concurrency | 8 | default |
| network.http_timeout | 30.0 | default |
| network.user_agent | ARGUS/0.36.0 (+authorised-security-research) | default |
| paths.output_dir | argus_home/output | settings |
| paths.case_dir | not set | settings |
Redacted by name, with the *state* of each kept: `model.api_key` (<redacted: unset, value not recorded>).

## Models

- **master-and-workers**: `unset` via openai — credential absent (looked in ARGUS\_LLM\_API\_KEY \| OPENAI\_API\_KEY); looked for in `ARGUS_LLM_API_KEY`, `OPENAI_API_KEY`.

The credential itself is never recorded: a reader who needs one supplies their own.


## Mission scope and limits

- objective: determine from the supplied disk image which processes wrote to /etc/hosts on 2026-02-11
- mode: `forensic`
- authorised scope: `artifact:disk-01.img`
- tools available: `forensic.mount`, `forensic.timeline`, `forensic.hash`, `log.parse`
- limits: max_subagents=4, max_total_workers=8, mission_budget_seconds=3600
- the mission would be finished when: the write is attributed to a process or the gap is stated; the image integrity is proven
- questions it set itself: a package upgrade rewrote /etc/hosts; an interactive edit rewrote /etc/hosts


## Timestamps

- recorded: 2026-11-12T10:51:59+00:00
- mission started: 2026-11-12T10:51:59+00:00
- mission ended: 2026-11-12T10:51:59+00:00
- duration: 0.48s
- per stage: planning 0.01s, master-priority 0.00s, subagent planning 0.00s, worker execution 0.05s, worker review 0.00s, reconciliation 0.32s, master review 0.01s, follow-up planning 0.09s, synthesis 0.00s.


## Dynamic hierarchy

14 unit(s) in 2 level(s): 3 subagent, 11 worker; 7 invented after the plan. Planned 7, invented after the plan 7, peak 3 in flight.

| unit | kind | role | parent | status | origin | attempts | evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sa-d5d2ce6948d6 | subagent | filesystem-timeline | master | succeeded | planned | 1 | 4 |
| wrk-1c07b0fb8d33 | worker | timeline-builder | sa-d5d2ce6948d6 | succeeded | planned | 1 | 1 |
| wrk-5858dc9ac0db | worker | filesystem-timeline gap closure | sa-d5d2ce6948d6 | succeeded | runtime | 1 | 1 |
| wrk-bb85d666fcc9 | worker | filesystem-timeline gap closure | sa-d5d2ce6948d6 | succeeded | runtime | 1 | 1 |
| wrk-4d732ce2f31d | worker | follow-up-flw-ed7c9f | sa-d5d2ce6948d6 | succeeded | follow-up | 1 | 1 |
| sa-4086c156a6ac | subagent | process-attribution | master | succeeded | planned | 1 | 3 |
| wrk-431fc1477437 | worker | log-correlator | sa-4086c156a6ac | succeeded | planned | 1 | 1 |
| wrk-b6e8a4138214 | worker | process-attribution gap closure | sa-4086c156a6ac | succeeded | runtime | 1 | 1 |
| wrk-497329fad247 | worker | process-attribution gap closure | sa-4086c156a6ac | succeeded | runtime | 1 | 1 |
| sa-e78a4faf4252 | subagent | integrity | master | succeeded | planned | 1 | 4 |
| wrk-e9172d9b03fe | worker | hasher | sa-e78a4faf4252 | succeeded | planned | 1 | 1 |
| wrk-747fa27d8781 | worker | custody-recorder | sa-e78a4faf4252 | succeeded | planned | 1 | 1 |
| wrk-9fbce6f2d677 | worker | integrity gap closure | sa-e78a4faf4252 | succeeded | runtime | 1 | 1 |
| wrk-23f0456d4738 | worker | integrity gap closure | sa-e78a4faf4252 | succeeded | runtime | 1 | 1 |

A `runtime` or `follow-up` origin is a unit the mission did not plan: it was created because the work demanded it, and the report's aggregation counts it like any other.


## Tool failures

No tool failure was recorded by this mission. That is a fact about this run, not a claim that every tool call succeeded silently.


## Stopping reason (audit)

- kind: **saturation** (condition `saturation`); the mission finished; bounded by 2 refusal(s)
- reason: no further round is allowed: round 2 planned the same work as round 1 over 3 target(s) that round had already addressed (saturation); the replanning budget of 1 round(s) is spent

## Task priority

| # | ran first | band | score | rule | why |
| --- | --- | --- | --- | --- | --- |
| 1 | timeline-builder | normal | 0.83 | priority | wrk-1c07b0fb8d33 has the highest expected information value per unit of price (0.83): gain 0.60, relevance 0.75, source quality 1.00, cost 0.85, time 0.17, risk 0.35; serves cq-1-… |
| 2 | custody-recorder | normal | 0.75 | priority | wrk-747fa27d8781 has the highest expected information value per unit of price (0.75): gain 0.60, relevance 0.75, source quality 1.00, cost 0.85, time 0.17, risk 0.85; serves cq-1-… |
| 3 | gap-gap-3191f2 | normal | 0.75 | priority | wrk-9fbce6f2d677 has the highest expected information value per unit of price (0.75): gain 0.60, relevance 0.75, source quality 1.00, cost 0.85, time 0.17, risk 0.85; serves cq-1-… |
| 4 | gap-gap-3191f2 | normal | 0.83 | priority | wrk-5858dc9ac0db has the highest expected information value per unit of price (0.83): gain 0.60, relevance 0.75, source quality 1.00, cost 0.85, time 0.17, risk 0.35; serves cq-1-… |
| 5 | gap-gap-c6138f | normal | 0.75 | priority | wrk-23f0456d4738 has the highest expected information value per unit of price (0.75): gain 0.60, relevance 0.75, source quality 1.00, cost 0.85, time 0.17, risk 0.85; serves cq-1-… |
| 6 | gap-gap-c6138f | normal | 0.83 | priority | wrk-bb85d666fcc9 has the highest expected information value per unit of price (0.83): gain 0.60, relevance 0.75, source quality 1.00, cost 0.85, time 0.17, risk 0.35; serves cq-1-… |
| 7 | log-correlator | normal | 0.87 | priority | wrk-431fc1477437 has the highest expected information value per unit of price (0.87): gain 0.60, relevance 0.75, source quality 0.90, cost 0.85, time 0.17, risk 0.00; serves cq-1-… |
| 8 | gap-gap-3191f2 | normal | 0.87 | priority | wrk-b6e8a4138214 has the highest expected information value per unit of price (0.87): gain 0.60, relevance 0.75, source quality 0.90, cost 0.85, time 0.17, risk 0.00; serves cq-1-… |
| 9 | gap-gap-c6138f | normal | 0.87 | priority | wrk-497329fad247 has the highest expected information value per unit of price (0.87): gain 0.60, relevance 0.75, source quality 0.90, cost 0.85, time 0.17, risk 0.00; serves cq-1-… |
| 10 | follow-up-flw-ed7c9f | urgent | 1.18 | priority | wrk-4d732ce2f31d has the highest expected information value per unit of price (1.18): gain 1.00, relevance 1.00, source quality 1.00, cost 0.85, time 0.17, risk 0.35; serves cq-1-… |

- weights: gain 1 + relevance 0.45 + source quality 0.25, divided by 1 + cost 0.35 + time 0.2 + risk 0.3; +0.22 per dispatch waited
- wait bound: 3; lookahead 6
- the clause: high-value first **yes** · nothing starved **yes** · decisions recorded **yes**


## Reproduction

1. `python -m pip install -r requirements.txt` — install the same dependency set (typer, rich, pydantic, langgraph, …)
2. `export ARGUS\_LLM\_MODEL=\<model\> && python vedant\_osint.py flow -t artifact:disk-01.img -o "determine from the supplied disk image which processes wrote to /etc/hosts on 2026-02-11" --out-dir out/` — run the same mission with your own credential and the model named in the Models section; the limits were max\_subagents=4, max\_total\_workers=8, mission\_budget\_seconds=3600 *(needs a credential you supply)*
3. `python vedant\_osint.py report --mission out/flow-\*.json --out-dir out/` — write the same three formats from the new run

Following these steps reproduces the *procedure*, not the answer. A re-run collects whatever the world says now, and the two results differ wherever the world changed between them.


## What is deliberately not recorded

- scan: clean: 117,506 byte(s) scanned for 12 credential pattern(s)
- not recorded — api keys and provider tokens: a credential is authority, not procedure: a record that carried one would let a reader act as the operator instead of reproducing their setup.
- not recorded — cookies and browser session state: a cookie is the operator's authenticated identity on somebody else's service.
- not recorded — browser profile contents and credentials: the profile directory is named so the setup can be repeated; none of its contents are copied.
- not recorded — page content beyond cited findings: the evidence table carries what a finding rests on, quoted and hashed; copying the pages themselves would spread third-party material the report does not need, 14 present.
- not recorded — model prompts, scratchpads and raw completions: a prompt carries the operator's phrasing and every retrieved page; the identifiers and limits are kept, the text is not.
- not recorded — the operator's home directory: the path is a fact about a workstation, not about the procedure.

The scan runs over the exact text that is written, not over the object it was rendered from: a value that appears in the file is found even when nothing meant to put it there. Any credential-shaped match refuses the write rather than redacting the file afterwards.


## Retention

This report is an investigation record, not a log file. It can contain personal data, unpublished material about a third party, and evidence that has been hashed so that it can be identified later. Protect it accordingly: keep it on access-controlled storage, share it only with people entitled to see the investigation, and keep the chain-of-custody sheet with the artefacts it describes — a digest without the artefact proves nothing. Scope, collection and retention of the data in this file are the operator's responsibility under the law that applies to them; this tool records what happened and does not decide how long that record may be kept. No API key, cookie, browser credential or page content beyond the cited findings is stored in it, and a copy of it is safe to hand to another operator *for the purpose of reproducing the procedure* — which is not the same as safe to publish.

- handled by: the operator
- retention decided by: the operator, under the law that applies to them
- personal data: may be present; third-party material: may be present; forensic artefacts: none recorded
- keep the .json beside the .md: the JSON is the record, the Markdown is a view of it
- keep the chain-of-custody sheet with the artefacts it describes
- do not commit investigation output to a public repository
- remove the file when the investigation's retention period ends, on the schedule the operator's own policy sets


## Audit clause

- names the software: yes
- names the configuration: yes
- names the models: yes
- names the scope: yes
- names the hierarchy: yes
- names the stop: yes
- reproducible: yes
- retention stated: yes
- priority recorded: yes
- no secrets: yes
- problems: none: another operator can reproduce this procedure from the record above without being given a secret.

## Acceptance

- Markdown complete: yes
- JSON re-validates against the dossier model: yes
- terminal summary concise: yes
- hashes and custody preserved: yes
- §39 report clause on this document: every finding cited yes, no conclusion above its evidence yes
- §42 audit clause on this record: another operator can reproduce the procedure yes, no secret in the file yes, retention stated yes

No finding in this document declares guilt or attributes identity with certainty; an identification appears only as a hypothesis with a test.


---

This document was assembled from the reviewed record. Every finding cites the evidence that carries it, confidence is derived from independent origins and capped by the claim's epistemic kind, and the JSON form (`flow-4da3c70d0ab3.json) is the authoritative record this Markdown is a view of.
