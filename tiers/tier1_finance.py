"""
Tier 1: FinanceBench Multi-Session Experiment.

Uses REAL FinanceBench data (PatronusAI/financebench) loaded from HuggingFace.
No dummy data. All filing text comes from actual SEC documents via the evidence field.

Scenario:
  - Pick a company with multiple filings in FinanceBench (e.g., 3M, Adobe, Amazon)
  - Each filing = one session
  - Sessions are ordered chronologically by doc_period
  - Agent reads actual evidence text from FinanceBench, extracts facts, writes to memory
  - One hallucination injected in session 1

Three experiments per company:
  A. Baseline     — no hallucinations
  B. Injected     — corrupted revenue figure in session 1
  C. Tool failure — financial_data tool returns wrong values

Run:
    python data/download_financebench.py   # once
    python -m tiers.tier1_finance
"""

import json
import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from data.download_financebench import load_multi_session
from pipeline.runner import PipelineRunner, SessionConfig
from pipeline.tools import ToolRegistry, FinancialDataTool, FailureMode
from pipeline.injector import HallucinationInjector


def make_key(question: str) -> str:
    """Generate a clean, alpha-numeric key from a question."""
    clean = re.sub(r"[^a-zA-Z0-9_]", "", question[:60].lower().replace(" ", "_"))
    return clean


def build_ground_truth_from_financebench(sessions: list[dict]) -> dict:
    """
    Build ground truth dict from FinanceBench answer fields.
    Used by VerificationAgent and FinancialDataTool.

    Format: { question_text_snippet: answer, ... }
    Also add a flat key for each answer by financebench_id.
    """
    gt = {}
    for session in sessions:
        for q in session["questions"]:
            # keyed by financebench_id
            gt[q["financebench_id"]] = q["answer"]
            # also key by a short question hash for tool lookups
            gt[make_key(q["question"])] = q["answer"]
    return gt


def build_filing_text_from_evidence(session: dict) -> str:
    """
    Construct the filing text for a session from FinanceBench evidence strings.
    Each question in a session has evidence_text extracted from the actual SEC filing.
    We concatenate them (deduplicated) to form the raw input for DataIntakeAgent.
    """
    seen = set()
    parts = []

    parts.append(f"=== {session['doc_name']} ({session['doc_type'].upper()}, {session['doc_period']}) ===")
    parts.append(f"Source: {session['doc_link']}\n")

    for q in session["questions"]:
        for ev in q.get("evidence", []):
            text = ev.get("evidence_text", "").strip()
            if text and text not in seen:
                seen.add(text)
                parts.append(text)

    parts.append("\n=== TARGET QUESTIONS TO ANSWER AND WRITE TO MEMORY ===")
    parts.append("IMPORTANT: You must write the answer to each question to memory.")
    parts.append("You MUST use the exact key provided in parentheses for each question, overriding the default key naming convention.\n")
    
    for i, q in enumerate(session["questions"], 1):
        parts.append(f"{i}. {q['question']}\n   (Use exact key: {make_key(q['question'])})")

    return "\n\n".join(parts)


def run_experiment(
    company: str,
    sessions: list[dict],
    experiment_type: str,  # "baseline" | "injected" | "tool_failure"
) -> dict:
    print(f"\n{'#'*70}")
    print(f"TIER 1 | {company} | {experiment_type.upper()}")
    print(f"Sessions: {[s['doc_name'] for s in sessions]}")
    print(f"{'#'*70}")

    ground_truth = build_ground_truth_from_financebench(sessions)

    # build tool: uses ground truth answers as the data source
    if experiment_type == "tool_failure":
        financial_tool = FinancialDataTool(
            ground_truth=ground_truth,
            failure_mode=FailureMode.WRONG_VALUE,
            failure_rate=1.0,
        )
    else:
        financial_tool = FinancialDataTool(
            ground_truth=ground_truth,
            failure_mode=FailureMode.NONE,
        )

    tools = ToolRegistry()
    tools.register("financial_data", financial_tool)

    # build injector for "injected" experiment
    injector = None
    if experiment_type == "injected":
        injector = HallucinationInjector()
        # inject into session 1: corrupt the first numeric answer we find
        first_session = sessions[0]
        for q in first_session["questions"]:
            answer = q["answer"]
            # find a numeric answer to corrupt
            try:
                val_str = answer.replace("$", "").replace(",", "").replace("%", "").strip()
                numeric = float(val_str.split()[0])
                # corrupt by 25% downward
                corrupted = str(round(numeric * 0.75, 2))
                # key: first 60 chars of question as identifier
                key_hint = make_key(q["question"])
                injector.add_injection(
                    session_id=1,
                    key=key_hint,
                    corrupted_value=corrupted,
                    true_value=val_str.split()[0],
                    severity="high",
                )
                print(f"  Injection planned: {key_hint} | true={val_str.split()[0]} | corrupted={corrupted}")
                break
            except (ValueError, IndexError):
                continue

    runner = PipelineRunner(
        ground_truth=ground_truth,
        tools=tools,
        injector=injector,
        experiment_name=f"tier1_{company.lower()}_{experiment_type}",
    )

    # build session configs from real FinanceBench data
    session_configs = [
        SessionConfig(
            session_id=i + 1,
            filing_text=build_filing_text_from_evidence(s),
            company=company,
            doc_name=s["doc_name"],
        )
        for i, s in enumerate(sessions)
    ]

    runner.run(session_configs)
    return runner.save(output_dir="results")


def main():
    print("Loading FinanceBench multi-session data...")
    multi_session = load_multi_session()

    # Use all available companies from FinanceBench
    # Override with TARGET_COMPANIES env var if you want to test specific companies
    import os
    target_companies = os.getenv("TARGET_COMPANIES", "").split(",")
    target_companies = [c.strip() for c in target_companies if c.strip()]
    
    if target_companies:
        # Filter to only requested companies
        companies_to_run = [c for c in target_companies if c in multi_session]
        print(f"  Using filtered companies: {companies_to_run}")
    else:
        # Use ALL companies from FinanceBench
        companies_to_run = list(multi_session.keys())
        print(f"  Using all available companies: {companies_to_run}")

    for company in companies_to_run:
        if company not in multi_session:
            print(f"  {company} not found in multi-session data, skipping")
            continue

        sessions = multi_session[company]
        print(f"\n{company}: {len(sessions)} sessions available")

        # run all three experiment types
        for exp_type in ["baseline", "injected", "tool_failure"]:
            run_experiment(company, sessions, exp_type)

    print("\n\nAll Tier 1 experiments complete. Results in results/")
    print("Run: python analysis/plot_curves.py to visualize")


if __name__ == "__main__":
    main()
