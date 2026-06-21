# MemorySnowball - Development Plan

**Companion to:** `PROJECT_CONTEXT.md` (the research spec). This file is the *build order* - what to tell your AI coding agent, in what sequence, and how to know each piece actually works before moving on.

**Core rule for the whole project:** build the smallest thing that could possibly be wrong, test it, then add the next layer. V1 failed not because the idea was bad, but because a subtle bug (lineage flag mistaken for correctness flag) sat undetected under several layers of code. Every phase below ends with a test that would have caught that exact class of bug.

---

## 0. Standards to set before writing any code

Tell your AI agent these rules up front - paste them as a system/project instruction if your tool supports it:

1. **One concept, one field.** Never let one variable silently mean two things (this is what broke V1 - `is_contaminated` meant both "inherited from a contaminated parent" and "is actually wrong"). If a field could be ambiguous, give it a more specific name.
2. **Every random process gets a fixed seed.** No exceptions. This is what makes results reproducible and is non-negotiable for the paper.
3. **Log everything about an injection.** When you plant a fake error, record: what session, what the true value was, what the fake value was, why (which rule fired). You will need to trace this back later.
4. **Write a test before trusting a number.** Any time you compute a metric (decay rate, cluster size, PNR), write a tiny synthetic example where you already know the right answer, and check the code gets it.
5. **Small functions, obvious names.** `check_contamination()` not `process()`. Your collaborator (and future you) needs to read this without you explaining it.
6. **Don't let the agent silently fix things.** If your AI coding tool wants to "improve" the contamination logic while building something else, stop it - flag it instead of letting scope creep into the gate logic.
7. **Keep raw injected-error metadata and computed labels in separate tables/files.** Ground truth (what you planted) should never be touched by the system being tested. This is your answer key - protect it.

---

## 1. Build order (phases)

Each phase is something you can hand to your AI agent as one focused task, with a clear "done" condition. Don't start phase N+1 until phase N's test passes.

### Phase 1 - The memory store (no agents yet)
**Build:** Just the data structure from `PROJECT_CONTEXT.md` §2.2. A place to store entries with `entry_id`, `session_id`, `content`, `state_tag`, `parent_ids`, `is_contaminated`, `verification_status`, `injection_metadata`. Functions to write an entry, read entries (by session, by id), and trace `parent_ids` back to their origin.

**Why first:** Everything else depends on this, and it's the easiest place to re-introduce V1's bug if you're not careful. Get it right in isolation.

