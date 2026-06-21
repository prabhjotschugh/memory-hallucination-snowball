# MemorySnowball: Cross-Session Hallucination Contamination in Memory-Augmented Agent Pipelines

**Project context document**

**Collaborators:** Prabhjot Singh (UT Austin) · Jianing Zhu (VITA Group, UT Austin)

**Predecessor work:** Singh & Pawar, *"The Hallucination Snowball: Modeling Error Propagation as State Transitions in Multi-Agent LLM Pipelines,"* FAGEN Workshop, ICML 2026.

**Target:** A* main-conference submission (not workshop). This document exists so that code can be written against a single, stable spec instead of re-deriving decisions from the email/doc history each time.

---

## 1. Where this project came from

### 1.1 The predecessor: Hallucination Snowball (single-run, single-session)

The first paper (FAGEN @ ICML 2026) established that hallucinations injected at the start of a **single** 4-agent pipeline (Researcher → Analyst → Writer → Reviewer, single session, no memory) transform through four states - Raw Fact → Derived → Narrative → Invisible - with sharply increasing escape probabilities at each boundary (24.6% → 48.3% → 89.3%). Headline results worth keeping in mind as the bar to clear:

- 346 injected hallucinations across 140 FinanceBench questions, gpt-4o-mini 4-agent LangGraph pipeline.
- Detection (gpt-4o Judge) decayed from 72.0% (S1) to 50.9% (S4); 23.7% of hallucinations survived completely undetected.
- A **deterministic, zero-LLM-call numeric matcher** against FinanceBench ground truth served as the rigorous detection instrument; an LLM judge served as the "realistic deployment" instrument. The two were always reported **separately**, never blended into one number.
- Boundary gates (verify at every handoff) crushed survival from 60.7% (Vanilla) to 16.2% (Ours), a result validated by **five independent statistical tests**: McNemar's χ², a 10,000-permutation test, Cohen's h, an unpaired χ², and Fisher's exact test - all p < 0.000001.
- The whole thing was formalized as a first-order Markov chain with a closed-form survival formula, P(survival) = ∏ sₖ, validated against measured data (predicted 10.6% vs. measured 16.2%, gap attributed to gate false negatives from value reformatting).
- Limitations section explicitly named the open extension: *"In memory-augmented pipelines, [the model] prescribes verification before any memory write, since a hallucination written to persistent memory propagates to every future agent that reads it."* This sentence is effectively the seed of the current project.

**Why this matters for V2's design bar:** the reviewers evaluating the successor will very likely be familiar with - or will go look up - the predecessor. The successor cannot just be "the same idea, but across sessions, with a demonstration that it gets worse." It needs the same evidentiary spine: a formal model with measured transition probabilities, a predictive closed-form result validated against data, a multi-test statistical validation of the core intervention, and an honest limitations/cost discussion. Anything less reads as a workshop-tier extension, not an A* paper.

### 1.2 Why "it snowballs across sessions too" is not a sufficient thesis

Literature review identified that the naive extension - "errors compound across memory-augmented sessions" - is now a **crowded and partially contradicted** lane:

- **HaluMem** (Nov 2025) already bills itself as the first operation-level benchmark for hallucination in agent memory, explicitly tracking how errors "arise, propagate, and impact outputs."
- An active **memory-poisoning** literature (attack + defense) already covers adversarial contamination of agent memory.
- **"Hallucination Cascade"** (June 2026) found cascades can *attenuate* rather than amplify - directly complicating a naive "it always gets worse" claim.

If the paper's contribution is just "contamination spreads across sessions," it is simultaneously incremental against HaluMem and contradicted by Hallucination Cascade. That is not fundable A*-paper territory.

### 1.3 The locked thesis

The paper's actual contribution is **not** "does it amplify or does it attenuate" as a binary finding. It is a **predictive model of which regime occurs and when**, with the **point-of-no-return (PNR) session horizon** as its central, actionable output.

