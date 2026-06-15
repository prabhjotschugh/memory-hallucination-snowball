"""
Metrics for measuring hallucination propagation across sessions.

Two core measurements for the paper:
  1. Detectability decay  — detection_rate vs session number
  2. Cluster growth rate  — contaminated_entries vs session number

Also computes:
  - Growth rate per session (is it superlinear?)
  - Point of no return
  - Cross-experiment comparison stats
"""

import json
import math
import os
from typing import Optional


def load_metrics(results_dir: str = "results") -> list[dict]:
    """Load all *_metrics.json files from results directory."""
    metrics = []
    for fname in os.listdir(results_dir):
        if fname.endswith("_metrics.json"):
            with open(os.path.join(results_dir, fname)) as f:
                metrics.append(json.load(f))
    return metrics


def compute_growth_rate(cluster_growth: list[dict]) -> list[dict]:
    """
    Compute per-session growth rate of contamination cluster.
    growth_rate[i] = cluster_size[i] / cluster_size[i-1]
    Superlinear growth (consistently > 1.5) is self-amplification proof.
    """
    rates = []
    for i, point in enumerate(cluster_growth):
        if i == 0 or cluster_growth[i - 1]["cluster_size"] == 0:
            rate = None
        else:
            prev = cluster_growth[i - 1]["cluster_size"]
            curr = point["cluster_size"]
            rate = round(curr / prev, 3) if prev > 0 else None
        rates.append({
            "session": point["session"],
            "cluster_size": point["cluster_size"],
            "growth_rate": rate,
        })
    return rates


def is_superlinear(cluster_growth: list[dict], threshold: float = 1.5) -> bool:
    """
    Returns True if average per-session growth rate > threshold.
    This is the empirical proof of self-amplification.
    """
    rates = compute_growth_rate(cluster_growth)
    valid_rates = [r["growth_rate"] for r in rates if r["growth_rate"] is not None]
    if not valid_rates:
        return False
    return (sum(valid_rates) / len(valid_rates)) > threshold


def decay_auc(detectability_decay: list[dict]) -> float:
    """
    Area under the detectability decay curve.
    Lower AUC = faster decay = worse contamination.
    Useful for comparing experiments.
    """
    if len(detectability_decay) < 2:
        return detectability_decay[0]["detection_rate"] if detectability_decay else 1.0

    auc = 0.0
    for i in range(1, len(detectability_decay)):
        # trapezoid rule
        h = 1  # session step = 1
        y0 = detectability_decay[i - 1]["detection_rate"]
        y1 = detectability_decay[i]["detection_rate"]
        auc += h * (y0 + y1) / 2
    return round(auc, 4)


def find_point_of_no_return(
    detectability_decay: list[dict],
    threshold: float = 0.20,
) -> Optional[int]:
    """Session where detection_rate first drops below threshold and stays there."""
    below = False
    for point in detectability_decay:
        if point["detection_rate"] <= threshold:
            if not below:
                below = True
                ponr = point["session"]
        else:
            below = False
    return ponr if below else None


def summarize_experiment(metrics: dict) -> dict:
    """Full summary for one experiment."""
    decay = metrics["detectability_decay"]
    growth = metrics["cluster_growth"]

    return {
        "experiment": metrics["experiment"],
        "sessions": metrics["total_sessions"],
        "point_of_no_return": metrics.get("point_of_no_return"),
        "decay_auc": decay_auc(decay),
        "superlinear_growth": is_superlinear(growth),
        "final_cluster_size": growth[-1]["cluster_size"] if growth else 0,
        "final_detection_rate": decay[-1]["detection_rate"] if decay else 1.0,
        "growth_rates": compute_growth_rate(growth),
    }


def compare_experiments(results_dir: str = "results") -> list[dict]:
    """Load all experiments and produce comparison table."""
    all_metrics = load_metrics(results_dir)
    return [summarize_experiment(m) for m in all_metrics]


def print_comparison_table(results_dir: str = "results"):
    summaries = compare_experiments(results_dir)

    header = f"{'Experiment':<45} {'PONR':>5} {'AUC':>6} {'SuperLin':>9} {'FinalCluster':>13} {'FinalDetect':>12}"
    print("\n" + "=" * len(header))
    print("EXPERIMENT COMPARISON")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for s in sorted(summaries, key=lambda x: x["experiment"]):
        ponr = str(s["point_of_no_return"]) if s["point_of_no_return"] else "none"
        print(
            f"{s['experiment']:<45} "
            f"{ponr:>5} "
            f"{s['decay_auc']:>6.3f} "
            f"{'YES' if s['superlinear_growth'] else 'NO':>9} "
            f"{s['final_cluster_size']:>13} "
            f"{s['final_detection_rate']:>11.1%}"
        )
    print("=" * len(header))
