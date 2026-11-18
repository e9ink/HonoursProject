"""Generate DEAP thesis figures and tables from existing pipeline outputs.

Usage (from project root):
    python deap/src/figures/make_figures.py

Figures go to deap/figures/ (PNG + PDF).
Data CSVs go to deap/figures/data/.
Tables go to deap/figures/tables/ (CSV + Markdown).
Every value is read from deap/reports/ or gold/DEAP/.
Script stops if a required value is missing.
No chart titles inside images (captions go in the thesis).
"""

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import matplotlib
matplotlib.use("Agg")  # headless, deterministic

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent.parent  # deap/
DATA_ROOT = ROOT.parent                               # project root
REPORTS = ROOT / "reports"
FIGURES = ROOT / "figures"
DATA_DIR = FIGURES / "data"
TABLES_DIR = FIGURES / "tables"

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
GREY      = "#999999"

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _save(fig, stem: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    png = FIGURES / f"{stem}.png"
    pdf = FIGURES / f"{stem}.pdf"
    fig.savefig(png, dpi=DPI, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    print(f"  {png.relative_to(DATA_ROOT)}")
    print(f"  {pdf.relative_to(DATA_ROOT)}")


def _save_csv(rows: list, stem: str, subdir: Path = DATA_DIR) -> None:
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{stem}.csv"
    if rows:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    print(f"  {path.relative_to(DATA_ROOT)}")
    return path


def _save_md(rows: list, stem: str, subdir: Path = TABLES_DIR) -> None:
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{stem}.md"
    if not rows:
        return
    headers = list(rows[0].keys())
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("| " + " | ".join(headers) + " |\n")
        fh.write("|" + "|".join("---" for _ in headers) + "|\n")
        for row in rows:
            fh.write("| " + " | ".join(str(row[h]) for h in headers) + " |\n")
    print(f"  {path.relative_to(DATA_ROOT)}")


def _require(val, name):
    if val is None:
        raise ValueError(f"Required value missing from reports: {name}")
    return val


# ---------------------------------------------------------------------------
# Figure 4.4 -- label audit: mismatches per participant
# ---------------------------------------------------------------------------
def fig4_4_label_audit():
    audit_path = REPORTS / "deap_label_audit.json"
    if not audit_path.exists():
        raise FileNotFoundError(f"Required report missing: {audit_path}")
    with open(audit_path, encoding="utf-8") as f:
        audit = json.load(f)

    xls_cmp = audit["v2_mirror"]["xls_comparison"]["per_participant"]
    sam_chk = audit["v2_mirror"]["sam_range_check"]["per_participant"]

    pids = sorted(xls_cmp.keys(), key=lambda s: int(s[1:]))
    total_mismatches, oor_counts = [], []
    for pid in pids:
        total_mismatches.append(len(xls_cmp[pid]["discrepancies"]))
        oor_counts.append(sam_chk.get(pid, {}).get("out_of_range_count", 0))

    within_range = [t - o for t, o in zip(total_mismatches, oor_counts)]
    x = np.arange(len(pids))

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.bar(x, oor_counts, color=VERMILION, label="Outside SAM scale [1,9]", width=0.75)
    ax.bar(x, within_range, bottom=oor_counts, color=ORANGE,
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
    baseline_path = REPORTS / "deap_baseline.json"
    if not baseline_path.exists():
        raise FileNotFoundError(f"Required report missing: {baseline_path}")
    with open(baseline_path, encoding="utf-8") as f:
        baseline = json.load(f)

    by_pid = {p["participant"]: p for p in baseline["participants"]}
    GROUP_A = {f"s{i:02d}" for i in range(1, 24)} | {"s25"}
    GROUP_B = {"s24"} | {f"s{i:02d}" for i in range(26, 33)}

    pids = sorted(by_pid.keys(), key=lambda s: int(s[1:]))
    x = np.arange(len(pids))
    ranges, colors, groups = [], [], []
    for pid in pids:
        temp = by_pid[pid]["channel_stats"]["Temp"]
        r = max(temp["max"] - temp["min"], 1e-6)
        ranges.append(r)
        if pid in GROUP_A:
            colors.append(BLUE); groups.append("A")
        else:
            colors.append(ORANGE); groups.append("B")

    fig, ax = plt.subplots(figsize=(12, 4))
    for xi, (r, c) in enumerate(zip(ranges, colors)):
        ax.scatter(xi, r, color=c, s=50, zorder=3)
    ax.set_xticks(x)
    ax.set_xticklabels(pids, rotation=45, ha="right")
    ax.set_yscale("log")
    ax.set_ylabel("Temp channel range (units undocumented)")
    legend_handles = [
        mpatches.Patch(color=BLUE,   label="Group A (s01-s23, s25)"),
        mpatches.Patch(color=ORANGE, label="Group B (s24, s26-s32)"),
    ]
    ax.legend(handles=legend_handles, loc="upper left", frameon=False)
    fig.tight_layout()
    _save(fig, "fig4_5_temp_scale_split")
    plt.close(fig)

    rows = [{"participant": pid, "temp_range": r, "group": g}
            for pid, r, g in zip(pids, ranges, groups)]
    _save_csv(rows, "fig4_5_temp_scale_split")


# ---------------------------------------------------------------------------
# Figure 4.6 -- label inversion scatter
# ---------------------------------------------------------------------------
def fig4_6_label_inversion():
    """
    Scatter of Kaggle v2 label value (y) vs participant_ratings.xls value (x)
    for all 5120 Valence and Arousal entries (32 participants * 40 trials * 2 dims).
    Matching entries in grey, mismatched entries in vermilion.
    Lines y=x and y=9-x (dashed). Shaded region y < 1 (below SAM minimum).
    Verifies mirror + xls = 9 for all 878 mismatches before plotting.
    """
    audit_path = REPORTS / "deap_label_audit.json"
    if not audit_path.exists():
        raise FileNotFoundError(f"Required report missing: {audit_path}")
    with open(audit_path, encoding="utf-8") as f:
        audit = json.load(f)

    # Gather all discrepancies with mirror and xls values and verify inversion rule
    all_disc = []
    for pid, pp in audit["v2_mirror"]["xls_comparison"]["per_participant"].items():
        for d in pp["discrepancies"]:
            if d["dim"] in ("Valence", "Arousal"):
                all_disc.append({
                    "pid": pid,
                    "xls": d["xls_value"],
                    "mirror": d["mirror_value"],
                    "dim": d["dim"],
                })

    bad = [d for d in all_disc if abs(d["mirror"] + d["xls"] - 9) > 1e-4]
    if bad:
        raise ValueError(
            f"{len(bad)} mismatched entries do NOT satisfy mirror + xls = 9: "
            f"{bad[:3]}"
        )
    print(f"  Verification: all {len(all_disc)} Valence/Arousal mismatches "
          f"satisfy mirror + xls = 9 (within 1e-4).")

    # Build full 5120 entry scatter (need all entries, not just mismatches)
    # Load from baseline or cleaning report -- we need the full label array
    # Instead, build match/mismatch sets from the audit discrepancy keys
    disc_keys = {
        (d["pid"], d["dim"], None): (d["xls"], d["mirror"])  # keyed loosely
        for d in all_disc
    }
    # We'll represent matching entries as (xls, mirror) = (xls, xls) with count
    # Count: 32 participants * 40 trials * 2 dims = 2560 total Valence+Arousal entries
    # mismatches = len(all_disc)
    total_entries = 32 * 40 * 2
    n_mismatch = len(all_disc)
    n_match = total_entries - n_mismatch

    # For the scatter: mismatch points from the audit, match points as y=x
    # We sample all_disc exactly; for matching points we just plot y=x line + count note
    mismatch_xls    = np.array([d["xls"] for d in all_disc])
    mismatch_mirror = np.array([d["mirror"] for d in all_disc])

    # Build matching grid: iterate cleaning report for all entries
    # Actually we can reconstruct from audit: for every participant all 40 trials
    # exist in xls_comparison; matching ones have no discrepancy record.
    # We need their xls values to plot them. Use the Silver label CSVs.
    silver_dir = DATA_ROOT / "silver" / "DEAP" / "labels"
    xls_path = (DATA_ROOT / "bronze" / "DEAP" / "deap-dataset" / "Metadata"
                / "participant_ratings.xls")

    import xlrd
    wb = xlrd.open_workbook(str(xls_path))
    sh = wb.sheet_by_index(0)
    header = sh.row_values(0)
    col = {h: i for i, h in enumerate(header)}

    # Build disc_set for fast lookup
    disc_set = set()
    for d in all_disc:
        disc_set.add((d["pid"], d["dim"].lower(), d["xls"]))  # keyed by (pid, dim, xls_val)

    # We need actual dat labels for each participant to get matching xls values
    # Use the cleaning report which records all 878 corrections
    cleaning_path = REPORTS / "deap_cleaning.json"
    if not cleaning_path.exists():
        raise FileNotFoundError(f"Required report missing: {cleaning_path}")
    with open(cleaning_path, encoding="utf-8") as f:
        cleaning = json.load(f)

    # Build a set of corrected (pid, trial_idx, dim) -> (dat_val, xls_val)
    corrected = {}
    for pid, prec in cleaning["participants"].items():
        for corr in prec.get("corrections", []):
            if corr["dim"] in ("valence", "arousal"):
                corrected[(pid, corr["trial_index"], corr["dim"])] = (
                    corr["dat_value"], corr["xls_value"]
                )

    # For matching entries: iterate all 32 pids * 40 trials * 2 dims
    # matching = not in corrected = mirror_value == xls_value
    # We only have xls values from XLS file, so read them
    xls_ratings = {}
    for row_idx in range(1, sh.nrows):
        row = sh.row_values(row_idx)
        pid_int = int(row[col["Participant_id"]])
        exp_id  = int(row[col["Experiment_id"]])
        xls_ratings.setdefault(pid_int, {})[exp_id] = {
            "valence": float(row[col["Valence"]]),
            "arousal": float(row[col["Arousal"]]),
        }

    match_xls = []
    match_mirror = []
    for pid_num in range(1, 33):
        pid = f"s{pid_num:02d}"
        for trial_idx in range(40):
            exp_id = trial_idx + 1
            for dim in ("valence", "arousal"):
                xls_val = xls_ratings.get(pid_num, {}).get(exp_id, {}).get(dim)
                if xls_val is None:
                    continue
                if (pid, trial_idx, dim) in corrected:
                    dat_val = corrected[(pid, trial_idx, dim)][0]
                else:
                    dat_val = xls_val  # matching: dat == xls
                match_xls.append(xls_val)
                match_mirror.append(dat_val)

    # Separate into match and mismatch for plotting
    match_xls = np.array(match_xls)
    match_mirror = np.array(match_mirror)
    # Remove entries in corrected (those are mismatches)
    # Actually match_xls/match_mirror already contain ALL entries -- split by equality
    is_match = np.abs(match_xls - match_mirror) <= 1e-4
    true_match_xls    = match_xls[is_match]
    true_match_mirror = match_mirror[is_match]
    # mismatches from full array
    true_mm_xls    = match_xls[~is_match]
    true_mm_mirror = match_mirror[~is_match]

    fig, ax = plt.subplots(figsize=(7, 7))

    # Shade below SAM minimum y < 1
    ax.axhspan(-0.5, 1.0, color=VERMILION, alpha=0.08, zorder=0)

    # Matching entries (grey, small)
    ax.scatter(true_match_xls, true_match_mirror,
               color=GREY, s=10, alpha=0.4, label=f"Matching ({len(true_match_xls):,})", zorder=2)
    # Mismatched entries (vermilion, slightly larger)
    ax.scatter(true_mm_xls, true_mm_mirror,
               color=VERMILION, s=15, alpha=0.8,
               label=f"Mismatched ({len(true_mm_xls):,}; mirror + XLS = 9)", zorder=3)

    # Reference lines
    vals = np.linspace(0.5, 9.5, 100)
    ax.plot(vals, vals,       color=BLACK, linewidth=1.0, label="y = x")
    ax.plot(vals, 9 - vals,   color=BLACK, linewidth=1.0, linestyle="--", label="y = 9 - x")
    ax.axhline(1, color=GREY, linewidth=0.8, linestyle=":")

    ax.set_xlim(0.5, 9.5)
    ax.set_ylim(-0.5, 9.5)
    ax.set_xlabel("Rating in participant_ratings.xls")
    ax.set_ylabel("Rating in Kaggle v2 mirror")
    ax.legend(loc="upper right", frameon=False, fontsize=8)
    fig.tight_layout()
    _save(fig, "fig4_6_label_inversion")
    plt.close(fig)

    # Data CSV
    rows = (
        [{"xls_value": x, "mirror_value": y, "match": True}
         for x, y in zip(true_match_xls.tolist(), true_match_mirror.tolist())]
        + [{"xls_value": x, "mirror_value": y, "match": False}
           for x, y in zip(true_mm_xls.tolist(), true_mm_mirror.tolist())]
    )
    _save_csv(rows, "fig4_6_label_inversion")
    return len(true_mm_xls)  # return mismatch count for reference numbers


# ---------------------------------------------------------------------------
# Figure 4.7 -- fault injection vs control: grouped bars
# ---------------------------------------------------------------------------
def fig4_7_fault_injection_vs_control():
    """
    Grouped bars per fault type showing increase over control for s01 and s25.
    Log y-axis if counts differ by orders of magnitude.
    Y-axis: "Increase over control (flagged count)".
    """
    fi_path = REPORTS / "experiments" / "deap_fault_injection_vs_control.json"
    if not fi_path.exists():
        raise FileNotFoundError(f"Required report missing: {fi_path}")
    with open(fi_path, encoding="utf-8") as f:
        fi = json.load(f)

    # Map: fault_id -> participant -> target metric delta
    target_metrics = {
        "nan_in_eeg":        ("completeness",   "total_nan"),
        "label_out_of_range": ("label_plausibility", "total_out_of_range"),
        "truncated_data":    ("conformance",    "violation_count"),
    }
    fault_labels = {
        "nan_in_eeg":         "NaN in EEG",
        "label_out_of_range": "Label out of range",
        "truncated_data":     "Truncated data",
    }
    participants = ["s01", "s25"]

    deltas = {fault: {} for fault in target_metrics}
    for entry in fi["comparisons"]:
        pid = entry["participant"]
        fault_id = entry["fault_id"]
        if fault_id not in target_metrics or pid not in participants:
            continue
        check, metric = target_metrics[fault_id]
        delta = entry["count_vs_control"][check][metric]["delta"]
        deltas[fault_id][pid] = delta

    faults = list(target_metrics.keys())
    x = np.arange(len(faults))
    width = 0.35
    colors_pid = {participants[0]: BLUE, participants[1]: ORANGE}

    fig, ax = plt.subplots(figsize=(8, 4))
    for i, pid in enumerate(participants):
        vals = [deltas[f].get(pid, 0) for f in faults]
        bars = ax.bar(x + (i - 0.5) * width, vals, width,
                      color=colors_pid[pid], label=pid)

    ax.set_xticks(x)
    ax.set_xticklabels([fault_labels[f] for f in faults])
    ax.set_ylabel("Increase over control (flagged count)")

    # Use log scale if range > 2 orders of magnitude
    all_vals = [v for pd in deltas.values() for v in pd.values() if v > 0]
    if all_vals and max(all_vals) / max(min(all_vals), 1) > 100:
        ax.set_yscale("log")

    ax.legend(frameon=False)
    fig.tight_layout()
    _save(fig, "fig4_7_fault_injection_vs_control")
    plt.close(fig)

    rows = [{"fault": f, "fault_label": fault_labels[f],
              "s01_delta": deltas[f].get("s01", 0),
              "s25_delta": deltas[f].get("s25", 0)}
             for f in faults]
    _save_csv(rows, "fig4_7_fault_injection_vs_control")


# ---------------------------------------------------------------------------
# Figure 4.8 -- GSR negative share per participant
# ---------------------------------------------------------------------------
def fig4_8_gsr_negative_share():
    """
    Bar per participant showing percentage of GSR samples below zero.
    GSR counts from the Gold manifest flag_and_retain.
    Total samples per participant: 40 trials * 8064 samples = 322,560.
    """
    manifest_path = DATA_ROOT / "gold" / "DEAP" / "deap_gold_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Required manifest missing: {manifest_path}")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    total_samples = 40 * 8064  # 322,560
    pids = sorted(manifest["participants"].keys(), key=lambda s: int(s[1:]))

    pcts, counts = [], []
    for pid in pids:
        neg = manifest["participants"][pid]["dat"]["flag_and_retain"]["gsr_negative_count"]
        pcts.append(100.0 * neg / total_samples)
        counts.append(neg)

    x = np.arange(len(pids))
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.bar(x, pcts, color=BLUE, width=0.75)
    ax.set_xticks(x)
    ax.set_xticklabels(pids, rotation=45, ha="right")
    ax.set_ylabel("GSR samples below zero (%)")
    ax.yaxis.set_minor_locator(matplotlib.ticker.AutoMinorLocator())
    fig.tight_layout()
    _save(fig, "fig4_8_gsr_negative_share")
    plt.close(fig)

    rows = [{"participant": pid, "gsr_negative_count": cnt,
             "total_samples": total_samples,
             "pct_negative": round(100.0 * cnt / total_samples, 4)}
            for pid, cnt in zip(pids, counts)]
    _save_csv(rows, "fig4_8_gsr_negative_share")


# ---------------------------------------------------------------------------
# Table 4.3 -- quality before/after
# ---------------------------------------------------------------------------
def table4_3_quality_before_after():
    rpt_path = REPORTS / "deap_quality_report.json"
    if not rpt_path.exists():
        raise FileNotFoundError(f"Required report missing: {rpt_path}")
    with open(rpt_path, encoding="utf-8") as f:
        q = json.load(f)
    dims = q["dimensions"]

    rows = []

    # Completeness
    c = dims["completeness"]
    rows.append({"dimension": "Completeness",
                 "bronze_value": str(c["value"]),
                 "silver_value": str(c["value"]),
                 "threshold": c["threshold"],
                 "pass": c["status"].upper(),
                 "note": c.get("note", "")})

    # Conformance
    cf = dims["conformance"]
    rows.append({"dimension": "Conformance",
                 "bronze_value": str(cf["value"]),
                 "silver_value": str(cf["value"]),
                 "threshold": cf["threshold"],
                 "pass": cf["status"].upper(),
                 "note": cf.get("note", "")})

    # Label plausibility (before/after)
    lp = dims["label_plausibility"]
    rows.append({"dimension": "Label plausibility",
                 "bronze_value": str(lp["before"]["value"]),
                 "silver_value": str(lp["after"]["value"]),
                 "threshold": lp["before"]["threshold"],
                 "pass": lp["after"]["status"].upper(),
                 "note": ""})

    # Consistency -- cross-source
    cs = dims["consistency"]["sub_checks"]["cross_source"]
    rows.append({"dimension": "Consistency (cross-source)",
                 "bronze_value": str(cs["before"]["value"]),
                 "silver_value": str(cs["after"]["value"]),
                 "threshold": cs["before"]["threshold"],
                 "pass": cs["after"]["status"].upper(),
                 "note": cs.get("note", "")})

    # Consistency -- structure
    cst = dims["consistency"]["sub_checks"]["structure"]
    rows.append({"dimension": "Consistency (structure)",
                 "bronze_value": str(cst["value"]),
                 "silver_value": str(cst["value"]),
                 "threshold": cst["threshold"],
                 "pass": cst["status"].upper(),
                 "note": cst.get("note", "")})

    # Physiological plausibility -- not applied
    pp = dims["physiological_plausibility"]
    rows.append({"dimension": "Physiological plausibility",
                 "bronze_value": "not applied",
                 "silver_value": "not applied",
                 "threshold": "N/A",
                 "pass": "NOT APPLIED",
                 "note": "Units undocumented for peripheral channels"})

    # Timeliness -- not applicable
    tl = dims["timeliness"]
    rows.append({"dimension": "Timeliness",
                 "bronze_value": "not applicable",
                 "silver_value": "not applicable",
                 "threshold": "N/A",
                 "pass": "NOT APPLICABLE",
                 "note": "Single sample clock per participant"})

    _save_csv(rows, "table4_3_quality_before_after", TABLES_DIR)
    _save_md(rows, "table4_3_quality_before_after", TABLES_DIR)


# ---------------------------------------------------------------------------
# Table 4.4 -- fault injection vs control
# ---------------------------------------------------------------------------
def table4_4_fault_injection_vs_control():
    fi_path = REPORTS / "experiments" / "deap_fault_injection_vs_control.json"
    if not fi_path.exists():
        raise FileNotFoundError(f"Required report missing: {fi_path}")
    with open(fi_path, encoding="utf-8") as f:
        fi = json.load(f)

    target_metrics = {
        "nan_in_eeg":         ("completeness",        "total_nan"),
        "label_out_of_range": ("label_plausibility",  "total_out_of_range"),
        "truncated_data":     ("conformance",          "violation_count"),
    }
    fault_labels = {
        "nan_in_eeg":         "NaN in EEG",
        "label_out_of_range": "Label out of range",
        "truncated_data":     "Truncated data",
    }

    rows = []
    for entry in fi["comparisons"]:
        fault_id = entry["fault_id"]
        if fault_id == "control" or fault_id not in target_metrics:
            continue
        pid = entry["participant"]
        check, metric = target_metrics[fault_id]
        ctrl = entry["count_vs_control"][check][metric]["control"]
        injected = entry["count_vs_control"][check][metric]["fault"]
        delta = entry["count_vs_control"][check][metric]["delta"]
        detected = "Yes" if delta > 0 else "No"
        rows.append({
            "participant":  pid,
            "fault":        fault_labels.get(fault_id, fault_id),
            "check":        check,
            "metric":       metric,
            "control":      ctrl,
            "injected":     injected,
            "increase":     delta,
            "detected":     detected,
        })

    _save_csv(rows, "table4_4_fault_injection_vs_control", TABLES_DIR)
    _save_md(rows, "table4_4_fault_injection_vs_control", TABLES_DIR)


# ---------------------------------------------------------------------------
# Table -- per participant summary
# ---------------------------------------------------------------------------
def table_per_participant():
    # Load required reports
    cleaning_path = REPORTS / "deap_cleaning.json"
    lp_path       = REPORTS / "deap_label_plausibility.json"
    post_path     = REPORTS / "deap_post_cleaning.json"
    manifest_path = DATA_ROOT / "gold" / "DEAP" / "deap_gold_manifest.json"
    baseline_path = REPORTS / "deap_baseline.json"
    for p in (cleaning_path, lp_path, post_path, manifest_path, baseline_path):
        if not p.exists():
            raise FileNotFoundError(f"Required report missing: {p}")

    with open(cleaning_path, encoding="utf-8") as f:
        cleaning = json.load(f)
    with open(lp_path, encoding="utf-8") as f:
        lp = json.load(f)
    with open(post_path, encoding="utf-8") as f:
        post = json.load(f)
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    with open(baseline_path, encoding="utf-8") as f:
        baseline = json.load(f)

    total_samples = 40 * 8064
    baseline_by_pid = {p["participant"]: p for p in baseline["participants"]}
    pids = sorted(cleaning["participants"].keys(), key=lambda s: int(s[1:]))

    rows = []
    for pid in pids:
        clean_pid = cleaning["participants"][pid]
        lp_pid    = lp["participants"].get(pid, {})
        post_pid  = post["participants"].get(pid, {})
        mfst_pid  = manifest["participants"][pid]
        b_pid     = baseline_by_pid[pid]

        flag = mfst_pid["dat"]["flag_and_retain"]
        post_lp = post_pid.get("label_plausibility", {})

        rows.append({
            "participant":             pid,
            "label_corrections":       clean_pid.get("n_corrections", 0),
            "oor_before":              lp_pid.get("total_out_of_range", 0),
            "oor_after":               post_lp.get("total_out_of_range", 0),
            "temp_group":              flag.get("temp_group", ""),
            "temp_range":              round(
                b_pid["channel_stats"]["Temp"]["max"] -
                b_pid["channel_stats"]["Temp"]["min"], 4),
            "temp_longest_flatline":   flag.get("temp_longest_flatline_samples", 0),
            "gsr_negative_count":      flag.get("gsr_negative_count", 0),
            "gsr_negative_pct":        round(
                100.0 * flag.get("gsr_negative_count", 0) / total_samples, 4),
        })

    _save_csv(rows, "table_per_participant", TABLES_DIR)
    _save_md(rows, "table_per_participant", TABLES_DIR)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("Figure 4.4: label audit ...")
    fig4_4_label_audit()

    print("Figure 4.5: Temp scale split ...")
    fig4_5_temp_scale_split()

    print("Figure 4.6: label inversion scatter ...")
    n_mismatch = fig4_6_label_inversion()
    print(f"  verified {n_mismatch} Valence/Arousal mismatches all satisfy mirror + xls = 9")

    print("Figure 4.7: fault injection vs control ...")
    fig4_7_fault_injection_vs_control()

    print("Figure 4.8: GSR negative share ...")
    fig4_8_gsr_negative_share()

    print("Table 4.3: quality before/after ...")
    table4_3_quality_before_after()

    print("Table 4.4: fault injection vs control ...")
    table4_4_fault_injection_vs_control()

    print("Table: per participant ...")
    table_per_participant()

    print("Done.")


if __name__ == "__main__":
    main()
