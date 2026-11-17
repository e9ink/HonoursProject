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

BRONZE_COLOUR      = "#CD7F32"
SILVER_COLOUR      = "#A8A9AD"
SILVER_TEXT_COLOUR = "#505052"   # darker for legibility on the gray band
GOLD_COLOUR        = "#CFB53B"

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

# Figure 4.2a cell colours: muted, colour-blind-safe
# verdict_flip=True (detected + verdict failed): muted amber
CELL_FLIP    = "#F5C07A"
# verdict_flip=False (detected + verdict still passed): muted sky blue
CELL_NO_FLIP = "#A8CCE0"
# not detected: very light grey
CELL_MISS    = "#F0F0F0"

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


def _pid_key(pid: str) -> int:
    """Sort key for participant IDs: S2, S3 ... S17 -> 2, 3 ... 17."""
    return int(pid[1:])


# ---------------------------------------------------------------------------
# Figure 3.1 -- pipeline overview
# ---------------------------------------------------------------------------

# Each entry: (num_or_None, label, short_output, layer, is_source)
# is_source=True marks the read-only data input node (no stage number, no output).
PIPELINE_ENTRIES = [
    (None, "Raw WESAD data (read-only)", "",                             "Bronze", True),
    (1,    "Profiling",                  "wesad_baseline.json",          "Bronze", False),
    (2,    "Conformance check",          "wesad_conformance.json",       "Silver", False),
    (3,    "Completeness check",         "wesad_completeness.json",      "Silver", False),
    (4,    "Plausibility check",         "wesad_plausibility.json",      "Silver", False),
    (5,    "Temporal alignment",         "wesad_alignment.json",         "Silver", False),
    (6,    "Silver cleaning",            "wesad_cleaning.json",          "Silver", False),
    (7,    "Post-cleaning",              "wesad_*_post_cleaning.json",   "Silver", False),
    (8,    "Governance",                 "wesad_lineage.json",           "Gold",   False),
    (9,    "Quality report",             "wesad_quality_report.json",    "Gold",   False),
    (10,   "Gold manifest",              "wesad_manifest.json",          "Gold",   False),
]

# Layer spans: (name, first_entry_index, last_entry_index) -- 0-indexed into PIPELINE_ENTRIES
LAYER_SPANS = [
    ("Bronze", 0, 1),
    ("Silver", 2, 7),
    ("Gold",   8, 10),
]


