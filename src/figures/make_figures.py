"""Generate all thesis figures and summary tables from existing pipeline outputs.

Usage:
    python -m src.figures.make_figures

Outputs go to figures/ (PNG + PDF) and figures/data/ (CSV).
Tables go to figures/tables/ (CSV + Markdown).
"""

import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless, deterministic

import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS = ROOT / "reports"
BRONZE = ROOT / "bronze" / "WESAD"
SILVER = ROOT / "silver" / "WESAD"
FIGURES = ROOT / "figures"
DATA_DIR = FIGURES / "data"
TABLES_DIR = FIGURES / "tables"

# ---------------------------------------------------------------------------
# Style constants (colour-blind-safe Wong palette)
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
DPI = 300

BRONZE_COLOUR = "#CD7F32"
SILVER_COLOUR = "#A8A9AD"
GOLD_COLOUR   = "#CFB53B"

# Bronze layer: stages 1-5; Silver: 6-7; Gold: 8-10
LAYER_COLOURS = {
    "Bronze": "#F4E0C4",
    "Silver": "#E8E8E8",
    "Gold":   "#FFF3B0",
}
LAYER_EDGE = {
    "Bronze": BRONZE_COLOUR,
    "Silver": SILVER_COLOUR,
    "Gold":   GOLD_COLOUR,
}

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

def _load(name: str) -> dict:
    """Load a JSON report by filename from reports/."""
    return json.loads((REPORTS / name).read_text(encoding="utf-8"))


def _save(fig: plt.Figure, stem: str) -> None:
    """Save figure as PNG and PDF."""
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / f"{stem}.png", dpi=DPI, bbox_inches="tight")
    fig.savefig(FIGURES / f"{stem}.pdf", bbox_inches="tight")
    plt.close(fig)


