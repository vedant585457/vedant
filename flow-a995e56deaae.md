# Mission report — map the publicly documented exposure of example.com and rank the advisory-backed risks

- mission: `flow-a995e56deaae`
- generated: 2026-11-11T11:20:21+00:00
- format: `argus-dossier/1` (schema version 1)
- produced by: argus 0.32.0 on Python 3.11.2 (CPython, x86\_64); schema argus-audit/1
- confidence: **low** — the weakest of 5 finding(s) sets the level: single-source (1 origin(s)), because the answer cannot be stronger than the claim it depends on
- evidence: 5 citation(s) from 5 independent origin(s); 6 item(s) in the table
- status: finished — the mission finished: the run completed and recorded no stopping bound, so this dossier reports the absence rather than inventing one. No stopping decision was part of this file, so the reason above is the whole of what the record says.

## Executive summary

5 reviewed finding(s) bear on: map the publicly documented exposure of example.com and rank the advisory-backed risks. None of them is corroborated by a second independent origin, so every finding below carries the band it earned. 1 explanation(s) remain open; this document does not claim that it has excluded the others. Confidence: low.

## Scope and methods

Objective: map the publicly documented exposure of example.com and rank the advisory-backed risks
The question this mission set out to answer: the published advisories name the affected component
Sources reviewed: published-advisories (3 item(s)); dns-and-archive (3 item(s))
Methods: every Worker result was judged on seven quality dimensions (§34) before it could be forwarded, retried attempts were re-tasked with a specific correction (§35), each Subagent reconciled duplicates and preserved disagreements (§36), the Master reviewed the report set with five lenses and a bounded loop (§37, §38), and this synthesis cites only evidence that survived all four.
Evidence base: 5 reviewed item(s) from 5 independent origin(s).

## Confidence

Mission confidence: low.
Basis: the weakest of 5 finding(s) sets the level: single-source (1 origin(s)), because the answer cannot be stronger than the claim it depends on
Bands: single-source 5, corroborated 0, well-corroborated 0
Band rules: one independent origin is single-source; two are corroborated; three or more are well-corroborated. An allegation is capped at corroborated — a third party repeating a claim does not establish it — and an inference is capped at corroborated, because reasoning over good evidence is still reasoning.

## Key findings

| finding | kind | confidence | evidence ids | what would refute it |
| --- | --- | --- | --- | --- |
| advisory-reader: each advisory has a version or an explicit unknown | observation | single-source (1) | `ev-c759a5e97a06` | a first-party record contradicting it, or a second independent origin failing to reproduce it |
| gap-gap-567041: the result addresses: the published advisories name the affected component | observation | single-source (1) | `ev-5a152a290231` | a first-party record contradicting it, or a second independent origin failing to reproduce it |
| follow-up-flw-5b6f40: at least one reviewed observation addresses: each documented risk cites a first-party advisory | observation | single-source (1) | `ev-7a78d9ac296e` | a first-party record contradicting it, or a second independent origin failing to reproduce it |
| dns-collector: every record type has a value or an unknown | observation | single-source (1) | `ev-b54e5ec0f860` | a first-party record contradicting it, or a second independent origin failing to reproduce it |
| archive-collector: snapshot list captured with dates | observation | single-source (1) | `ev-631b08366592` | a first-party record contradicting it, or a second independent origin failing to reproduce it |

## Corroborated indicators

No claim in this mission was stated independently by two or more origins, so the report claims no indicator. A corroborated indicator requires two distinct origins, not two sentences.

## Competing hypotheses

| hypothesis | status | competing explanation | test that decides it |
| --- | --- | --- | --- |
| the published advisories name the affected component | supported | the benign explanation: the same observations are consistent with configuration drift or a shared provider, and no evidence here excludes it | a first-party record that directly addresses question 1, dated and independently reproducible: the published advisories name the affected component |

## Contradictions

No two reviewed items make the same claim with opposite polarity. Silence here is a finding: nothing collected conflicts with anything else collected.

## Evidence gaps

The mission closed every gap it opened. That is a claim about the questions it asked, not about the target: questions it did not think to ask are not in this list.

## Limitations

- the deterministic runner does not contact the target

## Recommended next steps

| step | addresses | why it is lawful | value |
| --- | --- | --- | --- |
| re-run the same passive checks after the target publishes its next advisory, so a change in the record is distinguishable from a change in the collection | gap-1 | the same scope and method the mission already used (example.com) | low |

## Agent and task execution

2 Subagent(s), 6 Worker(s), 6 attempt(s), 0 retries, 6 reviewed evidence item(s), 5 finding(s). Statuses: succeeded 8

