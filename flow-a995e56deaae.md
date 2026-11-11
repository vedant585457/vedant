# Mission report — map the publicly documented exposure of example.com and rank the advisory-backed risks

- mission: `flow-a995e56deaae`
- generated: 2026-11-11T10:32:58+00:00
- format: `argus-dossier/1` (schema version 1)
- confidence: **low** — the weakest of 5 finding(s) sets the level: single-source (1 origin(s)), because the answer cannot be stronger than the claim it depends on
- evidence: 5 citation(s) from 5 independent origin(s); 6 item(s) in the table
- status: finished — the mission finished: the mission ran every unit it planned and the master closed it without recording a bound, which the trace supports and this line states. The bound that ended it is on the record, so a reader can tell a finished mission from a stopped one.

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
| wrk-7fa8d41b476a | worker | wrk-7fa8d41b476a (pass) | succeeded | none | 1 | 1 | 0.05s | planned |
| wrk-60aa16261035 | worker | wrk-60aa16261035 (pass) | succeeded | none | 1 | 1 | 0.05s | planned |
| wrk-03581617fd6c | worker | wrk-03581617fd6c (pass) | succeeded | none | 1 | 1 | 0.05s | planned |
| sa-4de82fcd5ca6 | subagent | dns-and-archive | succeeded | none | 1 | 3 | 0.11s | planned |
| wrk-e9cfb6efebac | worker | wrk-e9cfb6efebac (pass) | succeeded | none | 1 | 1 | 0.05s | planned |
| wrk-d9962bee6734 | worker | wrk-d9962bee6734 (pass) | succeeded | none | 1 | 1 | 0.05s | planned |
| wrk-ac9fe515391b | worker | wrk-ac9fe515391b (pass) | succeeded | none | 1 | 1 | 0.05s | planned |

## Time usage

Total wall-clock: 0.30s. First ledger event to last: 0.30s (the ledger opened 0.35s before its first event). 42 ledger event(s), 6 Worker attempt(s), peak 0 resource(s) in flight.

| stage | window |
| --- | --- |
| reconciliation | 0.174s |
| follow-up planning | 0.066s |
| worker execution | 0.052s |
| planning | 0.003s |
| subagent planning | 0.002s |
| worker review | 0.002s |
| master review | 0.002s |
| synthesis | 0.000s |

stage windows are differences between the first appearance of each stage in the ledger, not instrumented unit durations, so overlapping stages share their window rather than summing to the total. The ledger's zero is when the flow was built, 0.355s before its first event; the run's own clock starts when it is invoked, which is why the two totals differ.

## Errors

No error was recorded. That is a statement about the record, not a claim that nothing went wrong: an error the mission did not write down is not here, and the trace is the place to look for it.

## Retry history

No unit was retried, so there is no retry history. A mission that never retried is not necessarily a mission that got everything right first time: it may be one whose reviews passed.

## Stopping reason

the mission finished: the mission ran every unit it planned and the master closed it without recording a bound, which the trace supports and this line states. The bound that ended it is on the record, so a reader can tell a finished mission from a stopped one.

- stopped before finishing: no
- condition: `none` (not stated)
- master reviews: 0; rounds tracked: 0

## Source register

1 origin(s), 0 with a reproducible digest. A row without a digest is usable and not reproducible, and the register says so rather than implying otherwise.

| id | title | locator | kind | method | retrieved | digest | items | cited |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `src-3eb5bada85fd` | advisory-reader — published-advisories | example.com | local-artifact | local-read | 2026-11-11T10:28:33+00:00 | not hashed | 5 | 5 |

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
| `ev-c759a5e97a06` | example.com | **not hashed** | — | wrk-7fa8d41b476a | 2026-11-11T10:28:33+00:00 | local-read | **no** | not-assessed |

- `ev-c759a5e97a06`: no digest recorded — no custody record was made for this artefact: the digest alone does not establish who handled it or whether it was preserved

## Acceptance

- Markdown complete: yes
- JSON re-validates against the dossier model: yes
- terminal summary concise: yes
- hashes and custody preserved: yes
- §39 report clause on this document: every finding cited yes, no conclusion above its evidence yes

No finding in this document declares guilt or attributes identity with certainty; an identification appears only as a hypothesis with a test.


---

This document was assembled from the reviewed record. Every finding cites the evidence that carries it, confidence is derived from independent origins and capped by the claim's epistemic kind, and the JSON form (`flow-a995e56deaae.json) is the authoritative record this Markdown is a view of.