def fig_pipeline_overview() -> None:
    """Figure 3.1: pipeline stages diagram, Bronze / Silver / Gold layers."""
    n = len(PIPELINE_ENTRIES)
    gap   = 0.70   # vertical step per entry
    box_h = 0.54
    box_x0 = 0.4
    box_w  = 7.8   # narrower than v1

    fig_h = n * gap + 0.4
    fig, ax = plt.subplots(figsize=(7, fig_h))
    ax.set_xlim(0, 10)
    ax.set_ylim(-0.5, n * gap + 0.1)
    ax.axis("off")

    def entry_y(i: int) -> float:
        """y-centre for entry i (0-indexed, top-to-bottom)."""
        return (n - 1 - i) * gap

    # -- layer background bands --
    for layer, i_start, i_end in LAYER_SPANS:
        y_top = entry_y(i_start) + box_h / 2 + 0.10
        y_bot = entry_y(i_end)   - box_h / 2 - 0.10
        band = mpatches.FancyBboxPatch(
            (box_x0 - 0.12, y_bot),
            box_w + 0.24,
            y_top - y_bot,
            boxstyle="round,pad=0.04",
            linewidth=1.2,
            edgecolor=LAYER_EDGE[layer],
            facecolor=LAYER_COLOURS[layer],
            zorder=1,
        )
        ax.add_patch(band)
        text_colour = SILVER_TEXT_COLOUR if layer == "Silver" else LAYER_EDGE[layer]
        ax.text(
            box_x0 + box_w + 0.42, (y_top + y_bot) / 2,
            layer,
            ha="center", va="center",
            fontsize=9, fontweight="bold",
            color=text_colour,
            rotation=90,
            zorder=5,
        )

    # -- entry boxes and text --
    for i, (num, label, output, layer, is_source) in enumerate(PIPELINE_ENTRIES):
        y = entry_y(i)
        ls = "dashed" if is_source else "solid"
        fc = LAYER_COLOURS[layer] if is_source else "white"
        rect = mpatches.FancyBboxPatch(
            (box_x0, y - box_h / 2),
            box_w,
            box_h,
            boxstyle="round,pad=0.04",
            linewidth=1,
            edgecolor=LAYER_EDGE[layer],
            linestyle=ls,
            facecolor=fc,
            zorder=3,
        )
        ax.add_patch(rect)
        if is_source:
            ax.text(
                box_x0 + box_w / 2, y,
                label,
                ha="center", va="center",
                fontsize=9, style="italic",
                color="#555555", zorder=4,
            )
        else:
            prefix = f"{num}. " if num is not None else ""
            ax.text(
                box_x0 + 0.22, y + 0.03,
                f"{prefix}{label}",
                ha="left", va="center",
                fontsize=8.5, fontweight="bold",
                color=BLACK, zorder=4,
            )
            ax.text(
                box_x0 + 0.22, y - 0.18,
                f"output: {output}",
                ha="left", va="center",
                fontsize=7, color="#444444",
                style="italic", zorder=4,
            )

    # -- arrows between consecutive entries --
    mid_x = box_x0 + box_w / 2
    for i in range(n - 1):
        y_from = entry_y(i)   - box_h / 2
        y_to   = entry_y(i+1) + box_h / 2
        ax.annotate(
            "", xy=(mid_x, y_to),
            xytext=(mid_x, y_from),
            arrowprops=dict(
                arrowstyle="-|>",
                color="#666666",
                lw=1.0,
                mutation_scale=10,
            ),
            zorder=2,
        )

    fig.subplots_adjust(left=0.01, right=0.90, top=0.99, bottom=0.01)
    _save(fig, "fig3_1_pipeline_overview")
    _save_csv(
        [{"stage": num if num is not None else "data", "label": lbl, "output": out, "layer": lay}
         for num, lbl, out, lay, _ in PIPELINE_ENTRIES],
        "fig3_1_pipeline_stages",
    )
    print("  saved: fig3_1_pipeline_overview")


# ---------------------------------------------------------------------------
# Figure 4.1 -- TEMP warm-up artefact
# ---------------------------------------------------------------------------

def _read_temp_csv(path: Path) -> np.ndarray:
    """Read E4 TEMP CSV (start_time / hz / values...) and return values array."""
    lines = path.read_text(encoding="utf-8").splitlines()
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

    plaus_min, plaus_max = 15.0, 42.0
    artefact_val = raw[0]           # ~382 degC

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
    ax_hi.legend(loc="center right", framealpha=0.85, fontsize=8)

    # annotation pointing at the artefact samples in top panel
    ax_hi.annotate(
        "Warm-up artefact\n(first 4 samples, about 382 °C)",
        xy=(0.75 / hz, artefact_val),
        xytext=(6, artefact_val - 2),
        fontsize=8,
        arrowprops=dict(arrowstyle="->", color="#444444", lw=0.8),
        ha="left",
        color="#444444",
    )

    # bottom panel: normal range (plausibility bounds at 15 and 42 degC)
    ax_lo.plot(t, raw,     color=ORANGE, lw=1.5)
    ax_lo.plot(t, cleaned, color=BLUE,   lw=1.5, zorder=3)
    ax_lo.axhline(plaus_min, color=VERMILION, lw=1.0, ls="--",
                  label=f"Plausibility bound ({plaus_min:.0f} °C)")
    ax_lo.axhline(plaus_max, color=VERMILION, lw=1.0, ls="--",
                  label=f"Plausibility bound ({plaus_max:.0f} °C)")
    ax_lo.set_ylim(plaus_min - 2, plaus_max + 2)
    ax_lo.set_xlim(-0.5, 60.5)
    ax_lo.set_xlabel("Time (s)")
    ax_lo.spines["top"].set_visible(False)
    # bounds legend in the empty middle-right area of the lower panel
    ax_lo.legend(loc="center right", framealpha=0.85, fontsize=8)

    # -- shared y-axis label --
    ax_hi.set_ylabel("")
    ax_lo.set_ylabel("")
    fig.text(
        0.03, 0.5,
        "Skin temperature (°C)",
        va="center", ha="center",
        rotation="vertical",
        fontsize=10,
    )

    # -- break marks: use transAxes, clip_on=True (default) so nothing draws outside --
    # height_ratios=[1, 2] -> bottom panel is physically 2x taller.
    # To get equal physical mark size: d_lo = d_hi * (1/2).
    d_hi = 0.05   # axes fraction for top (shorter) panel
    d_lo = 0.025  # axes fraction for bottom (taller) panel
    bk = dict(color=BLACK, lw=1.2)
    # bottom edge of top panel (break line, marks straddle y=0 in transAxes)
    ax_hi.plot((-d_hi, d_hi), (-d_hi, d_hi), transform=ax_hi.transAxes, **bk)
    ax_hi.plot((1 - d_hi, 1 + d_hi), (-d_hi, d_hi), transform=ax_hi.transAxes, **bk)
    # top edge of bottom panel (break line, marks straddle y=1 in transAxes)
    ax_lo.plot((-d_lo, d_lo), (1 - d_lo, 1 + d_lo), transform=ax_lo.transAxes, **bk)
    ax_lo.plot((1 - d_lo, 1 + d_lo), (1 - d_lo, 1 + d_lo), transform=ax_lo.transAxes, **bk)

    fig.subplots_adjust(left=0.12, right=0.95, top=0.97, bottom=0.10, hspace=0.08)
    _save(fig, "fig4_1_temp_artefact")

    rows = [
        {"time_s": float(t[i]), "bronze_temp_c": float(raw[i]),
         "silver_temp_c": (float(cleaned[i]) if not np.isnan(cleaned[i]) else "NaN")}
        for i in range(n_samples)
    ]
    _save_csv(rows, "fig4_1_temp_artefact")
    print(f"  saved: fig4_1_temp_artefact  (participant {pid})")