| unit | kind | role | status | gate | attempts | evidence | seconds | origin |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sa-7adc0f884bde | subagent | published-advisories | succeeded | none | 1 | 3 | 0.06s | planned |
| wrk-7fa8d41b476a | worker | advisory-reader | succeeded | none | 1 | 1 | 0.05s | planned |
| wrk-60aa16261035 | worker | published-advisories gap closure | succeeded | none | 1 | 1 | 0.05s | runtime |
| wrk-03581617fd6c | worker | published-advisories follow-up | succeeded | none | 1 | 1 | 0.05s | follow-up |
| sa-4de82fcd5ca6 | subagent | dns-and-archive | succeeded | none | 1 | 3 | 0.12s | planned |
| wrk-e9cfb6efebac | worker | dns-collector | succeeded | none | 1 | 1 | 0.05s | planned |
| wrk-d9962bee6734 | worker | archive-collector | succeeded | none | 1 | 1 | 0.05s | planned |
| wrk-ac9fe515391b | worker | dns-and-archive gap closure | succeeded | none | 1 | 1 | 0.05s | runtime |

## Time usage

Total wall-clock: 0.31s. First ledger event to last: 0.31s (the ledger opened 0.34s before its first event). 42 ledger event(s), 6 Worker attempt(s), peak 0 resource(s) in flight.

| stage | window |
| --- | --- |
| reconciliation | 0.180s |
| follow-up planning | 0.065s |
| worker execution | 0.052s |
| subagent planning | 0.003s |
| worker review | 0.003s |
| master review | 0.003s |
| planning | 0.002s |
| synthesis | 0.000s |

stage windows are differences between the first appearance of each stage in the ledger, not instrumented unit durations, so overlapping stages share their window rather than summing to the total. The ledger's zero is when the flow was built, 0.344s before its first event; the run's own clock starts when it is invoked, which is why the two totals differ.

## Errors

No error was recorded. That is a statement about the record, not a claim that nothing went wrong: an error the mission did not write down is not here, and the trace is the place to look for it.

## Retry history

No unit was retried, so there is no retry history. A mission that never retried is not necessarily a mission that got everything right first time: it may be one whose reviews passed.

## Stopping reason

the mission finished: the run completed and recorded no stopping bound, so this dossier reports the absence rather than inventing one. No stopping decision was part of this file, so the reason above is the whole of what the record says.

- stopped before finishing: no
- condition: `none` (not stated)
- master reviews: 0; rounds tracked: 0

## Source register

1 origin(s), 0 with a reproducible digest. A row without a digest is usable and not reproducible, and the register says so rather than implying otherwise.

| id | title | locator | kind | method | retrieved | digest | items | cited |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `src-60fcfec4bda8` | advisory-reader — published-advisories | example.com | local-artifact | local-read | 2026-11-11T11:20:19+00:00 | not hashed | 5 | 5 |

## Evidence table

6 item(s), every one of them cited by a finding.

| evidence id | kind/confidence | statement | cited by | source | collected by | digest |
| --- | --- | --- | --- | --- | --- | --- |
| `ev-5a152a290231` | observation/low | gap-gap-567041: the result addresses: the published advisories name the affected component | `kf-a93c5576e8` | `example.com` | wrk-60aa16261035 | — |
| `ev-5a152a290231` | observation/low | gap-gap-567041: the result addresses: the published advisories name the affected component | `kf-a93c5576e8` | `example.com` | wrk-ac9fe515391b | — |
| `ev-631b08366592` | observation/low | archive-collector: snapshot list captured with dates | `kf-09229ef0bc` | `example.com` | wrk-d9962bee6734 | — |
| `ev-7a78d9ac296e` | observation/low | follow-up-flw-5b6f40: at least one reviewed observation addresses: each documented risk cites a first-party advisory | `kf-eb1453ad68` | `example.com` | wrk-03581617fd6c | — |
| `ev-b54e5ec0f860` | observation/low | dns-collector: every record type has a value or an unknown | `kf-68bbcb19cc` | `example.com` | wrk-e9cfb6efebac | — |
| `ev-c759a5e97a06` | observation/low | advisory-reader: each advisory has a version or an explicit unknown | `kf-f73fb812d3` | `example.com` | wrk-7fa8d41b476a | — |

## Chain of custody

1 record(s); 0 with a digest, 0 recorded as preserved. A digest alone establishes integrity, not custody: who handled the artefact and whether it was preserved are separate claims, and both are in the table.

| evidence | artefact | digest | coverage | handled by | when | method | preserved | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `ev-c759a5e97a06` | example.com | **not hashed** | — | wrk-7fa8d41b476a | 2026-11-11T11:20:19+00:00 | local-read | **no** | not-assessed |

- `ev-c759a5e97a06`: no digest recorded — no custody record was made for this artefact: the digest alone does not establish who handled it or whether it was preserved

## Audit and reproducibility

This mission ran on argus 0.32.0 on Python 3.11.2 (CPython, x86\_64); schema argus-audit/1. It was invoked as `report --mission /tmp/argus-t32-cli-3ukrnn50/flow-exposure.json`. 

## Environment

| field | value |
| --- | --- |
| application | argus |
| version | 0.32.0 |
| version label | 0.32.0-alpha |
| build phase | 3 |
| record format | argus-audit/1 |
| python | 3.11.2 (CPython) |
| platform | Linux-6.1.158+-x86_64-with-glibc2.36 |
| machine | x86_64 |
| user agent | ARGUS/0.32.0 (+authorised-security-research) |
| dry run | yes |

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
| network.user_agent | ARGUS/0.32.0 (+authorised-security-research) | default |
| paths.output_dir | argus_home/output | settings |
| paths.case_dir | not set | settings |
Redacted by name, with the *state* of each kept: `model.api_key` (<redacted: unset, value not recorded>).