**Test before moving on:**
- Write 3 fake entries by hand where you know the lineage (A is the parent of B, B is the parent of C).
- Mark only A as `is_contaminated = True`.
- Confirm B and C do **not** automatically become contaminated - `is_contaminated` must stay exactly as you set it, never auto-inherited.
- Confirm you *can* still trace C → B → A through `parent_ids` (lineage tracing works, it's just not the same thing as the contamination flag).

This single test is the most important one in the whole project. It directly checks the bug that killed V1.

### Phase 2 - The contamination checker (Tier A only, deterministic)
**Build:** The numeric ground-truth checker from §2.4 - given an entry with a checkable number, compare it against the real FinanceBench value within some tolerance, return True/False. No LLM calls yet.

**Test before moving on:**
- Feed it 5–10 hand-made examples: exact match (should pass), a value within tolerance (should pass), an obviously wrong value (should fail), a value with different formatting like "$71.2B" vs "71200000000" (should still match if your tolerance logic is right).
- This is a pure function - same input, same output, every time. Easy to unit test thoroughly. Do that.

### Phase 3 - One agent, no memory, on one task
**Build:** Just the Researcher agent. Give it one FinanceBench question, let it extract a number, save the output. No pipeline, no memory yet.

**Test before moving on:**
- Run it on 5 known questions where you already know the right answer.
- Confirm the contamination checker (Phase 2) correctly flags it when you manually inject a wrong number into the Researcher's output.

### Phase 4 - Full single-session pipeline (no memory across sessions)
**Build:** All 5 agents wired together - Researcher → Analyst → Writer → Reviewer → Memory-Curator - for **one session only**. The Curator writes to the memory store from Phase 1, using the checker from Phase 2, but there's no session 2 yet to read it back.

**Test before moving on:**
- Inject one hallucination at the Researcher stage.
- Confirm it shows up correctly tagged in memory after the full pipeline runs (contaminated entry has `verification_status = FLAGGED_CONTAMINATED`, lineage correctly shows it came from the injection).
- This is basically a mini-version of the original Snowball paper's pipeline, just stopping at the memory write instead of a final output. If this doesn't work cleanly, nothing after it will.

### Phase 5 - Two sessions, memory read-back (the actual new mechanism)
**Build:** Run session 2. This time, Researcher and Analyst read from memory before doing their work (per §2.1). Use Shared Blackboard (the simple, unfiltered condition) first - don't build Provenance-Gated yet.

**Test before moving on:**
- Inject a hallucination in session 1 only.
- Confirm session 2's Analyst output, which depends on the bad session-1 memory, is now also flagged contaminated by the Phase 2 checker.
- This is your first real "snowball across sessions" evidence - the moment you can see this working end-to-end, the core mechanism is proven.

### Phase 6 - Extend to many sessions, add the two metrics
**Build:** Loop sessions 1 through, say, 10. Add the detectability decay curve (§3.1) and cluster growth count (§3.2) as something you compute after each session.

**Test before moving on:**
- Run the full 10-session loop on one question with one injected error.
- Plot decay and cluster growth by hand from the logged data and sanity check: does cluster size only ever grow or stay flat (never shrink without a correction event)? Does detection rate trend downward, not bounce around randomly?

### Phase 7 - Add the write-time gate + Provenance-Gated condition
**Build:** The gate from §2.3 (runs the Phase 2 checker before every write, sets `verification_status`). Then build the second memory-read policy: Provenance-Gated retrieval, which ranks/filters by that status (§2.5).

**Test before moving on:**
- Run the *same* 10-session, same-injected-error setup under both Shared Blackboard and Provenance-Gated.
- Confirm they actually produce **different** memory states by session 5 or so. If they're identical, your gate isn't doing anything - debug before scaling up.

### Phase 8 - Outcome-level accuracy metric
**Build:** Score the final report/output of each session against real ground truth (§3.3) - independent of all the internal contamination flags.

**Test:** Confirm a session with a known injected, uncorrected error scores worse than a clean session, using a metric you computed completely separately from the internal labels.

### Phase 9 - Point of No Return (PNR) experiment
**Build:** The correction-injection procedure from §3.4 - at a chosen session, "fix" the error and see if the system recovers or not. Run this at different session numbers (correct at session 2, correct at session 4, correct at session 7, etc.) and see where recovery stops working.

**Test:** This is the experiment itself, not a unit test - but a good sanity check is to **first run it on Tier 3 (synthetic, controlled data)** where you fully control how strongly errors corroborate each other. If you can't find a point of no return even in data you constructed to have one, something upstream is broken.

### Phase 10 - Statistics layer
**Build:** Bootstrap confidence intervals, McNemar's test, permutation test, Cohen's h, Fisher's exact - as one shared, reusable module (§4.3). Apply it to the Phase 7 (Shared Blackboard vs. Provenance-Gated) comparison.

**Test:** Run the stats functions on a toy dataset where you know the answer (e.g., two clearly different groups should give you a tiny p-value; two identical groups should give you a p-value near 1).

### Phase 11 - Scale up: real experiments
Only now do you run the full thing across all of FinanceBench (Tier 1), then Tier 2 (MemoryArena), then formalize Tier 3 properly. Everything before this was building and proving the machine works on a small scale.

---

## 2. Order summary (quick reference)

```
1. Memory store (data only)              → test: lineage ≠ contamination
2. Contamination checker (Tier A)        → test: known right/wrong values
3. One agent, one task                   → test: known Q&A pairs
4. Full pipeline, single session         → test: injection gets flagged correctly
5. Two sessions, memory read-back        → test: error spreads to session 2
6. Many sessions + 2 core metrics        → test: curves behave sensibly
7. Write-gate + 2 memory conditions      → test: conditions actually differ
8. Outcome-level accuracy metric         → test: bad session scores worse
9. Point-of-no-return experiment         → test: works on controlled synthetic data first
10. Statistics module                    → test: known-different vs known-same toy data
11. Full-scale real experiments
```

---

## 3. A few simple ground rules while working with the AI coding agent

- **Give it one phase at a time.** Don't paste the whole `PROJECT_CONTEXT.md` and say "build all of this." Say "build Phase 1 from `DEV_PLAN.md`, here's the schema from `PROJECT_CONTEXT.md` §2.2."
- **Always ask it to write the test alongside the code**, not after. If it writes Phase 1's memory store, immediately ask it to write the lineage-vs-contamination test before you move on.
- **When something looks "too clean," be suspicious.** If decay curves look perfectly smooth on the first run, check whether you're accidentally measuring something trivial (this is exactly how V1's bug hid - the numbers looked plausible).
- **Re-read the relevant section of `PROJECT_CONTEXT.md` before each phase**, and paste just that section to the agent - it keeps the agent's context focused and matches how the spec doc was organized for this exact purpose.
- **Commit after every phase passes its test**, with a commit message that names the phase. This gives you a clean rollback point - exactly the thing you wished you had when V1 needed a rollback.
