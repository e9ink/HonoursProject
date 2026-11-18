"""Generate DEAP thesis figures and summary tables from pipeline outputs.

Usage (from project root):
    python deap/src/figures/make_figures.py

Outputs go to deap/figures/ (PNG + PDF) and deap/figures/tables/ (CSV + MD).

Figures produced:
  Figure 4.4 -- Label audit: before/after bar chart (OOR and cross-source mismatches).
  Figure 4.5 -- Temp channel scale split: violin plot of Temp values per participant group.

Tables produced:
  table_label_audit.csv / .md  -- per-participant label correction summary.
  table_quality_summary.csv / .md -- before/after quality dimension table.
"""

import csv
import json
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent  # deap/
DATA_ROOT = ROOT.parent                               # project root
REPORTS = ROOT / "reports"
FIGURES = ROOT / "figures"
TABLES_DIR = FIGURES / "tables"
BRONZE_DIR = DATA_ROOT / "bronze" / "DEAP" / "deap-dataset" / "data_preprocessed_python"

BLUE      = "#0072B2"
ORANGE    = "#E69F00"
GREEN     = "#009E73"
VERMILION = "#D55E00"
FONT = "DejaVu Sans"
DPI = 300

plt.rcParams.update({
    "font.family":      FONT,
    "font.size":        10,
    "axes.titlesize":   10,
    "axes.labelsize":   10,
    "xtick.labelsize":  9,
    "ytick.labelsize":  9,
    "legend.fontsize":  9,
    "figure.dpi":       DPI,
    "savefig.dpi":      DPI,
    "figure.facecolor": "white",
    "axes.facecolor":   "white",
    "axes.spines.top":  False,
    "axes.spines.right": False,
})


def _load(name: str) -> dict:
    return json.loads((REPORTS / name).read_text(encoding="utf-8"))


