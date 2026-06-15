# Memory Hallucination Snowball

> **A formal study of self-amplifying hallucination propagation in memory-augmented multi-session agent pipelines.**

This repository contains the full experimental pipeline for the paper:

**"The Memory Hallucination Snowball: Cross-Session Error Compounding in Memory-Augmented Agent Pipelines"**  
Prabhjot Singh · Jianing Zhu  
VITA Research Group, The University of Texas at Austin

---

## The Problem

> A hallucination that escapes detection in Run 1 gets written to long-term memory. In Run 2, it is retrieved and seeds derived analyses that corroborate it. Those corroborations are written back. By Run N, the original error is surrounded by a growing cluster of mutually consistent but false memories — and becomes practically impossible to correct.

**Nobody has formally modeled or measured this.** Specifically, these are open:

- Cross-session hallucination survival rate
- The rate at which contaminated memories become undetectable after N sessions
- The **point of no return** — the session horizon beyond which correction fails because the corroborating cluster outweighs any intervention

This paper fills that gap.

---

## Two Hallucination Sources (under one framework)

| Source | Description | Where in code |
|--------|-------------|---------------|
| **Injected** | We corrupt a specific memory write in session 1 (controlled, for ablation studies) | `pipeline/injector.py` |
| **Tool failure** | The financial data tool returns wrong values, which the agent writes to memory as fact | `pipeline/tools.py` — `FailureMode` enum |

Both sources produce generation-0 contamination. Everything downstream is automatically labeled as generation-1, 2, 3... via lineage tracking.

---

## Key Metrics

### 1. Detectability Decay Curve
After each session, an independent VerificationAgent checks all memory entries against ground truth. We plot:

```
detection_rate = true_positives / total_contaminated_entries
```

across sessions 1 → N. The session where detection rate drops below 20% and stays there is the **point of no return (PONR)**.

### 2. Cluster Growth Rate
We count contaminated memory entries after each session:

```
cluster_size[session] = count of entries where is_contaminated == True
```

If `cluster_size[i] / cluster_size[i-1] > 1.5` consistently, that is **superlinear growth** — the empirical proof of self-amplification.

### 3. Cluster by Generation
Breaks cluster size into generation depth (gen-0 = root, gen-1 = children, gen-2 = grandchildren...). Shows how deep the contamination tree grows per session.

---

## Experimental Tiers

### Tier 1 — FinanceBench (Primary)
Real SEC filings. No synthetic data.

**Scenario:** A financial analysis agent processes quarterly/annual earnings reports for a company, one filing per session. Memory persists across sessions. One hallucination (injected or tool-sourced) in session 1 compounds as the agent builds growth rates, trend analyses, projections, and investment reports in subsequent sessions — all referencing the false baseline.

