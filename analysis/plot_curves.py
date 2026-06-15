"""
Plot the two key result curves for the paper.

Usage:
    python analysis/plot_curves.py
    python analysis/plot_curves.py --results_dir results --company 3M
"""

import argparse
import json
import os

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns

from analysis.metrics import load_metrics, compute_growth_rate, summarize_experiment


sns.set_theme(style="whitegrid", palette="colorblind")
FIGSIZE = (12, 5)
DPI = 150


def plot_detectability_decay(experiments: list[dict], title_suffix: str = "", save_path: str = None):
    """
    Figure 1: Detectability decay curve.
    X = session number, Y = detection rate (0-1)
    One line per experiment type (baseline, injected, tool_failure).
    """
    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)

    for exp in experiments:
        decay = exp["detectability_decay"]
        sessions = [d["session"] for d in decay]
        rates = [d["detection_rate"] for d in decay]
        label = exp["experiment"].replace("tier1_", "").replace("tier2_", "").replace("_", " ")
        ax.plot(sessions, rates, marker="o", linewidth=2, label=label)

        # mark point of no return
        ponr = exp.get("point_of_no_return")
        if ponr:
            ax.axvline(x=ponr, linestyle="--", alpha=0.4, color="red")

    # threshold line
    ax.axhline(y=0.20, linestyle=":", color="red", alpha=0.7, label="Point-of-No-Return threshold (20%)")

    ax.set_xlabel("Session Number", fontsize=12)
    ax.set_ylabel("Hallucination Detection Rate", fontsize=12)
    ax.set_title(f"Detectability Decay Across Sessions {title_suffix}", fontsize=14)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0))
    ax.set_ylim(-0.05, 1.05)
    ax.legend(fontsize=9)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path)
        print(f"Saved: {save_path}")
    else:
        plt.show()
    plt.close()


def plot_cluster_growth(experiments: list[dict], title_suffix: str = "", save_path: str = None):
    """
    Figure 2: Contamination cluster growth rate.
    X = session number, Y = number of contaminated memory entries.
    """
    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)

    for exp in experiments:
        growth = exp["cluster_growth"]
        sessions = [g["session"] for g in growth]
        sizes = [g["cluster_size"] for g in growth]
        label = exp["experiment"].replace("tier1_", "").replace("tier2_", "").replace("_", " ")
        ax.plot(sessions, sizes, marker="s", linewidth=2, label=label)

    ax.set_xlabel("Session Number", fontsize=12)
    ax.set_ylabel("Contaminated Memory Entries", fontsize=12)
    ax.set_title(f"Contamination Cluster Growth {title_suffix}", fontsize=14)
    ax.legend(fontsize=9)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path)
        print(f"Saved: {save_path}")
    else:
        plt.show()
    plt.close()


def plot_combined(experiments: list[dict], save_path: str = None):
    """
    Combined 2-panel figure (paper-ready layout):
    Left: detectability decay | Right: cluster growth
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5), dpi=DPI)

    colors = sns.color_palette("colorblind", n_colors=len(experiments))

    for i, exp in enumerate(experiments):
        label = exp["experiment"].replace("tier1_", "").replace("_", " ").title()
        color = colors[i]

        # left: detectability decay
        decay = exp["detectability_decay"]
        ax1.plot(
            [d["session"] for d in decay],
            [d["detection_rate"] for d in decay],
            marker="o", linewidth=2, color=color, label=label
        )
        ponr = exp.get("point_of_no_return")
        if ponr:
            ax1.axvline(x=ponr, linestyle="--", alpha=0.35, color=color)

        # right: cluster growth
        growth = exp["cluster_growth"]
        ax2.plot(
            [g["session"] for g in growth],
            [g["cluster_size"] for g in growth],
            marker="s", linewidth=2, color=color, label=label
        )

    ax1.axhline(y=0.20, linestyle=":", color="red", alpha=0.7, label="PONR threshold")
    ax1.set_xlabel("Session", fontsize=11)
    ax1.set_ylabel("Detection Rate", fontsize=11)
    ax1.set_title("Detectability Decay", fontsize=13)
    ax1.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0))
    ax1.set_ylim(-0.05, 1.05)
    ax1.legend(fontsize=8)

    ax2.set_xlabel("Session", fontsize=11)
    ax2.set_ylabel("Contaminated Entries", fontsize=11)
    ax2.set_title("Cluster Growth Rate", fontsize=13)
    ax2.legend(fontsize=8)

    fig.suptitle("Memory Hallucination Snowball: Cross-Session Propagation", fontsize=14, y=1.02)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, bbox_inches="tight")
        print(f"Saved: {save_path}")
    else:
        plt.show()
    plt.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results_dir", default="results")
    parser.add_argument("--company", default=None, help="Filter by company name substring")
    parser.add_argument("--save", action="store_true", help="Save figures instead of showing")
    args = parser.parse_args()

    all_metrics = load_metrics(args.results_dir)
    if not all_metrics:
        print(f"No *_metrics.json files found in {args.results_dir}/")
        print("Run tiers/tier1_finance.py first.")
        return

    if args.company:
        all_metrics = [m for m in all_metrics if args.company.lower() in m["experiment"].lower()]

    print(f"Loaded {len(all_metrics)} experiments")
    for m in all_metrics:
        s = summarize_experiment(m)
        print(f"  {s['experiment']}: PONR={s['point_of_no_return']}, AUC={s['decay_auc']:.3f}, superlinear={s['superlinear_growth']}")

    save_dir = args.results_dir if args.save else None

    plot_combined(
        all_metrics,
        save_path=os.path.join(save_dir, "combined_curves.png") if save_dir else None,
    )

    plot_detectability_decay(
        all_metrics,
        save_path=os.path.join(save_dir, "detectability_decay.png") if save_dir else None,
    )

    plot_cluster_growth(
        all_metrics,
        save_path=os.path.join(save_dir, "cluster_growth.png") if save_dir else None,
    )


if __name__ == "__main__":
    main()