# ---------------------------------------------------------------------------
# Figure 4.2a -- detection grid by fault type and severity
# ---------------------------------------------------------------------------

GRID_FAULT_LABELS = {
    "completeness_scattered_nan":         "Completeness: scattered\nmissing values",
    "completeness_contiguous_dropout":    "Completeness: contiguous\ndropout",
    "conformance_non_numeric":            "Conformance: non-numeric\nvalues",
    "conformance_out_of_device_range":    "Conformance: out-of-range\nECG",
    "plausibility_physiological_impossible": "Plausibility: impossible\nvalues",
}

GRID_ROWS = [
    "completeness_scattered_nan",
    "completeness_contiguous_dropout",
    "conformance_non_numeric",
    "conformance_out_of_device_range",
    "plausibility_physiological_impossible",
]
SEVERITY_COLS   = [0.001, 0.01, 0.05, 0.1]
SEV_LABELS      = ["0.1 %", "1 %", "5 %", "10 %"]


def _aggregate_fault_records(records: list[dict]) -> dict:
    """Aggregate count-based fault records (avg detection_rate, any verdict_flip)."""
    drs   = [r["detection_rate"] for r in records if "detection_rate" in r]
    flips = [r.get("verdict_flip", False) for r in records]
    return {
        "n":              len(records),
        "detection_rate": float(np.mean(drs)) if drs else float("nan"),
        "verdict_flip":   any(flips),
    }