> **Thesis statement (lock this - this is what every experiment should be in service of):**
> Cross-session memory contamination is not monotonic amplification. It is governed by a measurable competition between **error reproduction** (corroborating writes that reinforce a planted error) and **error correction** (verification or contradicting evidence that weakens it). We formalize this competition as a stochastic process over sessions, measure its parameters empirically, and show it predicts - per condition (memory architecture, task domain, error type) - both (a) whether contamination amplifies or self-corrects, resolving the apparent contradiction between concurrent papers, and (b) if it amplifies, the **point-of-no-return**: the session index beyond which the corroborating evidence cluster is large enough that no realistic correction mechanism can still recover the original error.

This reframes the project from a single demonstration into a **predictive, falsifiable model** - directly analogous to how Snowball's Markov chain wasn't just "detection drops," but a model that *predicted* survival rates for arbitrary pipeline lengths and was checked against held-out data. PNR is to this paper what the S1→S2→S3→S4 escape-probability chain was to Snowball: the one number/curve that becomes the paper's signature result.

### 1.4 Positioning against related work (for the related-work section, keep updated as we read more)

| Prior work | What it covers | Gap we exploit |
|---|---|---|
| Hallucination Snowball (us, predecessor) | Single-session, single-run transformation across agent handoffs | No memory, no cross-session dynamics at all |
| HaluMem (Nov 2025, arXiv:2511.03506) | Operation-level benchmark for hallucination arising/propagating/impacting outputs in agent memory | Benchmark/taxonomy paper; does not model *correctability* or predict a point of no return |
| Hallucination Cascade (Jun 2026, arXiv:2606.07937) | Empirically finds cascades can attenuate, not just amplify | No model of *when* each regime occurs - we directly resolve this as a predictable function, not a contradiction |
| Memory-poisoning literature (attack + defense) | Adversarial injection into agent memory | Assumes adversarial intent; our failure mode (like Snowball's) requires no adversary - well-intentioned agents produce it structurally |
| Communication-topology papers (e.g., arXiv:2603.19677v1) | Shows topology (sparse/dense) shapes error propagation *within a single session*, multi-agent, stateless | Nobody has asked whether memory *architecture* (not communication topology) shapes whether contamination is recoverable *across* sessions - this is our Tier-2 contribution (§4) |
| RRR / confabulated reflections persistence work | Cross-trial persistence of confabulated reflections | Persistence ≠ a model of correctability decay or PNR |
| State/Compression-induced detectability loss (SPG-type work) | Single-step detectability loss under memory compression | Single-step, not a multi-session reproduction/correction competition model |

This table should be revisited and expanded as more papers from the shared list (§7.3) get properly read and slotted in - right now several are still only "shared, not yet integrated."

---

## 2. System architecture

### 2.1 The 5-agent handoff loop

Per-session pipeline, run once per "quarter" (one FinanceBench-derived earnings report = one session):

```
Researcher → Analyst → Writer → Reviewer → Memory-Curator
                                                  │
                                                  ▼
                                          [writes to persistent
                                           memory store, gated]
                                                  │
                          (next session reads from memory store)
                                                  ▼
                                             Researcher (session N+1)
```

| Agent | Role | Inherits from predecessor work |
|---|---|---|
| **Researcher** | Extracts exact figures from the current session's SEC filing / FinanceBench source doc. Also retrieves and reads relevant prior-session memory entries before extraction, so upstream contamination can bias *what it considers plausible or already-established*. | Same role as Snowball S1 |
| **Analyst** | Computes derived figures (YoY change, ratios, trend deltas) - now using **both** current-session Researcher output **and** retrieved historical memory (e.g., "last quarter's COGS was $X, so YoY = …"). This is the primary mechanism by which a contaminated historical entry corrupts a *new, otherwise-correct* session. | Same role as Snowball S2, extended to read memory |
| **Writer** | Produces the narrative report for this session, in the same style as Snowball S3, but may now reference prior-session narrative trends pulled from memory ("continuing the cost pressure seen in Q1…"). | Same role as Snowball S3 |
| **Reviewer** | Internal consistency check only, no source-document access - identical role/limits to Snowball S4. Approves or flags before handoff to the Curator. | Same role as Snowball S4 |
| **Memory-Curator** *(new)* | Decides what from this session's output gets written to persistent memory, in what form (raw fact / derived / narrative - tagging which transformation state it's in, reusing Snowball's state vocabulary), and runs the **write-time contamination gate** (§2.3) before commit. This agent is the mechanism for the "verify before any memory write" prescription from Snowball's own limitations section. | New - this is the paper's core architectural addition |

**Design rationale:** keeping Researcher→Analyst→Writer→Reviewer structurally identical to Snowball is deliberate. It lets us cleanly attribute any *new* failure mode to the memory layer (Curator + cross-session retrieval) rather than confounding it with a redesigned within-session pipeline. The only within-session change is that Researcher and Analyst now have read access to memory - that read access is precisely the channel through which cross-session contamination travels, and it should be the *only* structural difference from Snowball's pipeline.

### 2.2 Memory store: core schema

Flat key-value episodic memory, session-tagged writes (per the Google Doc decision), no compression in the base condition. Each entry:

```python
{
  "entry_id": str,              # unique id
  "session_id": int,            # which session (quarter) wrote this
  "agent_source": str,          # which of the 5 agents produced the content
  "content": str,                # the actual text/value
  "state_tag": str,              # one of: RAW_FACT | DERIVED | NARRATIVE
                                  # (reuses Snowball's S1-S3 vocabulary; S4/INVISIBLE
                                  # is not a memory state, it's an outcome we measure)
  "parent_ids": list[str],       # lineage - which prior entries this was derived from
  "ground_truth_checkable": bool,# does this entry contain a value traceable to
                                  # FinanceBench ground truth?
  "is_contaminated": bool,       # SET ONLY by the contamination-check pipeline (§2.4),
                                  # NEVER inherited automatically from parent_ids.
                                  # see §2.4 for the fix.
  "verification_status": str,    # one of: VERIFIED | UNVERIFIED | FLAGGED_CONTAMINATED
                                  # set by the write-time gate (§2.3); drives retrieval
                                  # ranking in the provenance-gated condition (§2.5)
  "injection_metadata": dict | None,  # if this entry traces back to an injected
                                       # hallucination: injection session, original
                                       # vs. perturbed value, perturbation type
}
```

**Critical fix vs. V1:** `is_contaminated` is a *measured outcome*, computed by the contamination-check pipeline (§2.4) by checking content correctness, not a flag that propagates automatically because a parent is contaminated. `parent_ids` remains purely for **lineage** - i.e., for *explaining* how an error spread once we've independently determined it's wrong, and for computing cluster-growth metrics. Conflating "derived from a contaminated parent" with "is itself wrong" was V1's bug; keeping these two concepts on two separate fields is the fix.

### 2.3 Write-time contamination gate (the architectural contribution)

Every entry the Memory-Curator wants to commit passes through this gate **before** it lands in the store. This is the cross-session analogue of Snowball's boundary gates (which operated at agent handoffs within a session; this one operates at memory writes between sessions) - and it is the mechanism that makes the **provenance-gated** memory condition (§2.5) a real, non-strawman architecture rather than naive isolation.

1. Run the contamination check (§2.4 - deterministic-first, judge-fallback) on the entry being written.
2. If the check finds the entry's checkable content matches ground truth (or, for non-checkable narrative entries, finds no contradiction with verified prior memory): `verification_status = VERIFIED`.
3. If the check finds the entry is wrong: `verification_status = FLAGGED_CONTAMINATED`. The entry is **still written** (we are not preventing contamination outright - that would make the "does contamination spread" question moot by construction) but is marked.
4. If the entry contains no checkable content and the judge fallback is inconclusive: `verification_status = UNVERIFIED`.

This status is written once, at commit time, and is what downstream retrieval (§2.5) acts on - it is computed independently of `is_contaminated`'s ground-truth label so that we can later measure gate precision/recall against the ground-truth label, exactly the way Snowball measured its boundary gate's false-positive rate (0.4%) and suppression-without-restoration rate (32.7%) against ground truth. **We want this same kind of honest gate-error analysis in the successor paper** - don't build the gate as a black box we trust blindly; build it so we can audit it.

### 2.4 Contamination ground-truth check (the measurement instrument)

This is the instrument used both (a) to label `is_contaminated` for measurement/analysis purposes, and (b) inside the write-time gate (§2.3). Two-tier, asymmetric, reported separately - directly modeled on Snowball's decision to never blend "gpt-4o Judge" and "Retrieval Checker" into one number.

**Tier A - Deterministic numeric check (primary instrument, zero LLM calls).**
Applies to any memory entry where `ground_truth_checkable = True`, i.e., it contains a value traceable to a FinanceBench ground-truth figure (directly, or one arithmetic transformation away - e.g., a YoY% computed from two prior raw facts). Reuse Snowball's matching approach: compare against FinanceBench ground truth, evidence strings, and the pre-injection upstream value, at a defined tolerance (start from Snowball's 1–2% tolerance bands, recalibrate if multi-session arithmetic chains introduce compounding rounding). This is the number that should anchor the paper's headline contamination/decay curves, exactly as the Retrieval Checker anchored Snowball's.