## Models

- **master-and-workers**: `unset` via openai — credential absent (looked in ARGUS\_LLM\_API\_KEY \| OPENAI\_API\_KEY); looked for in `ARGUS_LLM_API_KEY`, `OPENAI_API_KEY`.

The credential itself is never recorded: a reader who needs one supplies their own.


## Mission scope and limits

- objective: map the publicly documented exposure of example.com and rank the advisory-backed risks
- mode: `passive`
- authorised scope: `example.com`
- tools available: `http.fetch`, `dns.lookup`, `archive.search`, `advisory.read`
- limits: max_subagents=4, max_total_workers=8, mission_budget_seconds=3600
- the mission would be finished when: each documented risk cites a first-party advisory
- questions it set itself: the published advisories name the affected component


## Timestamps

- recorded: 2026-11-11T11:20:21+00:00
- mission started: 2026-11-11T11:20:19+00:00
- mission ended: 2026-11-11T11:20:19+00:00
- duration: 0.31s
- per stage: planning 0.00s, subagent planning 0.00s, worker execution 0.05s, worker review 0.00s, reconciliation 0.18s, master review 0.00s, follow-up planning 0.07s, synthesis 0.00s.


## Dynamic hierarchy

8 unit(s) in 2 level(s): 2 subagent, 6 worker; 3 invented after the plan. Planned 5, invented after the plan 3.

| unit | kind | role | parent | status | origin | attempts | evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sa-7adc0f884bde | subagent | published-advisories | master | succeeded | planned | 1 | 3 |
| wrk-7fa8d41b476a | worker | advisory-reader | sa-7adc0f884bde | succeeded | planned | 1 | 1 |
| wrk-60aa16261035 | worker | published-advisories gap closure | sa-7adc0f884bde | succeeded | runtime | 1 | 1 |
| wrk-03581617fd6c | worker | published-advisories follow-up | sa-7adc0f884bde | succeeded | follow-up | 1 | 1 |
| sa-4de82fcd5ca6 | subagent | dns-and-archive | master | succeeded | planned | 1 | 3 |
| wrk-e9cfb6efebac | worker | dns-collector | sa-4de82fcd5ca6 | succeeded | planned | 1 | 1 |
| wrk-d9962bee6734 | worker | archive-collector | sa-4de82fcd5ca6 | succeeded | planned | 1 | 1 |
| wrk-ac9fe515391b | worker | dns-and-archive gap closure | sa-4de82fcd5ca6 | succeeded | runtime | 1 | 1 |

A `runtime` or `follow-up` origin is a unit the mission did not plan: it was created because the work demanded it, and the report's aggregation counts it like any other.


## Tool failures

No tool failure was recorded by this mission. That is a fact about this run, not a claim that every tool call succeeded silently.


## Stopping reason (audit)

- kind: **not stated** (condition `none`); the mission finished
- reason: the run completed and recorded no stopping bound, so this dossier reports the absence rather than inventing one

## Reproduction

1. `python -m pip install -r requirements.txt` — install the same dependency set (typer, rich, pydantic, langgraph, …)
2. `python vedant\_osint.py policy -t example.com -o "map the publicly documented exposure of example.com and rank the advisory-backed risks"` — confirm the objective and scope are admissible before collecting
3. `export ARGUS\_LLM\_MODEL=\<model\> && python vedant\_osint.py flow -t example.com -o "map the publicly documented exposure of example.com and rank the advisory-backed risks" --out-dir out/` — run the same mission with your own credential and the model named in the Models section; the limits were max\_subagents=4, max\_total\_workers=8, mission\_budget\_seconds=3600 *(needs a credential you supply)*
4. `python vedant\_osint.py report --mission out/flow-\*.json --out-dir out/` — write the same three formats from the new run

Following these steps reproduces the *procedure*, not the answer. A re-run collects whatever the world says now, and the two results differ wherever the world changed between them.


## What is deliberately not recorded

- scan: clean: 57,926 byte(s) scanned for 12 credential pattern(s)
- not recorded — api keys and provider tokens: a credential is authority, not procedure: a record that carried one would let a reader act as the operator instead of reproducing their setup.
- not recorded — cookies and browser session state: a cookie is the operator's authenticated identity on somebody else's service.
- not recorded — browser profile contents and credentials: the profile directory is named so the setup can be repeated; none of its contents are copied.
- not recorded — page content beyond cited findings: the evidence table carries what a finding rests on, quoted and hashed; copying the pages themselves would spread third-party material the report does not need, 8 present.
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

This document was assembled from the reviewed record. Every finding cites the evidence that carries it, confidence is derived from independent origins and capped by the claim's epistemic kind, and the JSON form (`flow-a995e56deaae.json) is the authoritative record this Markdown is a view of.
