"""
Download and prepare FinanceBench data from HuggingFace.

FinanceBench (PatronusAI) — 150 open-source QA pairs from real SEC filings.
Each entry has: company, doc_name, doc_type, doc_period, question, answer,
evidence (with actual text from the filing), doc_link.

For our multi-session experiments, we group questions by company + doc_period
so that each session corresponds to a real fiscal year/quarter filing.

Run:
    python data/download_financebench.py
"""

import json
import os
from collections import defaultdict

from datasets import load_dataset


OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "financebench")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def download_and_prepare():
    print("Loading FinanceBench from HuggingFace (PatronusAI/financebench)...")
    ds = load_dataset("PatronusAI/financebench", split="train")
    print(f"Loaded {len(ds)} examples")

    # save raw data
    raw_path = os.path.join(OUTPUT_DIR, "raw.json")
    raw_data = [dict(row) for row in ds]

    # evidence is a list of dicts — serialize cleanly
    for row in raw_data:
        if "evidence" in row and row["evidence"]:
            row["evidence"] = [
                {k: v for k, v in e.items()} for e in row["evidence"]
            ]

    with open(raw_path, "w") as f:
        json.dump(raw_data, f, indent=2)
    print(f"Raw data saved to {raw_path}")

    # group by company -> sorted by doc_period
    # this gives us the multi-session structure:
    # session 1 = earliest filing, session N = latest filing
    company_sessions: dict[str, list[dict]] = defaultdict(list)
    for row in raw_data:
        company_sessions[row["company"]].append(row)

    multi_session = {}
    for company, rows in company_sessions.items():
        # sort by doc_period (year as int)
        sorted_rows = sorted(rows, key=lambda r: r.get("doc_period", 0))

        # group by doc_name (one doc = one session)
        doc_groups: dict[str, list[dict]] = defaultdict(list)
        for row in sorted_rows:
            doc_groups[row["doc_name"]].append(row)

        sessions = []
        for doc_name, doc_rows in doc_groups.items():
            sessions.append({
                "doc_name": doc_name,
                "doc_type": doc_rows[0]["doc_type"],
                "doc_period": doc_rows[0]["doc_period"],
                "doc_link": doc_rows[0]["doc_link"],
                "questions": [
                    {
                        "financebench_id": r["financebench_id"],
                        "question": r["question"],
                        "answer": r["answer"],
                        "question_type": r["question_type"],
                        "question_reasoning": r["question_reasoning"],
                        "evidence": r["evidence"],
                    }
                    for r in doc_rows
                ],
            })

        if len(sessions) >= 2:  # only keep companies with multiple filings
            multi_session[company] = sessions

    ms_path = os.path.join(OUTPUT_DIR, "multi_session.json")
    with open(ms_path, "w") as f:
        json.dump(multi_session, f, indent=2)

    print(f"\nMulti-session companies ({len(multi_session)}):")
    for company, sessions in multi_session.items():
        periods = [s["doc_period"] for s in sessions]
        print(f"  {company}: {len(sessions)} sessions — periods {periods}")

    print(f"\nMulti-session data saved to {ms_path}")
    return multi_session


def load_financebench_raw() -> list[dict]:
    path = os.path.join(OUTPUT_DIR, "raw.json")
    if not os.path.exists(path):
        raise FileNotFoundError("Run download_financebench.py first.")
    with open(path) as f:
        return json.load(f)


def load_multi_session() -> dict[str, list[dict]]:
    path = os.path.join(OUTPUT_DIR, "multi_session.json")
    if not os.path.exists(path):
        raise FileNotFoundError("Run download_financebench.py first.")
    with open(path) as f:
        return json.load(f)


if __name__ == "__main__":
    download_and_prepare()