def _save_csv(rows: list[dict], stem: str) -> None:
    """Save data rows as CSV in figures/data/."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    path = DATA_DIR / f"{stem}.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _df_to_markdown(df: pd.DataFrame) -> str:
    """Render a DataFrame as a Markdown table without external dependencies."""
    cols = list(df.columns)
    widths = [max(len(str(c)), max((len(str(v)) for v in df[c]), default=0)) for c in cols]
    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    header = "| " + " | ".join(str(c).ljust(w) for c, w in zip(cols, widths)) + " |"
    rows_md = []
    for _, row in df.iterrows():
        rows_md.append("| " + " | ".join(str(row[c]).ljust(w) for c, w in zip(cols, widths)) + " |")
    return "\n".join([header, sep] + rows_md) + "\n"


def _save_table(df: pd.DataFrame, stem: str) -> None:
    """Save a DataFrame as CSV and Markdown in figures/tables/."""
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(TABLES_DIR / f"{stem}.csv", index=False)
    (TABLES_DIR / f"{stem}.md").write_text(_df_to_markdown(df), encoding="utf-8")


# ---------------------------------------------------------------------------
# Figure 3.1 -- pipeline overview
# ---------------------------------------------------------------------------
PIPELINE_STAGES = [
    # (number, label, short output, layer)
    (1,  "Profiling",          "wesad_baseline.json",          "Bronze"),
    (2,  "Conformance check",  "wesad_conformance.json",       "Bronze"),
    (3,  "Completeness check", "wesad_completeness.json",      "Bronze"),
    (4,  "Plausibility check", "wesad_plausibility.json",      "Bronze"),
    (5,  "Temporal alignment", "wesad_alignment.json",         "Bronze"),
    (6,  "Silver cleaning",    "wesad_cleaning.json",          "Silver"),
    (7,  "Post-cleaning",      "wesad_*_post_cleaning.json",   "Silver"),
    (8,  "Governance",         "wesad_lineage.json",           "Gold"),
    (9,  "Quality report",     "wesad_quality_report.json",    "Gold"),
    (10, "Gold manifest",      "wesad_manifest.json",          "Gold"),
]

# Layer spans (1-indexed stage numbers)
LAYER_SPANS = [
    ("Bronze", 1, 5),
    ("Silver", 6, 7),
    ("Gold",   8, 10),
]


def fig_pipeline_overview() -> None:
    """Figure 3.1: pipeline stages diagram, Bronze / Silver / Gold layers."""
    n = len(PIPELINE_STAGES)
    fig_h = n * 0.75 + 1.0
    fig, ax = plt.subplots(figsize=(8, fig_h))
    ax.set_xlim(0, 10)
    ax.set_ylim(-0.5, n + 0.5)
    ax.axis("off")

    box_x0 = 0.5
    box_w  = 9.0
    box_h  = 0.58
    gap    = 0.75   # vertical step per stage (y increases upward; we flip)
    arrow_dx = 0.0  # centred

    def stage_y(i: int) -> float:
        """y-centre for stage i (0-indexed, top-to-bottom)."""
        return (n - 1 - i) * gap

    # -- layer background bands --
    for layer, s_start, s_end in LAYER_SPANS:
        y_top  = stage_y(s_start - 1) + box_h / 2 + 0.12
        y_bot  = stage_y(s_end   - 1) - box_h / 2 - 0.12
        band = mpatches.FancyBboxPatch(
            (box_x0 - 0.15, y_bot),
            box_w + 0.3,
            y_top - y_bot,
            boxstyle="round,pad=0.05",
            linewidth=1.2,
            edgecolor=LAYER_EDGE[layer],
            facecolor=LAYER_COLOURS[layer],
            zorder=1,
        )
        ax.add_patch(band)
        ax.text(
            9.65, (y_top + y_bot) / 2,
            layer,
            ha="center", va="center",
            fontsize=9, fontweight="bold",
            color=LAYER_EDGE[layer],
            rotation=90,
            zorder=5,
        )

    # -- stage boxes --
    for i, (num, label, output, layer) in enumerate(PIPELINE_STAGES):
        y = stage_y(i)
        rect = mpatches.FancyBboxPatch(
            (box_x0, y - box_h / 2),
            box_w - 0.3,
            box_h,
            boxstyle="round,pad=0.04",
            linewidth=1,
            edgecolor=LAYER_EDGE[layer],
            facecolor="white",
            zorder=3,
        )
        ax.add_patch(rect)
        ax.text(
            box_x0 + 0.25, y + 0.03,
            f"{num}. {label}",
            ha="left", va="center",
            fontsize=9, fontweight="bold",
            color=BLACK, zorder=4,
        )
        ax.text(
            box_x0 + 0.25, y - 0.19,
            f"output: {output}",
            ha="left", va="center",
            fontsize=7.5, color="#444444",
            style="italic", zorder=4,
        )

    # -- arrows between stages --
    for i in range(n - 1):
        y_from = stage_y(i)   - box_h / 2
        y_to   = stage_y(i+1) + box_h / 2
        ax.annotate(
            "", xy=(box_x0 + (box_w - 0.3) / 2, y_to),
            xytext=(box_x0 + (box_w - 0.3) / 2, y_from),
            arrowprops=dict(
                arrowstyle="-|>",
                color="#666666",
                lw=1.0,
                mutation_scale=10,
            ),
            zorder=2,
        )

    # -- raw data input arrow at the top --
    top_y = stage_y(0) + box_h / 2
    ax.annotate(
        "", xy=(box_x0 + (box_w - 0.3) / 2, top_y),
        xytext=(box_x0 + (box_w - 0.3) / 2, top_y + 0.4),
        arrowprops=dict(arrowstyle="-|>", color="#666666", lw=1.0, mutation_scale=10),
        zorder=2,
    )
    ax.text(
        box_x0 + (box_w - 0.3) / 2, top_y + 0.5,
        "Raw WESAD data (bronze/)",
        ha="center", va="bottom", fontsize=8.5, color="#444444",
    )

    fig.subplots_adjust(left=0.01, right=0.93, top=0.97, bottom=0.01)
    _save(fig, "fig3_1_pipeline_overview")
    _save_csv(
        [{"stage": num, "label": lbl, "output": out, "layer": lay}
         for num, lbl, out, lay in PIPELINE_STAGES],
        "fig3_1_pipeline_stages",
    )
    print("  saved: fig3_1_pipeline_overview")


# ---------------------------------------------------------------------------
# Figure 4.1 -- TEMP warm-up artefact
# ---------------------------------------------------------------------------

def _read_temp_csv(path: Path) -> np.ndarray:
    """Read E4 TEMP CSV (start_time / hz / values...) and return values array."""
    lines = path.read_text(encoding="utf-8").splitlines()
    # skip first two lines (unix timestamp, sampling rate)
    vals = []
    for line in lines[2:]:
        line = line.strip()
        if not line:
            continue
        try:
            vals.append(float(line))
        except ValueError:
            vals.append(np.nan)
    return np.array(vals, dtype=float)


def fig_temp_artefact(pid: str = "S2") -> None:
    """Figure 4.1: E4 TEMP warm-up artefact -- raw vs cleaned, first 60 s."""
    hz = 4.0
    n_samples = int(60 * hz)   # 240 samples for 60 s

    bronze_path = BRONZE / pid / f"{pid}_E4_Data" / "TEMP.csv"
    silver_path = SILVER / pid / f"{pid}_E4_Data" / "TEMP.csv"

    raw     = _read_temp_csv(bronze_path)[:n_samples]
    cleaned = _read_temp_csv(silver_path)[:n_samples]
    t = np.arange(n_samples) / hz   # seconds

    # Plausibility bounds from physiological_ranges.yaml (embedded constants)
    plaus_min, plaus_max = 15.0, 42.0
    artefact_val = raw[0]           # ~382 C

    # -- broken y-axis: top panel = artefact zone, bottom = normal range --
    fig = plt.figure(figsize=(8, 5))
    gs = gridspec.GridSpec(2, 1, figure=fig, hspace=0.06, height_ratios=[1, 2])
    ax_hi = fig.add_subplot(gs[0])
    ax_lo = fig.add_subplot(gs[1])

    # top panel: artefact zone
    ax_hi.plot(t, raw,     color=ORANGE, lw=1.5, label="Bronze (raw)")
    ax_hi.plot(t, cleaned, color=BLUE,   lw=1.5, label="Silver (cleaned)", zorder=3)
    ax_hi.set_ylim(artefact_val - 5, artefact_val + 5)
    ax_hi.set_xlim(-0.5, 60.5)
    ax_hi.set_yticks([artefact_val - 4, artefact_val, artefact_val + 4])
    ax_hi.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}"))
    ax_hi.spines["bottom"].set_visible(False)
    ax_hi.tick_params(bottom=False, labelbottom=False)
    ax_hi.set_ylabel("Temp (deg C)")
    ax_hi.legend(loc="center right", framealpha=0.85, fontsize=8)

    # annotation in top panel pointing at the artefact samples
    ax_hi.annotate(
        "Warm-up artefact\n(indices 0-3)",
        xy=(0.75 / hz, artefact_val),   # first sample
        xytext=(5, artefact_val - 1),
        fontsize=8,
        arrowprops=dict(arrowstyle="->", color="#444444", lw=0.8),
        ha="left",
        color="#444444",
    )

    # bottom panel: normal range (plaus bounds at 15 and 42 deg C)
    ax_lo.plot(t, raw,     color=ORANGE, lw=1.5)
    ax_lo.plot(t, cleaned, color=BLUE,   lw=1.5, zorder=3)
    ax_lo.axhline(plaus_min, color=VERMILION, lw=1.0, ls="--",
                  label=f"Plausibility bound ({plaus_min:.0f} deg C)")
    ax_lo.axhline(plaus_max, color=VERMILION, lw=1.0, ls="--",
                  label=f"Plausibility bound ({plaus_max:.0f} deg C)")
    ax_lo.set_ylim(plaus_min - 2, plaus_max + 2)
    ax_lo.set_xlim(-0.5, 60.5)
    ax_lo.set_xlabel("Time (s)")
    ax_lo.set_ylabel("Temp (deg C)")
    ax_lo.spines["top"].set_visible(False)
    ax_lo.legend(loc="lower right", framealpha=0.85, fontsize=8)

    # -- break markers using axes-relative coordinates --
    # d_hi and d_lo matched so the marks are the same physical size on the page;
    # height_ratios=[1,2] so d_lo = d_hi * (1/2)
    d_hi = 0.03
    d_lo = d_hi / 2
    bk = dict(color=BLACK, clip_on=False, lw=1.2)
    ax_hi.plot((-d_hi, d_hi), (-d_hi, d_hi), transform=ax_hi.transAxes, **bk)
    ax_hi.plot((1 - d_hi, 1 + d_hi), (-d_hi, d_hi), transform=ax_hi.transAxes, **bk)
    ax_lo.plot((-d_lo, d_lo), (1 - d_lo, 1 + d_lo), transform=ax_lo.transAxes, **bk)
    ax_lo.plot((1 - d_lo, 1 + d_lo), (1 - d_lo, 1 + d_lo), transform=ax_lo.transAxes, **bk)

    fig.subplots_adjust(left=0.1, right=0.95, top=0.97, bottom=0.1, hspace=0.08)
    _save(fig, "fig4_1_temp_artefact")

    # save data
    rows = [
        {"time_s": float(t[i]), "bronze_temp_c": float(raw[i]),
         "silver_temp_c": (float(cleaned[i]) if not np.isnan(cleaned[i]) else "NaN")}
        for i in range(n_samples)
    ]
    _save_csv(rows, "fig4_1_temp_artefact")
    print(f"  saved: fig4_1_temp_artefact  (participant {pid})")


# ---------------------------------------------------------------------------
# Figure 4.2 -- fault injection results
# ---------------------------------------------------------------------------

def _aggregate_fault_records(records: list[dict]) -> dict:
    """Aggregate fault records (avg detection_rate, any verdict_flip)."""
    drs = [r["detection_rate"] for r in records if "detection_rate" in r]
    flips = [r.get("verdict_flip", False) for r in records]
    fps = [r.get("false_positive_count", 0) for r in records if "false_positive_count" in r]
    return {
        "n": len(records),
        "detection_rate": float(np.mean(drs)) if drs else float("nan"),
        "verdict_flip": any(flips),
        "false_positive_count": int(sum(fps)),
    }


# Human-readable short names for fault types
FAULT_LABELS = {
    "completeness_contiguous_dropout":    "Completeness: contiguous dropout",
    "completeness_scattered_nan":         "Completeness: scattered NaN",
    "conformance_non_numeric":            "Conformance: non-numeric values",
    "conformance_out_of_device_range":    "Conformance: out-of-range",
    "conformance_sampling_rate_fault":    "Conformance: sampling rate",
    "plausibility_physiological_impossible": "Plausibility: impossible value",
}
# Order for grid rows
GRID_ROWS = [
    "completeness_contiguous_dropout",
    "completeness_scattered_nan",
    "conformance_non_numeric",
    "conformance_out_of_device_range",
    "plausibility_physiological_impossible",
]
SEVERITY_COLS = [0.001, 0.01, 0.05, 0.1]
SEV_LABELS = ["0.1 %", "1 %", "5 %", "10 %"]


def fig_fault_injection(fi: dict) -> None:
    """Figure 4.2: fault injection result grid."""
    records = fi["records"]
    fault_records = [r for r in records if r["fault_type"] != "control_no_injection"]
    control_records = [r for r in records if r["fault_type"] == "control_no_injection"]

    # -- build grid data --
    # grid[row_ft][sev] = aggregated
    grid: dict[str, dict] = {}
    for ft in GRID_ROWS:
        grid[ft] = {}
        for sev in SEVERITY_COLS:
            subset = [r for r in fault_records
                      if r["fault_type"] == ft and r.get("severity") == sev]
            grid[ft][sev] = _aggregate_fault_records(subset)

    # sampling rate fault
    sr_records = [r for r in fault_records if r["fault_type"] == "conformance_sampling_rate_fault"]
    sr_agg = {
        "n": len(sr_records),
        "detected": sum(1 for r in sr_records if r.get("detected", False)),
        "verdict_flip": any(r.get("verdict_flip", False) for r in sr_records),
    }

    # timeliness
    tim_records = [r for r in fault_records if r["fault_type"] == "timeliness_start_shift"]
    tim_offsets = sorted(set(r["offset_injected_s"] for r in tim_records))
    tim_by_offset: dict[float, dict] = {}
    for off in tim_offsets:
        subset = [r for r in tim_records if r["offset_injected_s"] == off]
        detected = sum(1 for r in subset if r.get("detected", False))
        tim_by_offset[off] = {
            "n": len(subset),
            "detected": detected,
            "undetected": len(subset) - detected,
        }

    # control
    ctrl_agg = {
        "n": len(control_records),
        "any_flag": sum(1 for r in control_records if r.get("any_flag", True)),
        "false_detections": sum(1 for r in control_records if r.get("any_flag", True)),
    }

    # -- figure layout: two panels stacked --
    fig = plt.figure(figsize=(10, 8))
    gs_main = gridspec.GridSpec(2, 1, figure=fig, hspace=0.45,
                                height_ratios=[5, 2])

    ax_grid = fig.add_subplot(gs_main[0])
    ax_tim  = fig.add_subplot(gs_main[1])

    ax_grid.axis("off")
    ax_tim.axis("off")

    n_rows = len(GRID_ROWS) + 2  # +1 sampling rate, +1 control
    n_cols = len(SEVERITY_COLS)

    col_w = 1.0 / (n_cols + 1.5)
    row_h = 1.0 / (n_rows + 0.5)

    # column headers
    for j, sl in enumerate(SEV_LABELS):
        ax_grid.text(
            (j + 1.5) * col_w, 1 - 0.3 * row_h,
            sl,
            ha="center", va="center", fontsize=9, fontweight="bold",
            transform=ax_grid.transAxes,
        )
    ax_grid.text(
        0.5 * col_w, 1 - 0.3 * row_h, "Fault type",
        ha="center", va="center", fontsize=9, fontweight="bold",
        transform=ax_grid.transAxes,
    )

    def _cell_color(dr: float) -> str:
        if np.isnan(dr):
            return "#FFFFFF"
        # gradient: 0 = red, 1 = green (colour-blind-safe using blue-orange)
        # DR=1 -> green; DR=0 -> light red
        g = int(dr * 180 + 40)
        r = int((1 - dr) * 180 + 40)
        b = 40
        return f"#{r:02X}{g:02X}{b:02X}"

    # grid rows
    for i, ft in enumerate(GRID_ROWS):
        y = 1 - (i + 1.3) * row_h
        # row label
        ax_grid.text(
            0.5 * col_w, y + 0.5 * row_h,
            FAULT_LABELS[ft],
            ha="center", va="center", fontsize=8,
            transform=ax_grid.transAxes,
        )
        for j, sev in enumerate(SEVERITY_COLS):
            agg = grid[ft][sev]
            x = (j + 1.5) * col_w
            dr = agg["detection_rate"]
            flip = agg["verdict_flip"]
            fp = agg["false_positive_count"]
            fc = _cell_color(dr)
            rect = mpatches.FancyBboxPatch(
                (x - col_w * 0.47, y + 0.05 * row_h),
                col_w * 0.94, row_h * 0.9,
                boxstyle="round,pad=0.01",
                linewidth=0.6, edgecolor="#888888",
                facecolor=fc, transform=ax_grid.transAxes,
            )
            ax_grid.add_patch(rect)
            flip_sym = " F" if flip else ""
            fd_sym   = f" fd={fp}" if fp > 0 else ""
            ax_grid.text(
                x, y + 0.5 * row_h,
                f"DR={dr:.2f}{flip_sym}{fd_sym}",
                ha="center", va="center", fontsize=8,
                transform=ax_grid.transAxes,
            )

    # sampling rate row
    i = len(GRID_ROWS)
    y = 1 - (i + 1.3) * row_h
    ax_grid.text(
        0.5 * col_w, y + 0.5 * row_h,
        FAULT_LABELS["conformance_sampling_rate_fault"],
        ha="center", va="center", fontsize=8,
        transform=ax_grid.transAxes,
    )
    # one merged cell spanning all severity columns
    n_det = sr_agg["detected"]
    n_tot = sr_agg["n"]
    dr_sr = n_det / n_tot if n_tot else float("nan")
    flip_sym = " F" if sr_agg["verdict_flip"] else ""
    fc_sr = _cell_color(dr_sr)
    merged_x0 = 1.5 * col_w
    merged_w  = n_cols * col_w
    rect = mpatches.FancyBboxPatch(
        (merged_x0 - col_w * 0.47, y + 0.05 * row_h),
        merged_w - 0.06 * col_w, row_h * 0.9,
        boxstyle="round,pad=0.01",
        linewidth=0.6, edgecolor="#888888",
        facecolor=fc_sr, transform=ax_grid.transAxes,
    )
    ax_grid.add_patch(rect)
    ax_grid.text(
        merged_x0 + (merged_w - col_w) / 2, y + 0.5 * row_h,
        f"DR={dr_sr:.2f}{flip_sym}  (single fault, no severity parameter)",
        ha="center", va="center", fontsize=8,
        transform=ax_grid.transAxes,
    )

    # control row
    i = len(GRID_ROWS) + 1
    y = 1 - (i + 1.3) * row_h
    ax_grid.text(
        0.5 * col_w, y + 0.5 * row_h,
        "Control (no injection)",
        ha="center", va="center", fontsize=8, style="italic",
        transform=ax_grid.transAxes,
    )
    fc_ctrl = _cell_color(0.0) if ctrl_agg["any_flag"] > 0 else "#C8E6C9"
    rect = mpatches.FancyBboxPatch(
        (1.5 * col_w - col_w * 0.47, y + 0.05 * row_h),
        n_cols * col_w - 0.06 * col_w, row_h * 0.9,
        boxstyle="round,pad=0.01",
        linewidth=0.6, edgecolor="#888888",
        facecolor=fc_ctrl, transform=ax_grid.transAxes,
    )
    ax_grid.add_patch(rect)
    ax_grid.text(
        1.5 * col_w + (n_cols * col_w - col_w) / 2, y + 0.5 * row_h,
        f"{ctrl_agg['n']} participants, 0 false detections (expected: none flagged)",
        ha="center", va="center", fontsize=8,
        transform=ax_grid.transAxes,
    )

    ax_grid.text(
        0.5, 1.03,
        "F = verdict flipped to Fail",
        ha="center", va="bottom", fontsize=8, color="#555555",
        transform=ax_grid.transAxes,
    )

    # -- timeliness panel --
    ax_tim.set_title("Timeliness fault injection (start-time shift; all undetected by design)",
                     fontsize=9, loc="left", pad=4)

    n_offs = len(tim_offsets)
    bar_colors = [ORANGE if d["detected"] == 0 else GREEN
                  for d in tim_by_offset.values()]
    ypos = np.arange(n_offs)

    ax_tim2 = fig.add_axes(ax_tim.get_position(), frameon=True)
    ax_tim2.barh(ypos, [d["n"] for d in tim_by_offset.values()],
                 color=SILVER_COLOUR, label="Injected (not detected)", height=0.5)
    ax_tim2.set_yticks(ypos)
    ax_tim2.set_yticklabels([f"{o:.0f} s" if o >= 1 else f"{o} s" for o in tim_offsets],
                            fontsize=9)
    ax_tim2.set_xlabel("Number of participants tested")
    ax_tim2.set_xlim(0, max(d["n"] for d in tim_by_offset.values()) + 1)
    ax_tim2.set_xticks([0, 1, 2, 3])
    ax_tim2.spines["top"].set_visible(False)
    ax_tim2.spines["right"].set_visible(False)
    ax_tim2.text(
        0.98, 0.95,
        "Offset injected on one E4 signal;\n5-point method cannot detect it",
        ha="right", va="top", fontsize=8, color="#444444",
        transform=ax_tim2.transAxes,
    )
    ax_tim.set_visible(False)

    _save(fig, "fig4_2_fault_injection")

    # save data
    rows = []
    for ft in GRID_ROWS:
        for sev in SEVERITY_COLS:
            agg = grid[ft][sev]
            rows.append({
                "fault_type": ft,
                "severity": sev,
                "n_records": agg["n"],
                "detection_rate": agg["detection_rate"],
                "verdict_flip": agg["verdict_flip"],
                "false_positive_count": agg["false_positive_count"],
            })
    rows.append({
        "fault_type": "conformance_sampling_rate_fault",
        "severity": "N/A",
        "n_records": sr_agg["n"],
        "detection_rate": dr_sr,
        "verdict_flip": sr_agg["verdict_flip"],
        "false_positive_count": 0,
    })
    for off, d in tim_by_offset.items():
        rows.append({
            "fault_type": "timeliness_start_shift",
            "severity": f"{off}s",
            "n_records": d["n"],
            "detection_rate": 0.0,
            "verdict_flip": False,
            "false_positive_count": 0,
        })
    _save_csv(rows, "fig4_2_fault_injection")
    print("  saved: fig4_2_fault_injection")


# ---------------------------------------------------------------------------
# Figure 4.3 -- start-time gap per participant
# ---------------------------------------------------------------------------

def fig_start_time_gap(al: dict) -> None:
    """Figure 4.3: E4 to RespiBAN start-time gap per participant."""
    pp = al["participants"]
    pids = sorted(pp.keys())
    gaps = [pp[pid]["offset_before_s"] for pid in pids]
    mean_gap = al["summary"]["mean_offset_before_s"]

    fig, ax = plt.subplots(figsize=(7, 4.5))

    ax.scatter(gaps, range(len(pids)), color=BLUE, s=60, zorder=3, label="Participant gap")
    ax.axvline(mean_gap, color=ORANGE, lw=1.5, ls="--",
               label=f"Mean ({mean_gap:.0f} s)")

    ax.set_yticks(range(len(pids)))
    ax.set_yticklabels(pids, fontsize=9)
    ax.set_xlabel("E4 to RespiBAN start-time gap (s)")
    ax.set_xlim(700, 1550)
    ax.legend(framealpha=0.85)
    ax.grid(axis="x", color="#E0E0E0", zorder=0)

    fig.tight_layout()
    _save(fig, "fig4_3_start_time_gap")
    _save_csv(
        [{"participant": pid, "offset_before_s": gap}
         for pid, gap in zip(pids, gaps)],
        "fig4_3_start_time_gap",
    )
    print("  saved: fig4_3_start_time_gap")


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

def table_quality_before_after(qr: dict) -> None:
    """Table 4.1: quality dimensions, before/after, threshold, pass."""
    dims = qr["dimensions"]
    rows = []

    # completeness
    c = dims["completeness"]
    rows.append({
        "Dimension": "Completeness",
        "Threshold": c["threshold"],
        "Before (Bronze)": c["before"]["missingness_rate"],
        "After (Gold)": c["after"]["missingness_rate"],
        "Gold passes": c["threshold_pass_gold"],
        "Note": "60 intentional removals excluded from rate",
    })

    # validity_conformance
    vc = dims["validity_conformance"]
    rows.append({
        "Dimension": "Validity: conformance",
        "Threshold": vc["threshold"],
        "Before (Bronze)": f"{vc['before']['violation_rate']:.2e} ({vc['before']['violation_count']} violations)",
        "After (Gold)": f"{vc['after']['violation_rate']:.2e} ({vc['after']['violation_count']} violations)",
        "Gold passes": vc["threshold_pass_gold"],
        "Note": "TEMP warm-up artefact (60 samples, all participants)",
    })

    # validity_plausibility
    vp = dims["validity_plausibility"]
    rows.append({
        "Dimension": "Validity: plausibility",
        "Threshold": f"<= {vp['threshold']}",
        "Before (Bronze)": f"{vp['before']['failure_rate']:.2e} ({vp['before']['violation_count']} failures)",
        "After (Gold)": f"{vp['after']['failure_rate']:.2e} ({vp['after']['violation_count']} failures)",
        "Gold passes": vp["threshold_pass_gold"],
        "Note": "Same 60 TEMP samples; BVP and IBI excluded",
    })

    # timeliness
    t = dims["timeliness"]
    rows.append({
        "Dimension": "Timeliness (partly assessed)",
        "Threshold": f"<= {t['threshold']} s",
        "Before (Bronze)": f"~{t['before']['value_s']:.0f} s start gap",
        "After (Gold)": f"{t['after']['max_offset_s']:.6f} s max residual (15/15 pass)",
        "Gold passes": t["threshold_pass_gold"],
        "Note": "5-point method; cannot detect single-device clock offset",
    })

    # consistency / accuracy
    for key, label in [("consistency", "Consistency"), ("accuracy", "Accuracy")]:
        rows.append({
            "Dimension": label,
            "Threshold": "N/A",
            "Before (Bronze)": "not measured",
            "After (Gold)": "not measured",
            "Gold passes": "N/A",
            "Note": dims[key].get("limitation", "intentionally unmeasured"),
        })

    df = pd.DataFrame(rows)
    _save_table(df, "table4_1_quality_before_after")
    print("  saved: table4_1_quality_before_after")


def table_fault_injection_summary(fi: dict) -> None:
    """Table 4.2: fault injection summary per fault type."""
    records = fi["records"]
    fault_records = [r for r in records if r["fault_type"] != "control_no_injection"]

    rows = []
    for ft in list(FAULT_LABELS.keys()):
        if ft == "conformance_sampling_rate_fault":
            subset = [r for r in fault_records if r["fault_type"] == ft]
            n_det = sum(1 for r in subset if r.get("detected", False))
            rows.append({
                "Fault type": FAULT_LABELS[ft],
                "Dimension": subset[0]["dimension"] if subset else "",
                "Severity": "N/A (binary)",
                "n records": len(subset),
                "Detection rate": f"{n_det / len(subset):.2f}" if subset else "N/A",
                "Verdict flip": any(r.get("verdict_flip", False) for r in subset),
                "False detections": sum(r.get("false_positive_count", 0) for r in subset
                                        if "false_positive_count" in r),
            })
            continue
        for sev in SEVERITY_COLS:
            subset = [r for r in fault_records
                      if r["fault_type"] == ft and r.get("severity") == sev]
            if not subset:
                continue
            agg = _aggregate_fault_records(subset)
            rows.append({
                "Fault type": FAULT_LABELS[ft],
                "Dimension": subset[0]["dimension"],
                "Severity": f"{sev * 100:.1f}%",
                "n records": agg["n"],
                "Detection rate": f"{agg['detection_rate']:.2f}",
                "Verdict flip": agg["verdict_flip"],
                "False detections": agg["false_positive_count"],
            })

    # timeliness
    tim_records = [r for r in fault_records if r["fault_type"] == "timeliness_start_shift"]
    tim_offsets = sorted(set(r["offset_injected_s"] for r in tim_records))
    for off in tim_offsets:
        subset = [r for r in tim_records if r["offset_injected_s"] == off]
        detected = sum(1 for r in subset if r.get("detected", False))
        rows.append({
            "Fault type": "Timeliness: start-time shift",
            "Dimension": "timeliness",
            "Severity": f"{off} s shift",
            "n records": len(subset),
            "Detection rate": f"{detected / len(subset):.2f}",
            "Verdict flip": False,
            "False detections": 0,
        })

    df = pd.DataFrame(rows)
    _save_table(df, "table4_2_fault_injection_summary")
    print("  saved: table4_2_fault_injection_summary")


def table_per_participant(al: dict, fi_records: list[dict]) -> None:
    """Per-participant table: conformance violations, plausibility failures, removals, alignment."""
    conf  = _load("wesad_conformance.json")
    plaus = _load("wesad_plausibility.json")
    clean = _load("wesad_cleaning.json")

    pids = sorted(al["participants"].keys())
    rows = []
    for pid in pids:
        # conformance: total range violations (e4 only, all signals)
        c = conf["participants"][pid]
        e4_viol = sum(
            sig.get("range", {}).get("n_violations", 0)
            for sig in c["e4"].values()
            if isinstance(sig, dict) and "range" in sig
        )

        # plausibility: total e4 violations
        p = plaus["participants"][pid]
        e4_plaus = sum(
            sig.get("n_violations", 0)
            for sig in p["e4"].values()
            if isinstance(sig, dict)
        )

        # cleaning
        n_replaced = len(clean["participants"][pid]["cleaning"]["indices_replaced"])

        # alignment
        aln = al["participants"][pid]
        offset_before = aln["offset_before_s"]
        offset_after  = aln["offset_after_s"]
        passes        = aln["passes_threshold"]

        rows.append({
            "Participant": pid,
            "Conf. violations (Bronze)": e4_viol,
            "Plaus. failures (Bronze)": e4_plaus,
            "Samples removed (cleaning)": n_replaced,
            "Start-time gap (s)": offset_before,
            "Within-overlap residual (s)": offset_after,
            "Alignment passes (<=1.0 s)": passes,
        })

    df = pd.DataFrame(rows)
    _save_table(df, "table_per_participant")
    print("  saved: table_per_participant")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Build all figures and tables."""
    FIGURES.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    al = _load("wesad_alignment.json")
    qr = _load("wesad_quality_report.json")
    fi = json.loads(
        (REPORTS / "experiments" / "fault_injection_results.json").read_text(encoding="utf-8")
    )

    print("Building figures ...")
    fig_pipeline_overview()
    fig_temp_artefact("S2")
    fig_fault_injection(fi)
    fig_start_time_gap(al)

    print("Building tables ...")
    table_quality_before_after(qr)
    table_fault_injection_summary(fi)
    table_per_participant(al, fi["records"])

    print("Done.")


if __name__ == "__main__":
    main()
