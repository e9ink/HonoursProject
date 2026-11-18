"""Generate DEAP thesis figures from existing pipeline outputs.

Usage (from project root):
    python deap/src/figures/make_figures.py

Outputs go to deap/figures/ (PNG + PDF) and deap/figures/data/ (CSV).
Every number comes from deap/reports/; script stops if a value is missing.
No chart titles inside images (captions go in the thesis).
"""

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import matplotlib
matplotlib.use("Agg")  # headless, deterministic

import matplotlib.pyplot as plt
import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent.parent  # deap/
DATA_ROOT = ROOT.parent                               # project root
REPORTS = ROOT / "reports"
FIGURES = ROOT / "figures"
DATA_DIR = FIGURES / "data"

# ---------------------------------------------------------------------------
# Style constants -- Wong colour-blind-safe palette (matches WESAD figures)
# ---------------------------------------------------------------------------
BLUE      = "#0072B2"
ORANGE    = "#E69F00"
GREEN     = "#009E73"
SKY       = "#56B4E9"
VERMILION = "#D55E00"
PURPLE    = "#CC79A7"
YELLOW    = "#F0E442"
BLACK     = "#000000"

FONT = "DejaVu Sans"
DPI  = 300

plt.rcParams.update({
    "font.family":        FONT,
    "font.size":          10,
    "axes.titlesize":     10,
    "axes.labelsize":     10,
    "xtick.labelsize":    9,
    "ytick.labelsize":    9,
    "legend.fontsize":    9,
    "figure.dpi":         DPI,
    "savefig.dpi":        DPI,
    "figure.facecolor":   "white",
    "axes.facecolor":     "white",
    "axes.spines.top":    False,
    "axes.spines.right":  False,
})