**Why FinanceBench:** 150 QA pairs from real SEC filings with exact evidence text, clean ground truth answers, and multiple filings per company. Ground truth is unambiguous (revenue is either $34.2B or it isn't). Domain is legible to any reviewer.

**Companies with multiple sessions:** 3M, Adobe, Amazon, Amcor (and others — depends on what `download_financebench.py` finds).

**Three experiments per company:**
- `baseline` — no hallucinations, clean run
- `injected` — corrupted revenue figure injected in session 1
- `tool_failure` — FinancialDataTool returns wrong values (WRONG_VALUE mode)

### Tier 2 — MemoryArena (Secondary)
Cross-domain generalizability. MemoryArena provides human-crafted multi-session tasks in web navigation, preference-constrained planning, progressive information search, and sequential formal reasoning. If the contamination cluster phenomenon holds here too, the finding is domain-general.

*(tier2_memory_arena.py — in progress)*

### Tier 3 — Synthetic Dataset (Ablation)
Fully controlled. We construct fictional companies with known ground truth financials and perfect contamination lineage labels. Enables:

- Precise measurement of generation-N detectability
- Controlled severity experiments (subtle 5-10% vs high 25-35% deviation)
- Varying injection session (session 1 vs session 3 — does timing matter?)
- Scaling to 10 sessions to find PONR precisely

*(tier3_synthetic.py — in progress)*

---

## Repository Structure

```
memory-hallucination-snowball/
│
├── pipeline/                         # Core framework (model-agnostic)
│   ├── __init__.py
│   ├── memory.py                     # MemoryStore: flat key-value store with session
│   │                                 #   tagging, lineage tracking, contamination
│   │                                 #   inference, cluster metrics
│   ├── agents.py                     # 5 agent definitions (Gemini-powered)
│   │   ├── DataIntakeAgent           #   Agent 1: reads filings + tools → raw facts
│   │   ├── AnalysisAgent             #   Agent 2: derives metrics (gen-1 contamination)
│   │   ├── SynthesisAgent            #   Agent 3: cross-session narratives (gen-2+)
│   │   ├── VerificationAgent         #   Agent 4: imperfect fact-checker → decay curve
│   │   └── ReportingAgent            #   Agent 5: final output → joins cluster
│   ├── tools.py                      # FinancialDataTool with 4 failure modes:
│   │                                 #   NONE, WRONG_VALUE, STALE_DATA,
│   │                                 #   PARTIAL, TIMEOUT
│   ├── injector.py                   # HallucinationInjector: intercepts memory
│   │                                 #   writes, corrupts target entries, logs lineage
│   └── runner.py                     # PipelineRunner: session loop orchestrator,
│                                     #   metric collection, PONR detection, file I/O
│
├── tiers/                            # Experiment entry points
│   ├── __init__.py
│   ├── tier1_finance.py              # FinanceBench multi-session (Tier 1)
│   ├── tier2_memory_arena.py         # MemoryArena experiments (Tier 2) [WIP]
│   └── tier3_synthetic.py            # Synthetic controlled experiments (Tier 3) [WIP]
│
├── analysis/                         # Metrics and visualization
│   ├── __init__.py
│   ├── metrics.py                    # cluster growth rate, decay AUC, PONR,
│   │                                 #   superlinearity test, cross-experiment
│   │                                 #   comparison table
│   └── plot_curves.py                # matplotlib/seaborn plots:
│                                     #   detectability decay curve,
│                                     #   cluster growth curve,
│                                     #   combined paper-ready 2-panel figure
│
├── data/                             # Data loading and preparation
│   ├── __init__.py
│   ├── download_financebench.py      # Downloads PatronusAI/financebench from
│   │                                 #   HuggingFace, groups by company+period
│   │                                 #   into multi-session JSON structure
│   └── financebench/                 # Created at download time (gitignored)
│       ├── raw.json                  #   All 150 FinanceBench examples
│       └── multi_session.json        #   Grouped by company → sorted sessions
│
├── experiments/
│   └── configs/                      # YAML configs for experiment variants [WIP]
│
├── results/                          # Experiment outputs (gitignored)
│   ├── tier1_3m_baseline_metrics.json
│   ├── tier1_3m_baseline_memory.json
│   ├── tier1_3m_injected_metrics.json
│   ├── ...
│   └── combined_curves.png
│
├── tests/
│   └── test_pipeline.py              # Smoke tests (no API calls):
│                                     #   memory lineage, injector, tool failures,
│                                     #   context string, cluster metrics
│
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Memory Design

`MemoryStore` is a flat list of `MemoryEntry` objects. No summarization. No compression. Raw entries only.

```python
@dataclass
class MemoryEntry:
    key: str
    value: str
    session_id: int           # which session wrote this
    entry_id: str             # unique 8-char ID
    parent_ids: list[str]     # entry_ids that were in context when this was written
                              # → this is the lineage graph
    is_contaminated: bool     # ground truth label (auto-inferred from parents)
    generation: int           # 0=root, 1=child, 2=grandchild, ...
    source: str               # "agent" | "tool" | "injected"
    timestamp: str
```

**Contamination propagates automatically:** when an entry is written with `parent_ids` that include any contaminated entry, `is_contaminated` is set to `True` and `generation` is incremented. No manual labeling.

**The family tree builds itself** as agents write to memory across sessions.

---

## Quickstart

### 1. Clone and install

```bash
git clone https://github.com/prabhjotschugh/memory-hallucination-snowball
cd memory-hallucination-snowball
pip install -r requirements.txt
```

### 2. Set your Gemini API key

```bash
export GEMINI_API_KEY=your_key_here
```

To use a different model (default is `gemini-2.5-flash`):

```bash
export GEMINI_MODEL=gemini-2.5-pro   # for final paper experiments
```

### 3. Download FinanceBench data (one time)

```bash
python data/download_financebench.py
```

This downloads the real FinanceBench dataset from HuggingFace (`PatronusAI/financebench`) and groups it by company into multi-session format. Saved to `data/financebench/`.

### 4. Run smoke tests (no API calls, instant)

```bash
python tests/test_pipeline.py
```

Verifies memory lineage, injector, tool failures, context strings, and cluster metrics. Should output `All tests passed.`

### 5. Run Tier 1 experiments

```bash
python -m tiers.tier1_finance
```

Runs baseline, injected, and tool_failure experiments for all companies with multiple sessions in FinanceBench. Results saved to `results/`.

### 6. Plot the curves

```bash
python analysis/plot_curves.py --save
```

Generates `results/combined_curves.png` — the two-panel figure with detectability decay and cluster growth curves.

---

## Understanding the Output

After each experiment run, two files are saved per experiment:

**`{experiment_name}_metrics.json`** — the key measurement output:
```json
{
  "experiment": "tier1_3m_injected",
  "total_sessions": 3,
  "detectability_decay": [
    {"session": 1, "detection_rate": 0.85},
    {"session": 2, "detection_rate": 0.42},
    {"session": 3, "detection_rate": 0.11}
  ],
  "cluster_growth": [
    {"session": 1, "cluster_size": 1},
    {"session": 2, "cluster_size": 4},
    {"session": 3, "cluster_size": 9}
  ],
  "point_of_no_return": 3
}
```

**`{experiment_name}_memory.json`** — full memory dump with contamination labels, generation depth, and parent lineage for every entry. Used for qualitative analysis and error inspection.

---

## Tool Failure Modes

The `FinancialDataTool` simulates a financial data API with four failure modes:

| Mode | What happens | Hallucination source |
|------|-------------|---------------------|
| `NONE` | Returns correct value | Baseline |
| `WRONG_VALUE` | Returns ±15–30% corrupted numeric value, marked as `is_hallucinated=True` | Tool |
| `STALE_DATA` | Returns prior period's value as current | Tool |
| `PARTIAL` | Returns `[DATA UNAVAILABLE]`, agent may confabulate | Agent (induced) |
| `TIMEOUT` | Returns `[TIMEOUT]`, agent may confabulate | Agent (induced) |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | *(required)* | Your Google Gemini API key |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Model to use. Options: `gemini-2.5-flash`, `gemini-2.5-pro` |

---