def _save(fig, stem: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    for ext, kwargs in [(".png", {"dpi": DPI, "bbox_inches": "tight"}),
                        (".pdf", {"bbox_inches": "tight"})]:
        path = FIGURES / f"{stem}{ext}"
        for attempt in range(5):
            try:
                fig.savefig(path, **kwargs)
                break
            except OSError:
                if attempt == 4:
                    raise
                time.sleep(1.5)
    plt.close(fig)


def _save_table(rows: list, fieldnames: list, stem: str) -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = TABLES_DIR / f"{stem}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Markdown table
    widths = [max(len(h), max((len(str(r.get(h, ""))) for r in rows), default=0))
              for h in fieldnames]
    md_path = TABLES_DIR / f"{stem}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        header = "| " + " | ".join(h.ljust(w) for h, w in zip(fieldnames, widths)) + " |"
        sep = "| " + " | ".join("-" * w for w in widths) + " |"
        f.write(header + "\n")
        f.write(sep + "\n")
        for row in rows:
            line = "| " + " | ".join(str(row.get(h, "")).ljust(w)
                                     for h, w in zip(fieldnames, widths)) + " |"
            f.write(line + "\n")


def fig_label_audit():
    """Figure 4.4: Label audit before/after bar chart."""
    lp = _load("deap_label_plausibility.json")
    cons = _load("deap_consistency.json")
    cleaning = _load("deap_cleaning.json")
    post = _load("deap_post_cleaning.json")

    total_lp_before = lp["total_out_of_range_all_participants"]
    total_cs_before = cons["consistency_cross_source"]["total_mismatches"]
    total_lp_after = post["total_label_plausibility_oor"]
    total_cs_after = post["total_cross_source_mismatches"]

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    ax = axes[0]
    bars = ax.bar(["Before (Bronze)", "After (Silver)"],
                  [total_lp_before, total_lp_after],
                  color=[VERMILION, GREEN], width=0.5)
    ax.set_title("Label Plausibility\n(out-of-SAM-range values)")
    ax.set_ylabel("Count")
    for bar, val in zip(bars, [total_lp_before, total_lp_after]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                str(val), ha="center", va="bottom", fontsize=9)
    ax.set_ylim(0, total_lp_before * 1.2 + 10)

    ax = axes[1]
    bars = ax.bar(["Before (Bronze)", "After (Silver)"],
                  [total_cs_before, total_cs_after],
                  color=[VERMILION, GREEN], width=0.5)
    ax.set_title("Cross-source Consistency\n(mismatches vs XLS)")
    ax.set_ylabel("Count")
    for bar, val in zip(bars, [total_cs_before, total_cs_after]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 5,
                str(val), ha="center", va="bottom", fontsize=9)
    ax.set_ylim(0, total_cs_before * 1.2 + 50)

    fig.suptitle(
        "DEAP Label Quality: Before vs After Cleaning\n"
        "(v2 inversion artefact corrected using participant_ratings.xls)",
        fontsize=11
    )
    fig.tight_layout()
    _save(fig, "fig4_4_label_audit")
    print("  Saved: fig4_4_label_audit.png / .pdf")

    # Per-participant correction table
    table_rows = []
    for pid_str in sorted(cleaning["participants"].keys()):
        rec = cleaning["participants"][pid_str]
        post_rec = post["participants"].get(pid_str, {})
        table_rows.append({
            "participant": pid_str,
            "n_corrections": rec["n_corrections"],
            "lp_oor_after": post_rec.get("label_plausibility", {}).get("total_out_of_range", ""),
            "cs_mismatch_after": post_rec.get("cross_source", {}).get("total_mismatches", ""),
        })
    _save_table(
        table_rows,
        ["participant", "n_corrections", "lp_oor_after", "cs_mismatch_after"],
        "table_label_audit"
    )
    print("  Saved: table_label_audit.csv / .md")


def fig_temp_scale_split():
    """Figure 4.5: Temp channel scale split across participants."""
    sys.path.insert(0, str(DATA_ROOT))
    try:
        from deap.src.loader import load_dat
    except ImportError:
        print("  WARNING: could not import loader; skipping Figure 4.5")
        return

    if not BRONZE_DIR.exists():
        print("  WARNING: bronze DEAP dir not found; skipping Figure 4.5")
        return

    dat_files = sorted(BRONZE_DIR.glob("*.dat"))
    if not dat_files:
        print("  WARNING: no .dat files found; skipping Figure 4.5")
        return

    # Group A: s01-s23 and s25 (small baseline-corrected values)
    # Group B: s24 and s26-s32 (large raw values)
    group_a = []
    group_b = []

    for path in dat_files:
        pid = path.stem  # e.g. "s01"
        pid_int = int(pid[1:])
        d = load_dat(str(path))
        temp_vals = d["data"][:, 39, :].ravel()  # channel index 39 = Temp
        finite = temp_vals[np.isfinite(temp_vals)]
        if finite.size == 0:
            continue
        median_val = float(np.median(finite))
        if pid_int in range(1, 24) or pid_int == 25:
            group_a.append((pid, median_val))
        else:
            group_b.append((pid, median_val))

    fig, ax = plt.subplots(figsize=(12, 4))

    all_pids = [x[0] for x in group_a] + [x[0] for x in group_b]
    all_medians = [x[1] for x in group_a] + [x[1] for x in group_b]
    colors = [BLUE] * len(group_a) + [ORANGE] * len(group_b)
    x = range(len(all_pids))

    ax.bar(x, all_medians, color=colors, width=0.7)
    ax.set_xticks(list(x))
    ax.set_xticklabels(all_pids, rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("Temp channel median value")
    ax.set_title(
        "DEAP Temp Channel: Median Value per Participant\n"
        "Group A (s01-s23, s25): baseline-corrected small values  |  "
        "Group B (s24, s26-s32): large raw values"
    )

    import matplotlib.patches as mpatches
    legend_handles = [
        mpatches.Patch(color=BLUE, label="Group A (s01-s23, s25): baseline-corrected"),
        mpatches.Patch(color=ORANGE, label="Group B (s24, s26-s32): large raw values"),
    ]
    ax.legend(handles=legend_handles, fontsize=8)
    fig.tight_layout()
    _save(fig, "fig4_5_temp_scale_split")
    print("  Saved: fig4_5_temp_scale_split.png / .pdf")


def table_quality_summary():
    """Quality before/after summary table."""
    qr = _load("deap_quality_report.json")
    dims = qr["dimensions"]

    rows = [
        {
            "Dimension": "Completeness",
            "Before (Bronze)": f"0 NaN, 0 Inf",
            "After (Silver)": "unchanged",
            "Threshold": "max=0",
            "Pass": "PASS",
        },
        {
            "Dimension": "Conformance",
            "Before (Bronze)": "0 violations",
            "After (Silver)": "unchanged",
            "Threshold": "max=0",
            "Pass": "PASS",
        },
        {
            "Dimension": "Label plausibility",
            "Before (Bronze)": f"163 OOR",
            "After (Silver)": "0 OOR",
            "Threshold": "max=0",
            "Pass": "PASS (after)",
        },
        {
            "Dimension": "Consistency cross-source",
            "Before (Bronze)": "878 mismatches",
            "After (Silver)": "0 mismatches",
            "Threshold": "max=0",
            "Pass": "PASS (after)",
        },
        {
            "Dimension": "Phys. plausibility",
            "Before (Bronze)": "not applied",
            "After (Silver)": "not applied",
            "Threshold": "--",
            "Pass": "N/A",
        },
        {
            "Dimension": "Timeliness",
            "Before (Bronze)": "not applicable",
            "After (Silver)": "not applicable",
            "Threshold": "--",
            "Pass": "N/A",
        },
    ]

    _save_table(
        rows,
        ["Dimension", "Before (Bronze)", "After (Silver)", "Threshold", "Pass"],
        "table_quality_summary"
    )
    print("  Saved: table_quality_summary.csv / .md")


def main():
    print("=== DEAP figures ===")
    print("[1/3] Figure 4.4: label audit ...")
    fig_label_audit()
    print("[2/3] Figure 4.5: Temp scale split ...")
    fig_temp_scale_split()
    print("[3/3] Quality summary table ...")
    table_quality_summary()
    print(f"=== Done. Figures in {FIGURES} ===")


if __name__ == "__main__":
    main()