def fig_detection_grid(fi: dict) -> None:
    """Figure 4.2a: fault detection rate grid with verdict-flip colouring."""
    records = fi["records"]
    fault_records = [r for r in records if r["fault_type"] != "control_no_injection"]

    # build grid
    grid: dict[str, dict] = {}
    for ft in GRID_ROWS:
        grid[ft] = {}
        for sev in SEVERITY_COLS:
            subset = [r for r in fault_records
                      if r["fault_type"] == ft and r.get("severity") == sev]
            grid[ft][sev] = _aggregate_fault_records(subset)

    # sampling rate aggregates for the note
    sr_records = [r for r in fault_records if r["fault_type"] == "conformance_sampling_rate_fault"]
    sr_det   = sum(1 for r in sr_records if r.get("detected", False))
    sr_total = len(sr_records)
    sr_flip  = any(r.get("verdict_flip", False) for r in sr_records)

    ctrl_records = [r for r in records if r["fault_type"] == "control_no_injection"]
    ctrl_total   = len(ctrl_records)
    ctrl_flags   = sum(1 for r in ctrl_records if r.get("any_flag", False))

    # -- figure layout --
    n_rows = len(GRID_ROWS)
    n_cols = len(SEVERITY_COLS)

    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # column proportions: label_frac takes the left portion
    label_frac = 0.38
    data_frac  = 1.0 - label_frac
    col_w = data_frac / n_cols

    # vertical allocation:
    #   header_h   = column-header row
    #   legend_h   = colour-swatch legend row
    #   note_h     = note text at very bottom
    #   remainder  = n_rows data rows
    header_h = 0.10
    legend_h = 0.10
    note_h   = 0.07
    row_h    = (1.0 - header_h - legend_h - note_h) / n_rows

    def row_y(i: int) -> float:
        """Bottom y of data row i (0 = top row)."""
        return 1.0 - header_h - (i + 1) * row_h

    # -- column headers --
    for j, sl in enumerate(SEV_LABELS):
        cx = label_frac + (j + 0.5) * col_w
        ax.text(cx, 1.0 - header_h * 0.5, sl,
                ha="center", va="center", fontsize=9, fontweight="bold",
                transform=ax.transAxes)
    ax.text(label_frac * 0.5, 1.0 - header_h * 0.5, "Fault type",
            ha="center", va="center", fontsize=9, fontweight="bold",
            transform=ax.transAxes)

    # -- data cells and row labels --
    for i, ft in enumerate(GRID_ROWS):
        y = row_y(i)
        # row label (left-aligned, centred vertically in row)
        ax.text(0.01, y + row_h * 0.5,
                GRID_FAULT_LABELS[ft],
                ha="left", va="center", fontsize=8.5,
                transform=ax.transAxes, linespacing=1.3)
        # cell separator line under row
        ax.plot([0, 1], [y, y], color="#CCCCCC", lw=0.5, transform=ax.transAxes)

        for j, sev in enumerate(SEVERITY_COLS):
            agg = grid[ft][sev]
            dr   = agg["detection_rate"]
            flip = agg["verdict_flip"]

            if np.isnan(dr) or dr == 0.0:
                fc = CELL_MISS
            elif flip:
                fc = CELL_FLIP
            else:
                fc = CELL_NO_FLIP

            cell_x = label_frac + j * col_w
            pad = 0.004
            rect = mpatches.FancyBboxPatch(
                (cell_x + pad, y + pad),
                col_w - 2 * pad, row_h - 2 * pad,
                boxstyle="round,pad=0.005",
                linewidth=0.5, edgecolor="#AAAAAA",
                facecolor=fc, transform=ax.transAxes, zorder=2,
            )
            ax.add_patch(rect)

            pct = f"{dr * 100:.0f}%" if not np.isnan(dr) else "--"
            ax.text(cell_x + col_w * 0.5, y + row_h * 0.5, pct,
                    ha="center", va="center", fontsize=9,
                    transform=ax.transAxes, zorder=3)

    # top border under column headers
    ax.plot([0, 1], [1.0 - header_h, 1.0 - header_h],
            color="#888888", lw=1.0, transform=ax.transAxes)
    # bottom border of last row
    ax.plot([0, 1], [row_y(n_rows - 1), row_y(n_rows - 1)],
            color="#888888", lw=1.0, transform=ax.transAxes)
    # vertical divider between labels and cells (ends at bottom of last data row)
    ax.plot([label_frac, label_frac], [note_h + legend_h, 1.0],
            color="#888888", lw=0.8, transform=ax.transAxes)

    # -- legend row: sits between data rows and note --
    swatch_y = note_h + legend_h * 0.25
    swatch_h = legend_h * 0.50
    swatch_w = 0.025
    legend_x = 0.01   # start from the left edge
    for fc, txt in [
        (CELL_FLIP,    "Detected -- verdict failed"),
        (CELL_NO_FLIP, "Detected -- verdict still passed"),
    ]:
        sw = mpatches.FancyBboxPatch(
            (legend_x, swatch_y),
            swatch_w, swatch_h,
            boxstyle="round,pad=0.003",
            linewidth=0.5, edgecolor="#AAAAAA",
            facecolor=fc, transform=ax.transAxes, zorder=2,
        )
        ax.add_patch(sw)
        ax.text(legend_x + swatch_w + 0.01, swatch_y + swatch_h * 0.5,
                txt, ha="left", va="center", fontsize=8,
                transform=ax.transAxes)
        legend_x += swatch_w + 0.01 + len(txt) * 0.011 + 0.03

    # -- note at the very bottom --
    sr_flip_txt = "verdict failed" if sr_flip else "verdict still passed"
    note = (
        f"Sampling-rate fault: detected for {sr_det} of {sr_total} participants, {sr_flip_txt}.  "
        f"Control: {ctrl_flags} flags across {ctrl_total} participants."
    )
    ax.text(0.0, note_h * 0.45, note,
            ha="left", va="center", fontsize=8, color="#444444",
            transform=ax.transAxes)

    fig.subplots_adjust(left=0.02, right=0.98, top=0.97, bottom=0.04)
    _save(fig, "fig4_2a_detection_grid")

    rows = []
    for ft in GRID_ROWS:
        for sev in SEVERITY_COLS:
            agg = grid[ft][sev]
            rows.append({
                "fault_type":     ft,
                "severity":       f"{sev * 100:.1f}%",
                "n_records":      agg["n"],
                "detection_rate": f"{agg['detection_rate']:.2f}" if not np.isnan(agg["detection_rate"]) else "NaN",
                "verdict_flip":   agg["verdict_flip"],
            })
    _save_csv(rows, "fig4_2a_detection_grid")
    print("  saved: fig4_2a_detection_grid")