**Tier B - LLM-judge semantic check (secondary instrument, reported separately).**
Applies only to entries with `ground_truth_checkable = False` - pure narrative/projection/trend claims with no underlying checkable number (e.g., "cost pressure is likely to continue into next quarter"). A judge model checks the claim for consistency against verified prior memory and the actual ground-truth trend direction. **Never pooled into the same headline rate as Tier A.** Report as a separate curve/table, the same way Snowball kept gpt-4o Judge and Retrieval Checker as visually and statistically distinct rows (Table 1, Figure 2).

This split is also a natural extra contribution: it gives a second decay curve - "deterministic-detectable contamination" vs. "judge-only-detectable contamination" - almost for free, and lets us ask whether narrative-only contamination (no longer attached to any checkable number) is the specific subpopulation responsible for the point of no return, which would be a genuinely interesting structural finding parallel to Snowball's S3→S4 "narrative embedding is near-irreversible" result.

### 2.5 Memory architecture as the contrastive variable

Per the decision to bring this into scope now rather than defer it: two conditions, run head-to-head, same pipeline, same tasks, same injections - only retrieval/write policy differs. This directly operationalizes the flagged gap (topology shapes propagation *within* a session is known; whether memory *architecture* shapes recoverability *across* sessions is not).

**Condition 1 - Shared Blackboard (baseline, "V1's architecture").**
All agents read the full pool of prior-session memory entries relevant to the current query, regardless of `verification_status`. This is the naive, V1-equivalent setup and represents how most memory-augmented agent frameworks work today (no provenance-aware retrieval). This condition is expected to show the fastest contamination reproduction and the earliest point of no return.