def _save(fig, stem: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    png = FIGURES / f"{stem}.png"
    pdf = FIGURES / f"{stem}.pdf"
    fig.savefig(png, dpi=DPI, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    print(f"  {png.relative_to(DATA_ROOT)}")
    print(f"  {pdf.relative_to(DATA_ROOT)}")


def _save_csv(rows: list, stem: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{stem}.csv"
    if rows:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    print(f"  {path.relative_to(DATA_ROOT)}")


# ---------------------------------------------------------------------------
# Figure 4.4 -- label audit: mismatches per participant
# ---------------------------------------------------------------------------
def fig4_4_label_audit():
    """
    One bar per participant (s01-s32, sorted numerically).
    Each bar shows the total label entries that disagree with
    participant_ratings.xls (before cleaning), with the subset also
    outside the SAM 1-9 scale shown in a contrasting colour at the bottom
    of the bar.

    Y-axis: "Label entries (of 160)"
    Data source: deap/reports/deap_label_audit.json
    """
    audit_path = REPORTS / "deap_label_audit.json"
    if not audit_path.exists():
        raise FileNotFoundError(f"Required report missing: {audit_path}")

    with open(audit_path, encoding="utf-8") as f:
        audit = json.load(f)

    xls_cmp = audit["v2_mirror"]["xls_comparison"]["per_participant"]
    sam_chk = audit["v2_mirror"]["sam_range_check"]["per_participant"]

    # Build sorted participant list
    pids = sorted(xls_cmp.keys(), key=lambda s: int(s[1:]))

    total_mismatches = []
    oor_counts = []
    for pid in pids:
        total = len(xls_cmp[pid]["discrepancies"])
        oor = sam_chk.get(pid, {}).get("out_of_range_count", 0)
        total_mismatches.append(total)
        oor_counts.append(oor)

    within_range = [t - o for t, o in zip(total_mismatches, oor_counts)]
    x = np.arange(len(pids))

    fig, ax = plt.subplots(figsize=(12, 4))

    # Stacked bar: OOR (bottom, more prominent), within-range on top
    bars_oor = ax.bar(x, oor_counts, color=VERMILION, label="Outside SAM scale [1,9]",
                      width=0.75)
    bars_wr  = ax.bar(x, within_range, bottom=oor_counts, color=ORANGE,
                      label="Within scale, mismatches XLS", width=0.75)

    ax.set_xticks(x)
    ax.set_xticklabels(pids, rotation=45, ha="right")
    ax.set_ylabel("Label entries (of 160)")
    ax.set_ylim(0, max(total_mismatches) * 1.15)
    ax.legend(loc="upper right", frameon=False)
    ax.yaxis.set_minor_locator(matplotlib.ticker.AutoMinorLocator())

    fig.tight_layout()
    _save(fig, "fig4_4_label_audit")
    plt.close(fig)

    # Data CSV
    rows = [{"participant": pid,
             "total_mismatches": t,
             "out_of_sam_range": o,
             "within_range_mismatches": t - o}
            for pid, t, o in zip(pids, total_mismatches, oor_counts)]
    _save_csv(rows, "fig4_4_label_audit")


# ---------------------------------------------------------------------------
# Figure 4.5 -- Temp scale split: range per participant
# ---------------------------------------------------------------------------
def fig4_5_temp_scale_split():
    """
    One point per participant (s01-s32, sorted numerically).
    Y-axis: Temp channel range (max minus min), log scale.
    Points coloured by group (Group A vs Group B).

    Y-axis label: "Temp channel range (units undocumented)"
    Data source: deap/reports/deap_baseline.json
    """
    baseline_path = REPORTS / "deap_baseline.json"
    if not baseline_path.exists():
        raise FileNotFoundError(f"Required report missing: {baseline_path}")

    with open(baseline_path, encoding="utf-8") as f:
        baseline = json.load(f)

    # Build lookup by participant id
    by_pid = {p["participant"]: p for p in baseline["participants"]}

    GROUP_A = {f"s{i:02d}" for i in range(1, 24)} | {"s25"}
    GROUP_B = {"s24"} | {f"s{i:02d}" for i in range(26, 33)}

    pids = sorted(by_pid.keys(), key=lambda s: int(s[1:]))
    x = np.arange(len(pids))

    ranges = []
    colors = []
    groups = []
    for pid in pids:
        temp = by_pid[pid]["channel_stats"]["Temp"]
        r = temp["max"] - temp["min"]
        # Clamp to small positive value for log scale if exactly 0
        r = max(r, 1e-6)
        ranges.append(r)
        if pid in GROUP_A:
            colors.append(BLUE)
            groups.append("A")
        else:
            colors.append(ORANGE)
            groups.append("B")

    fig, ax = plt.subplots(figsize=(12, 4))

    for xi, (r, c) in enumerate(zip(ranges, colors)):
        ax.scatter(xi, r, color=c, s=50, zorder=3)

    ax.set_xticks(x)
    ax.set_xticklabels(pids, rotation=45, ha="right")
    ax.set_yscale("log")
    ax.set_ylabel("Temp channel range (units undocumented)")

    # Legend
    import matplotlib.patches as mpatches
    legend_handles = [
        mpatches.Patch(color=BLUE,   label="Group A (s01-s23, s25)"),
        mpatches.Patch(color=ORANGE, label="Group B (s24, s26-s32)"),
    ]
    ax.legend(handles=legend_handles, loc="upper left", frameon=False)

    fig.tight_layout()
    _save(fig, "fig4_5_temp_scale_split")
    plt.close(fig)

    # Data CSV
    rows = [{"participant": pid, "temp_range": r, "group": g}
            for pid, r, g in zip(pids, ranges, groups)]
    _save_csv(rows, "fig4_5_temp_scale_split")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    import matplotlib.ticker
    globals()["matplotlib"] = matplotlib  # make ticker accessible inside functions
    # re-import ticker so the functions above can use it
    import matplotlib.ticker as _ticker
    matplotlib.ticker = _ticker

    print("Figure 4.4: label audit ...")
    fig4_4_label_audit()

    print("Figure 4.5: Temp scale split ...")
    fig4_5_temp_scale_split()

    print("Done.")


if __name__ == "__main__":
    main()