# ---------------------------------------------------------------------------
# Figure 4.2b -- start-time shift vs measured residual
# ---------------------------------------------------------------------------

def fig_timeliness_shift(fi: dict) -> None:
    """Figure 4.2b: injected start-time shift vs measured alignment residual."""
    records = fi["records"]
    tim = [r for r in records if r["fault_type"] == "timeliness_start_shift"]
    pids    = sorted(set(r["participant"] for r in tim), key=_pid_key)
    offsets = sorted(set(r["offset_injected_s"] for r in tim))

    fig, ax = plt.subplots(figsize=(7, 4))

    markers = ["o", "s", "^"]
    colours = [BLUE, ORANGE, VERMILION]
    for idx, pid in enumerate(pids):
        pts = {r["offset_injected_s"]: r["dirty_residual_s"]
               for r in tim if r["participant"] == pid}
        xs = [off for off in offsets]
        ys = [pts[off] for off in offsets]
        ax.scatter(xs, ys,
                   color=colours[idx % len(colours)],
                   marker=markers[idx % len(markers)],
                   s=55, zorder=4, label=pid)

    threshold = 1.0
    ax.axhline(threshold, color="#888888", lw=1.2, ls="--",
               label=f"Threshold ({threshold:.1f} s)")

    ax.set_xscale("log")
    ax.set_xticks(offsets)
    ax.set_xticklabels(
        [f"{o:.0f} s" if o >= 1 else f"{o} s" for o in offsets],
        fontsize=9,
    )
    ax.set_xlabel("Injected start-time shift (s)")
    ax.set_ylabel("Measured alignment residual (s)")
    ax.set_ylim(bottom=0)

    # annotation: signal and device from experiment design
    ax.annotate(
        "Signal shifted: E4/EDA start timestamp\n(Empatica E4 wristband)",
        xy=(0.03, 0.72), xycoords="axes fraction",
        fontsize=8, color="#444444",
        ha="left", va="top",
    )

    ax.legend(loc="upper right", framealpha=0.85, fontsize=8)
    ax.grid(axis="y", color="#E8E8E8", zorder=0)

    fig.tight_layout()
    _save(fig, "fig4_2b_timeliness_shift")

    rows = [
        {
            "participant":       r["participant"],
            "offset_injected_s": r["offset_injected_s"],
            "dirty_residual_s":  r["dirty_residual_s"],
            "signal":            r["signal"],
        }
        for r in sorted(tim, key=lambda x: (_pid_key(x["participant"]), x["offset_injected_s"]))
    ]
    _save_csv(rows, "fig4_2b_timeliness_shift")
    print("  saved: fig4_2b_timeliness_shift")