**Condition 2 - Provenance-Gated ("Ours").**
Retrieval is **ranked and filtered by `verification_status`**, not by full isolation. Concretely:
- `VERIFIED` entries are retrieved normally, ranked first.
- `UNVERIFIED` entries are retrieved but ranked behind verified entries and are **structurally tagged in-context** when passed to an agent (e.g., presented with an explicit "unverified" marker), so a downstream agent has the option, but not the obligation, to discount them.
- `FLAGGED_CONTAMINATED` entries are **excluded from retrieval by default** (not hard-deleted from the store - they remain for lineage/audit purposes) but are not used to seed new derived/narrative content.

This is deliberately **not** full isolation (each session only sees its own writes) - that design would trivially prevent cross-session contamination by construction and a reviewer would correctly call it an unrealistic strawman that breaks the actual value of having memory at all. It is also deliberately **not** pure soft-tagging with no filtering - that risks too weak a manipulation to produce a measurably different PNR, which would leave the paper's one architectural ablation as a null result. Gate-then-rank-and-filter is the version that (a) is a real systems contribution practitioners could adopt, (b) directly reuses the write-time gate from §2.3 rather than requiring a second mechanism, and (c) is concretely expected to shift the PNR horizon later, giving us a clean, testable, non-trivial hypothesis: **"provenance-gated memory pushes the point of no return to a significantly later session than shared blackboard, measured via the same 5-test statistical battery Snowball used for its boundary-gate result."**

---

## 3. Core metrics

Two primary curves, plus the new outcome-level metric and the PNR derivation.

### 3.1 Detectability decay (per session)

After each session, run the contamination check (§2.4) on all memory entries known to trace back to an injected error (via `injection_metadata`/lineage), and plot the fraction still correctly flagged as contaminated, as a function of session index. This is the direct cross-session analogue of Snowball's Figure 2 (per-stage decay) - same idea, but the x-axis is sessions instead of pipeline stages, and the y-axis should report Tier A and Tier B (§2.4) as separate lines, not blended.

### 3.2 Cluster growth rate

Per contaminated entry, count how many new memory entries it spawns (i.e., appear as a `parent_id`) per session. Superlinear growth in this count is the direct evidence of self-amplification (corroboration begetting more corroboration) - this is the quantity that distinguishes "amplify" from "attenuate" per-condition, which is what resolves the Hallucination Cascade contradiction rather than just asserting one side of it.

### 3.3 Outcome-level accuracy (new)

V1 had no end-task scoring. Score the actual investment-call / projection output at the end of each session against ground truth (independent of internal `is_contaminated` labels - this is the "does it matter to the thing a human would actually read" check). Plot accuracy degradation over sessions. This metric is what lets the paper make a real-world-stakes claim analogous to Snowball's "23.7% of hallucinations survive completely undetected in the final output" - i.e., not just an internal-metrics story, but a demonstrated effect on the thing the pipeline is supposed to produce.

### 3.4 Point of no return (PNR) - the paper's signature output

Defined as the session horizon *n** beyond which a defined correction intervention (e.g., injecting the true ground-truth value at session *n* and observing whether downstream entries still revert toward the error) fails to reduce contamination back below a threshold, because the corroborating cluster (§3.2) already outweighs the correction. Concretely:

1. At a chosen session *n*, inject a "correction" (ground-truth value made available with maximal salience/verification status) for a known contaminated entry.
2. Measure whether, over the following sessions, the corroborating cluster's measured contamination rate (§3.1) returns below a defined threshold (e.g., back to the Tier-A false-positive floor) or whether it persists/re-corrupts.
3. PNR = the smallest *n* (as a function of condition: memory architecture, error type, task domain) at which correction reliably fails. This should be fit as a function of measurable covariates - write-back rate, corroboration count, dependency density, compression - not just reported as a single scalar, mirroring how Snowball didn't just report "89.3% escape probability" but built it into a predictive closed-form model (P(survival) = ∏ sₖ) that generalized to arbitrary pipeline lengths. **The equivalent closed-form target here is a PNR-prediction formula as a function of those covariates, validated against held-out sessions/conditions** - this is the centerpiece deliverable.

---

## 4. Experimental plan

### 4.1 Tiered scenario design (per Google Doc, retained)