# ---------------------------------------------------------------------------
# Figure 4.3 -- start-time gap per participant
# ---------------------------------------------------------------------------

def fig_start_time_gap(al: dict) -> None:
    """Figure 4.3: E4 to RespiBAN start-time gap per participant, S2 at top."""
    pp   = al["participants"]
    pids = sorted(pp.keys(), key=_pid_key)   # S2, S3 ... S17
    gaps = [pp[pid]["offset_before_s"] for pid in pids]
    mean_gap = al["summary"]["mean_offset_before_s"]

    fig, ax = plt.subplots(figsize=(7, 4.5))

    ax.scatter(gaps, range(len(pids)), color=BLUE, s=60, zorder=3,
               label="Participant gap")
    ax.axvline(mean_gap, color=ORANGE, lw=1.5, ls="--",
               label=f"Mean ({mean_gap:.0f} s)")

    ax.set_yticks(range(len(pids)))
    ax.set_yticklabels(pids, fontsize=9)
    ax.invert_yaxis()   # S2 at top, S17 at bottom
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

    c = dims["completeness"]
    rows.append({
        "Dimension":        "Completeness",
        "Threshold":        c["threshold"],
        "Before (Bronze)":  c["before"]["missingness_rate"],
        "After cleaning":   c["after"]["missingness_rate"],
        "Passes":           c["threshold_pass_gold"],
        "Note":             "60 intentional removals excluded from rate",
    })

    vc = dims["validity_conformance"]
    rows.append({
        "Dimension":        "Validity: conformance",
        "Threshold":        vc["threshold"],
        "Before (Bronze)":  f"{vc['before']['violation_rate']:.2e} ({vc['before']['violation_count']} violations)",
        "After cleaning":   f"{vc['after']['violation_rate']:.2e} ({vc['after']['violation_count']} violations)",
        "Passes":           vc["threshold_pass_gold"],
        "Note":             "TEMP warm-up artefact (60 samples, all participants)",
    })

    vp = dims["validity_plausibility"]
    rows.append({
        "Dimension":        "Validity: plausibility",
        "Threshold":        f"<= {vp['threshold']}",
        "Before (Bronze)":  f"{vp['before']['failure_rate']:.2e} ({vp['before']['violation_count']} failures)",
        "After cleaning":   f"{vp['after']['failure_rate']:.2e} ({vp['after']['violation_count']} failures)",
        "Passes":           vp["threshold_pass_gold"],
        "Note":             "Same 60 TEMP samples; BVP and IBI excluded",
    })

    tl = dims["timeliness"]
    rows.append({
        "Dimension":        "Timeliness (partly assessed)",
        "Threshold":        f"<= {tl['threshold']} s",
        "Before (Bronze)":  f"~{tl['before']['value_s']:.0f} s start gap",
        "After cleaning":   f"{tl['after']['max_offset_s']:.6f} s max residual (15/15 pass)",
        "Passes":           tl["threshold_pass_gold"],
        "Note":             "5-point method; cannot detect single-device clock offset",
    })

    for key, label in [("consistency", "Consistency"), ("accuracy", "Accuracy")]:
        rows.append({
            "Dimension":        label,
            "Threshold":        "N/A",
            "Before (Bronze)":  "not measured",
            "After cleaning":   "not measured",
            "Passes":           "N/A",
            "Note":             dims[key].get("limitation", "intentionally unmeasured"),
        })

    df = pd.DataFrame(rows)
    _save_table(df, "table4_1_quality_before_after")
    print("  saved: table4_1_quality_before_after")