**Tier 1 - Primary: FinanceBench, multi-session extension.**
A financial analysis pipeline (§2.1) processes quarterly earnings reports one per session, writing findings to memory and reading prior memory before each new quarter. One hallucination is injected at session 1 (reuse Snowball's injection protocol - deterministic regex perturbation, fixed seed, dollar/percentage/large-number classes - see Appendix B of the Snowball paper for the exact regex and seeding scheme to port over) and is tracked as it compounds across sessions while the agent builds trend analysis and projections on a false baseline. Ground truth is clean, stakes are legible. This is the tier the core PNR model is fit and validated on.

**Tier 2 - Secondary: MemoryArena, cross-domain generalizability.**
If the contamination-cluster phenomenon and the PNR model hold on MemoryArena's sequential reasoning / web navigation tasks, that substantially strengthens external validity - directly addresses the kind of "is this just a finance-numbers artifact" critique Snowball itself flagged as a limitation in its own domain (Snowball §5, Limitations, point 1).

**Tier 3 - Synthetic: controlled injection dataset.**
A constructed dataset with fully known contamination lineage: exact injection session, n-th-generation descendants, controllable severity, session counts from 1–10. This is the only tier precise enough to cleanly measure detectability decay and cluster growth rate without confounds - Tier 1/2 results serve as real-world validation of what Tier 3 establishes under control. This mirrors how Snowball used a controlled injection protocol (fixed seeds, full metadata logging) as the backbone of its measurement even though FinanceBench itself is "real-world."

### 4.2 The core intervention experiment (analogue of Snowball's Experiment 3)

Snowball's strongest, most reviewer-convincing result was not the existence of decay - it was the **timing-dominates-method** result (Vanilla vs. End-Check vs. Ours boundary gates), validated by 5 independent statistical tests. The successor needs a structurally equivalent centerpiece experiment. Proposed design, directly parallel:

| Condition | Memory write policy | Memory read policy |
|---|---|---|
| **Vanilla** | No contamination gate at write time | Shared blackboard, unfiltered |
| **End-of-Horizon Check** | No gate during the run; contamination check + correction only applied once, after session N | Shared blackboard, unfiltered, until the one-time end check |
| **Ours (Provenance-Gated)** | Write-time gate every session (§2.3) | Provenance-gated retrieval (§2.5, Condition 2) |

Primary outcome variable: **PNR session index** (does correction succeed or fail, and at what session does it stop succeeding) - this replaces Snowball's "survival rate" as the headline number, but the statistical battery should be reused as-is: McNemar's χ² (paired, correction-succeeds-or-not across matched injected errors), a permutation test, Cohen's h for effect size, an unpaired χ², and Fisher's exact test. Report all five, exactly as Snowball did, since that multi-test convergence is part of what made Snowball's Experiment 3 result hard to dismiss.

Secondary outcomes to carry over directly: actionable detection rate, contamination-free final-session-output rate, correction rate, and an output-quality score - with the same honest framing Snowball used (its quality metric was *structurally blind* to the intervention's main benefit, and the paper said so explicitly rather than hiding it). Expect and plan to report an analogous tradeoff here (provenance-gating likely costs some narrative fluency/continuity across sessions) rather than assuming the new architecture is a free lunch.

### 4.3 Statistical rigor bar (non-negotiable, carried over from Snowball)

- Fixed random seeds, fully logged injection metadata, exact-replication capability - same as Snowball Appendix B.
- Bootstrap confidence intervals (Snowball used 5,000 resamples) on any single-condition detection/correction rate.
- Any headline comparison between two conditions needs the multi-test treatment from §4.2, not a single p-value.
- Report gate error analysis honestly: false-positive rate of the contamination gate against ground truth, and a "suppression-without-restoration"-style breakdown if corrections are flagged but not actually propagated - Snowball's most credible moment was admitting its quality metric couldn't see its own intervention's benefit; do the equivalent here rather than overclaiming.

---

## 5. Build history and decisions log (V1 → V2)

### 5.1 V1 (built, then rolled back)

What was built in V1 and pushed to `memory-hallucination-snowball`:
- 5-agent handoff loop (structure as in §2.1, though roles were not yet finalized at that point - this doc finalizes them).
- Session-tagged memory store with `parent_ids` lineage tracking.
- Automated contamination inference across generations (generation-0 through generation-N).
- Tier 1 structure on FinanceBench, including a detailed worked example (3M Company test case) in `project_working.md`.
- Agent backend: **Gemini models** as the agents' underlying LLM (kept for V2 unless changed - see §7.1).
- Baseline metrics: detectability decay, cluster growth (the two metrics from the original Google Doc plan).
- Tier 2/3 benchmarks: marked WIP, not built.
- Pre-prevention/propagation-stopping module: not yet built.

### 5.2 The bug caught - and why it mattered

In V1's `memory.py`, an entry was marked `is_contaminated` if **any** of its `parent_ids` was contaminated, and derived agents passed most of prior memory as parents. Consequence: once session 1 was corrupted, *all* later writes - including correct new facts - inherited the contamination flag. This meant:
- "Cluster growth" was measuring **cumulative entry count**, not actual error reproduction.
- "Detection decay" was partly an artifact of correct-but-mislabeled entries, not real undetectability.

This is the exact same category of mistake Snowball's own Tier-A/Tier-B separation and lineage-vs-correctness distinction (§2.2, §2.4) is designed to structurally prevent in V2: **lineage explains how something spread; it must never be used as a proxy for whether it's wrong.** This is now a first-class architectural rule for V2, not just a bugfix - see the schema in §2.2, where `parent_ids` and `is_contaminated` are deliberately kept as two independent fields, with `is_contaminated` only ever set by the contamination-check pipeline (§2.4), never inherited.

### 5.3 V2 plan (current, in progress)

- Roll back the V1 commit; rewrite core logic so lineage tracking (`parent_ids`) and contamination labeling (`is_contaminated`, set via §2.4) are structurally separated from the start, not bolted on after.
- Finalize the 5 agent roles per §2.1 (Researcher, Analyst, Writer, Reviewer, Memory-Curator).
- Build the write-time contamination gate (§2.3) as a first-class component, not a later add-on - this is what makes the provenance-gated condition (§2.5) real rather than a strawman.
- Build both memory architecture conditions (Shared Blackboard, Provenance-Gated) from the start, per the decision to bring this into scope now.
- Add the outcome-level accuracy metric (§3.3), which V1 lacked.

---

## 6. Component checklist for the rewrite (practical, for direct reference while coding)

This is the same information as §2–§5, restated as a build checklist so it's easy to track against while writing code.

- [ ] **Memory store module** - schema per §2.2. `parent_ids` and `is_contaminated` structurally separate. `verification_status` field present and only ever set by the write-time gate.
- [ ] **Contamination check module (§2.4)**
  - [ ] Tier A: deterministic numeric/value matcher against FinanceBench ground truth, evidence strings, pre-injection upstream values. Port tolerance logic from Snowball, recalibrate for multi-session arithmetic chains.
  - [ ] Tier B: LLM-judge semantic check, used only when `ground_truth_checkable = False`. Reported as a separate curve, never pooled with Tier A.
- [ ] **Write-time contamination gate (§2.3)** - runs the contamination check before every Memory-Curator commit; sets `verification_status`; does **not** block writes, only flags them.
- [ ] **5-agent pipeline (§2.1)** - Researcher, Analyst, Writer, Reviewer unchanged in role from Snowball except for memory read access on Researcher/Analyst; Memory-Curator new, owns the write-time gate call.
- [ ] **Two memory architecture conditions (§2.5)** - Shared Blackboard (unfiltered retrieval) and Provenance-Gated (ranked + filtered by `verification_status`, contaminated entries excluded from retrieval by default but retained for lineage/audit).
- [ ] **Injection protocol** - port Snowball's Appendix B regex/seeding scheme; extend metadata to track injection session and generation depth across sessions.
- [ ] **Metrics**
  - [ ] Detectability decay per session, Tier A and Tier B reported separately (§3.1).
  - [ ] Cluster growth rate per contaminated entry per session (§3.2).
  - [ ] Outcome-level end-task accuracy per session, independent of internal labels (§3.3) - **new vs. V1**.
  - [ ] PNR computation: correction-injection procedure + threshold-based detection of correction failure, fit as a function of covariates (§3.4) - **new vs. V1**, this is the centerpiece.
- [ ] **Tier 1 (FinanceBench multi-session)** - primary experimental harness, build first.
- [ ] **Tier 2 (MemoryArena)** - secondary, cross-domain generalization, build after Tier 1 is validated.
- [ ] **Tier 3 (synthetic controlled injection)** - precise lineage-known dataset, session counts 1–10, build in parallel with or after Tier 1.
- [ ] **Core intervention experiment (§4.2)** - Vanilla / End-of-Horizon Check / Ours(Provenance-Gated), with the full 5-test statistical battery on PNR as outcome.
- [ ] **Statistical infrastructure** - bootstrap CIs (5,000 resamples), McNemar, permutation test, Cohen's h, unpaired χ², Fisher's exact - reusable across experiments, build as a shared stats utility rather than per-experiment.

---

## 7. Open questions log

Anything not fully pinned down should be logged here rather than silently decided in code, so it surfaces in the next sync with team.

### 7.1 Resolved, but worth flagging as a deliberate choice
- **Agent backend = Gemini models**, per V1 ("for the agentic pipeline, I am currently using Gemini models as agent's brain"*). Carried forward into V2 unless changed. Snowball itself used gpt-4o-mini/gemini-2.5-flash for different experiments - worth deciding whether V2 should test backend-sensitivity the way Snowball's Experiment 2 tested model-capability ceilings, or just fix one backend throughout. **Not yet decided - flag for sync.**
- **Tolerance bands for Tier A contamination check** - Snowball used 1% (detection instrument) and 2% (gate, to tolerate reformatting like "$71.2B" → "$71B"). Multi-session arithmetic (YoY-on-YoY, compounding derived values) may need wider or session-scaled tolerance to avoid false contamination flags from legitimate rounding propagation. **Needs empirical recalibration once Tier 1 harness exists - don't hardcode Snowball's exact numbers without re-checking.**

### 7.2 Genuinely open - needs a decision before or during the sync
- Exact correction-injection procedure for PNR measurement (§3.4, step 1): how "maximal salience/verification status" is operationalized - e.g., does the corrected value simply get `verification_status = VERIFIED` and re-injected as a new entry, or does it actively overwrite/supersede the contaminated entry? This affects whether PNR measures "can the system route around the error" vs. "can the system actively un-learn it" - these are different and reviewers may ask which one we mean.
- Whether MemoryArena (Tier 2) needs any adaptation to support session-tagged memory writes in the format §2.2 expects, or whether its native task structure already fits.
- Compression: Google Doc explicitly deferred "no compression to start, more sophisticated memory policies as ablations once the base phenomenon is established." Confirm this is still the plan - i.e., compression is a *future* ablation, not part of the Shared Blackboard vs. Provenance-Gated comparison itself.

### 7.3 Literature still to fully integrate into §1.4's table
Papers shared but not yet read closely enough to place precisely in the positioning table:
- https://arxiv.org/abs/2605.29463
- https://arxiv.org/abs/2512.23128
- https://arxiv.org/abs/2605.12978
- https://arxiv.org/abs/2503.03704
- https://arxiv.org/pdf/2505.06120
- https://arxiv.org/pdf/2307.03172
- https://arxiv.org/abs/2605.16746

As each gets read, add a row to §1.4 rather than leaving the positioning section thin - for an A* submission, the related-work section needs to show the same density of recent (2025–2026) citations the Snowball paper itself demonstrated.

---

## 8. One-paragraph summary (for re-orienting quickly at the start of a coding session)

We're building the cross-session successor to Hallucination Snowball. Where Snowball showed a single hallucination transforms and becomes undetectable across one pipeline's four agent handoffs, this project asks what happens when that pipeline has **persistent memory across many sessions**: does a planted error get reproduced and corroborated until it becomes permanently unrecoverable (a "point of no return"), or does it self-correct - and can we predict which, and when, as a function of memory architecture and other covariates? The architecture is a 5-agent pipeline (Researcher, Analyst, Writer, Reviewer, Memory-Curator) over a session-tagged key-value memory store, with a write-time contamination gate as the core new mechanism, tested under two memory architectures (Shared Blackboard vs. Provenance-Gated retrieval). The central deliverable is a predictive model of the point-of-no-return session horizon, validated with the same statistical rigor (multi-test batteries, bootstrap CIs, a closed-form predictive formula checked against held-out data) that made the original Snowball paper's claims credible - this is what separates the project from being "Snowball but with memory" and makes it a real A*-level contribution.