def table_fault_injection_summary(fi: dict) -> None:
    """Table 4.2: fault injection summary per fault type."""
    records = fi["records"]
    fault_records = [r for r in records if r["fault_type"] != "control_no_injection"]

    all_ft_labels = {
        "completeness_scattered_nan":         "Completeness: scattered missing values",
        "completeness_contiguous_dropout":    "Completeness: contiguous dropout",
        "conformance_non_numeric":            "Conformance: non-numeric values",
        "conformance_out_of_device_range":    "Conformance: out-of-range ECG",
        "conformance_sampling_rate_fault":    "Conformance: sampling-rate fault",
        "plausibility_physiological_impossible": "Plausibility: impossible values",
    }

    rows = []
    for ft, label in all_ft_labels.items():
        if ft == "conformance_sampling_rate_fault":
            subset = [r for r in fault_records if r["fault_type"] == ft]
            n_det = sum(1 for r in subset if r.get("detected", False))
            rows.append({
                "Fault type":       label,
                "Dimension":        subset[0]["dimension"] if subset else "",
                "Severity":         "N/A (binary fault)",
                "n records":        len(subset),
                "Detection rate":   f"{n_det / len(subset):.2f}" if subset else "N/A",
                "Verdict flip":     any(r.get("verdict_flip", False) for r in subset),
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
                "Fault type":       label,
                "Dimension":        subset[0]["dimension"],
                "Severity":         f"{sev * 100:.1f}%",
                "n records":        agg["n"],
                "Detection rate":   f"{agg['detection_rate']:.2f}",
                "Verdict flip":     agg["verdict_flip"],
                "False detections": 0,
            })

    tim_records = [r for r in fault_records if r["fault_type"] == "timeliness_start_shift"]
    for off in sorted(set(r["offset_injected_s"] for r in tim_records)):
        subset = [r for r in tim_records if r["offset_injected_s"] == off]
        detected = sum(1 for r in subset if r.get("detected", False))
        rows.append({
            "Fault type":       "Timeliness: start-time shift",
            "Dimension":        "timeliness",
            "Severity":         f"{off} s shift",
            "n records":        len(subset),
            "Detection rate":   f"{detected / len(subset):.2f}",
            "Verdict flip":     False,
            "False detections": 0,
        })

    df = pd.DataFrame(rows)
    _save_table(df, "table4_2_fault_injection_summary")
    print("  saved: table4_2_fault_injection_summary")


def table_per_participant(al: dict, fi_records: list[dict]) -> None:
    """Per-participant table sorted S2 to S17."""
    conf  = _load("wesad_conformance.json")
    plaus = _load("wesad_plausibility.json")
    clean = _load("wesad_cleaning.json")

    pids = sorted(al["participants"].keys(), key=_pid_key)
    rows = []
    for pid in pids:
        c = conf["participants"][pid]
        e4_viol = sum(
            sig.get("range", {}).get("n_violations", 0)
            for sig in c["e4"].values()
            if isinstance(sig, dict) and "range" in sig
        )

        p = plaus["participants"][pid]
        e4_plaus = sum(
            sig.get("n_violations", 0)
            for sig in p["e4"].values()
            if isinstance(sig, dict)
        )

        n_replaced = len(clean["participants"][pid]["cleaning"]["indices_replaced"])

        aln = al["participants"][pid]
        rows.append({
            "Participant":                 pid,
            "Conf. violations (Bronze)":   e4_viol,
            "Plaus. failures (Bronze)":    e4_plaus,
            "Samples removed (cleaning)":  n_replaced,
            "Start-time gap (s)":          aln["offset_before_s"],
            "Within-overlap residual (s)": aln["offset_after_s"],
            "Alignment passes (<=1.0 s)":  aln["passes_threshold"],
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

    # remove old split fig4_2 file replaced by 4.2a and 4.2b
    for old in [
        FIGURES / "fig4_2_fault_injection.png",
        FIGURES / "fig4_2_fault_injection.pdf",
        DATA_DIR / "fig4_2_fault_injection.csv",
    ]:
        if old.exists():
            old.unlink()

    al = _load("wesad_alignment.json")
    qr = _load("wesad_quality_report.json")
    fi = json.loads(
        (REPORTS / "experiments" / "fault_injection_results.json").read_text(encoding="utf-8")
    )

    print("Building figures ...")
    fig_pipeline_overview()
    fig_temp_artefact("S2")
    fig_detection_grid(fi)
    fig_timeliness_shift(fi)
    fig_start_time_gap(al)

    print("Building tables ...")
    table_quality_before_after(qr)
    table_fault_injection_summary(fi)
    table_per_participant(al, fi["records"])

    print("Done.")


if __name__ == "__main__":
    main()
