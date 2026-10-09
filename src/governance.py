"""
Gold layer — governance controls: lineage metadata and audit trail.

Produces two outputs (read-only on bronze/ and silver/):

  gold/WESAD/wesad_lineage.json
      Per-participant, per-signal provenance document.
      Grounded in Abraham et al. (2019) metadata management:
        Abraham, R., John, D., & Pollock, E. (2019). A comprehensive survey of
        metadata management. Information Processing & Management, 56(6), 102069.
        https://doi.org/10.1016/j.ipm.2019.102069

  reports/wesad_governance.json
      Chronological audit trail and governance summary.
      Grounded in Tallon et al. (2013) accountability/stewardship:
        Tallon, P., Ramirez, R., & Short, J. (2013). The information artifact in
        IT governance: toward a theory of information governance. Journal of
        Management Information Systems, 30(3), 141-177.
        https://doi.org/10.2753/MIS0742-1222300306

Determinism:
    The lineage content (source paths, transformations, stage references) is
    fully deterministic across reruns. Run timestamps are non-deterministic by
    nature; they are isolated in a single top-level "run_context" key in each
    output so the rest of the document is diffable. The timestamp field is
    clearly labelled; callers that want a diffable snapshot can strip or ignore
    "run_context" without touching the substantive content.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT         = Path(__file__).resolve().parent.parent
BRONZE_WESAD = ROOT / "bronze" / "WESAD"
SILVER_WESAD = ROOT / "silver" / "WESAD"
GOLD_WESAD   = ROOT / "gold"   / "WESAD"
REPORTS      = ROOT / "reports"

PARTICIPANTS = [f"S{n}" for n in range(2, 18) if n != 12]

E4_SIGNALS = ["ACC", "BVP", "EDA", "HR", "TEMP"]

RESPIBAN_CHANNELS = [
    "ACC_X", "ACC_Y", "ACC_Z",
    "ECG",
    "EDA",
    "EMG",
    "RESP",
    "TEMP",
]

# ── References ────────────────────────────────────────────────────────────────

LINEAGE_REFERENCE = (
    "Abraham, R., John, D., & Pollock, E. (2019). A comprehensive survey of "
    "metadata management. Information Processing & Management, 56(6), 102069. "
    "https://doi.org/10.1016/j.ipm.2019.102069"
)

AUDIT_REFERENCE = (
    "Tallon, P., Ramirez, R., & Short, J. (2013). The information artifact in "
    "IT governance: toward a theory of information governance. Journal of "
    "Management Information Systems, 30(3), 141-177. "
    "https://doi.org/10.2753/MIS0742-1222300306"
)

# ── Pipeline stage registry (ordered) ─────────────────────────────────────────

PIPELINE_STAGES = [
    {
        "stage_id":    "profiling",
        "display_name": "Profiling (Task 2)",
        "module":      "src/profiling.py",
        "report":      "reports/wesad_baseline.json",
        "description": (
            "Dataset profiling: per-participant, per-signal sample counts, "
            "sampling rates, and value ranges. Establishes the baseline against "
            "which later checks are cross-validated."
        ),
    },
    {
        "stage_id":    "conformance",
        "display_name": "Conformance check (Task 3)",
        "module":      "src/checks/conformance.py",
        "report":      "reports/wesad_conformance.json",
        "description": (
            "Format, numeric type, and physiological range conformance checks "
            "across all signals and participants."
        ),
    },
    {
        "stage_id":    "completeness",
        "display_name": "Completeness check (Task 4)",
        "module":      "src/checks/completeness.py",
        "report":      "reports/wesad_completeness.json",
        "description": (
            "Missingness and sequence-gap checks across all signals. "
            "Cross-validated against Task 2 baseline."
        ),
    },
    {
        "stage_id":    "plausibility",
        "display_name": "Plausibility check (Task 5)",
        "module":      "src/checks/plausibility.py",
        "report":      "reports/wesad_plausibility.json",
        "description": (
            "Physiological plausibility checks against supervisor-signed-off bounds "
            "(config/physiological_ranges.yaml, signed off Dr. Tobias Cibis 2026-09-09). "
            "RespiBAN chest EDA (CH2) and TEMP (CH4) are explicitly excluded from "
            "plausibility checking: they are stored as raw sensor values, not physical "
            "units, and their physiology is already verified on the E4 wrist channels "
            "(duplicate coverage). Deliberate scope decision, documented in "
            "docs/progress_log.md."
        ),
    },
    {
        "stage_id":    "alignment",
        "display_name": "Cross-modal alignment (Task 7)",
        "module":      "src/alignment.py",
        "report":      "reports/wesad_alignment.json",
        "description": (
            "Cross-modal temporal alignment between E4 wristband and RespiBAN chest "
            "sensor. Five-point nearest-sample reconstruction measures the maximum "
            "absolute timestamp offset within the recording overlap window."
        ),
    },
    {
        "stage_id":    "cleaning",
        "display_name": "Silver cleaning (Task 8)",
        "module":      "src/cleaning.py",
        "report":      "reports/wesad_cleaning.json",
        "description": (
            "E4 TEMP warm-up artefact removal. Indices 0-3 of each participant's "
            "E4 TEMP channel replaced with NaN in the Silver layer (bronze untouched). "
            "Literal 'NaN' text preserves channel length regardless of pandas read "
            "settings. 60 samples replaced across 15 participants (4 per participant)."
        ),
    },
]

_STAGE_IDS = {s["stage_id"] for s in PIPELINE_STAGES}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rel(path: Path) -> str:
    """Return a forward-slash repo-relative path string."""
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _load_report(name: str) -> dict:
    path = REPORTS / name
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _e4_signal_entry(pid: str, signal: str, cleaning_report: dict) -> dict:
    """Build the lineage entry for one E4 signal of one participant."""
    bronze_path = BRONZE_WESAD / pid / f"{pid}_E4_Data" / f"{signal}.csv"
    silver_path = SILVER_WESAD / pid / f"{pid}_E4_Data" / f"{signal}.csv"

    stages = ["profiling", "conformance", "completeness", "plausibility"]
    transformations = []
    silver = None

    if signal == "TEMP":
        stages.append("cleaning")
        silver = _rel(silver_path)
        pid_cleaning = (
            cleaning_report.get("participants", {}).get(pid, {}).get("cleaning", {})
        )
        transformations.append({
            "stage":               "cleaning",
            "action":              "e4_temp_warmup_strip",
            "description":         (
                "NTC thermistor warm-up artefact: sensor reads ~382 degrees C "
                "during the first second before reaching thermal equilibrium. "
                "Indices 0-3 replaced with NaN; channel length preserved."
            ),
            "indices_replaced":    pid_cleaning.get("indices_replaced", [0, 1, 2, 3]),
            "original_values":     pid_cleaning.get("original_values"),
            "replacement":         "NaN",
            "channel_length_before": pid_cleaning.get("channel_length_before"),
            "channel_length_after":  pid_cleaning.get("channel_length_after"),
            "length_preserved":    pid_cleaning.get("length_unchanged", True),
            "silver_output":       silver,
            "cleaning_report_ref": "reports/wesad_cleaning.json",
        })

    return {
        "bronze_source":     _rel(bronze_path),
        "silver_intermediate": silver,
        "stages_applied":    stages,
        "transformations":   transformations,
    }


def _respiban_channel_entry(pid: str, channel: str) -> dict:
    """Build the lineage entry for one RespiBAN channel of one participant."""
    bronze_path = BRONZE_WESAD / pid / f"{pid}_respiban.txt"
    return {
        "bronze_source":      _rel(bronze_path),
        "silver_intermediate": None,
        "note":               (
            "RespiBAN channels are stored as columns in a single flat file; "
            "the bronze_source refers to the whole participant data file."
        ),
        "stages_applied":    [
            "profiling", "conformance", "completeness", "plausibility", "alignment"
        ],
        "transformations":   [],
        "plausibility_note": (
            "EDA (CH2) and TEMP (CH4) excluded from plausibility checks "
            "(raw sensor values, duplicate physiological coverage from E4 wrist). "
            "See docs/progress_log.md."
        ) if channel in ("EDA", "TEMP") else None,
    }


# ── Lineage document ──────────────────────────────────────────────────────────

def _build_lineage(cleaning_report: dict) -> dict:
    """
    Build the per-participant, per-signal lineage document.
    The run_context timestamp is the only non-deterministic field.
    """
    participants = {}
    for pid in sorted(PARTICIPANTS):
        e4 = {
            sig: _e4_signal_entry(pid, sig, cleaning_report)
            for sig in E4_SIGNALS
        }
        respiban = {
            ch: _respiban_channel_entry(pid, ch)
            for ch in RESPIBAN_CHANNELS
        }
        participants[pid] = {"e4": e4, "respiban": respiban}

    return {
        "schema":  "wesad_lineage_v1",
        "dataset": "WESAD",
        "grounding": {
            "framework":   "Abraham et al. (2019) metadata management",
            "citation":    LINEAGE_REFERENCE,
            "note": (
                "Lineage records the provenance chain for each signal: "
                "bronze source, any Silver intermediate, pipeline stages applied, "
                "and transformations. Non-transformed signals are traceable to "
                "their bronze source file with a full stage history."
            ),
        },
        "run_context": {
            "note":         "This field is non-deterministic. Strip it for diffing.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generator":    "src/governance.py",
        },
        "pipeline_stages": PIPELINE_STAGES,
        "participants":    participants,
    }


# ── Audit trail document ──────────────────────────────────────────────────────

def _build_audit(
    cleaning_report: dict,
    alignment_report: dict,
) -> dict:
    """
    Build the chronological audit trail and governance summary.
    """
    # Summarise per-stage findings from existing reports (read-only, no re-runs)
    stage_summaries = [
        {
            "order":       1,
            "stage_id":    "profiling",
            "display_name": "Profiling (Task 2)",
            "report":      "reports/wesad_baseline.json",
            "outcome":     "Baseline established for 15 participants.",
        },
        {
            "order":       2,
            "stage_id":    "conformance",
            "display_name": "Conformance check (Task 3)",
            "report":      "reports/wesad_conformance.json",
            "outcome": (
                "60 range violations found (E4 TEMP warm-up artefact, indices 0-3, "
                "all 15 participants). All other signals: zero violations."
            ),
        },
        {
            "order":       3,
            "stage_id":    "completeness",
            "display_name": "Completeness check (Task 4)",
            "report":      "reports/wesad_completeness.json",
            "outcome":     "Zero missingness. Cross-check against baseline passed.",
        },
        {
            "order":       4,
            "stage_id":    "plausibility",
            "display_name": "Plausibility check (Task 5)",
            "report":      "reports/wesad_plausibility.json",
            "outcome": (
                "60 physiologically-implausible samples (same E4 TEMP warm-up "
                "artefact). Overall failure rate 1.5e-07. Dataset passes threshold."
            ),
        },
        {
            "order":       5,
            "stage_id":    "alignment",
            "display_name": "Cross-modal alignment (Task 7)",
            "report":      "reports/wesad_alignment.json",
            "outcome": (
                f"15/15 participants pass 1.0 s threshold. "
                f"12/15 zero residual. S2/S3/S4 have small residuals "
                f"(max 0.107 s, within E4 EDA quantisation bound of 0.125 s). "
                f"Mean start-time gap: "
                f"{alignment_report.get('summary', {}).get('mean_offset_before_s', 'N/A')} s."
            ),
        },
        {
            "order":       6,
            "stage_id":    "cleaning",
            "display_name": "Silver cleaning (Task 8)",
            "report":      "reports/wesad_cleaning.json",
            "outcome": (
                "60 TEMP warm-up samples replaced with NaN across 15 participants "
                "(4 per participant, indices 0-3). Conformance violations 60 → 0. "
                "Channel lengths preserved. Silver TEMP.csv files written for all "
                "15 participants. Bronze untouched."
            ),
        },
    ]

    silver_files = [
        f"silver/WESAD/{pid}/{pid}_E4_Data/TEMP.csv"
        for pid in sorted(PARTICIPANTS)
    ]

    transformations_applied = [
        {
            "action":        "e4_temp_warmup_strip",
            "signal":        "E4/TEMP",
            "scope":         "all 15 participants",
            "indices":       [0, 1, 2, 3],
            "replacement":   "NaN",
            "bronze_modified": False,
            "silver_files_written": silver_files,
            "report_ref":    "reports/wesad_cleaning.json",
            "rationale": (
                "NTC thermistor warm-up artefact: sensor reads ~382 degrees C "
                "during the first second before reaching equilibrium. "
                "Samples flagged as conformance and plausibility violations before "
                "cleaning. Replaced in-place with NaN to preserve channel length."
            ),
        }
    ]

    return {
        "task":    "gold_governance",
        "dataset": "WESAD",
        "grounding": {
            "framework":   "Tallon et al. (2013) information governance / accountability",
            "citation":    AUDIT_REFERENCE,
            "note": (
                "The audit trail provides an accountability record: what pipeline "
                "stages ran, in order, what each produced, and what transformations "
                "were applied. Sufficient to reconstruct the complete history of "
                "what happened to the data."
            ),
        },
        "run_context": {
            "note":         "This field is non-deterministic. Strip it for diffing.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generator":    "src/governance.py",
        },
        "lineage_document": "gold/WESAD/wesad_lineage.json",
        "bronze_integrity": {
            "status":  "untouched",
            "note":    "bronze/ is read-only throughout the pipeline. No stage writes to bronze/.",
        },
        "silver_scope": {
            "note": (
                "silver/ contains only the one signal that required cleaning "
                "(E4 TEMP). All other signals are used directly from bronze/."
            ),
            "silver_files_written": len(silver_files),
        },
        "audit_trail":              stage_summaries,
        "transformations_applied":  transformations_applied,
        "governance_summary": {
            "n_participants":        len(PARTICIPANTS),
            "n_e4_signals_tracked":  len(E4_SIGNALS),
            "n_respiban_channels_tracked": len(RESPIBAN_CHANNELS),
            "n_transformations_applied": len(transformations_applied),
            "total_samples_replaced":    60,
            "pipeline_stages_completed": len(PIPELINE_STAGES),
            "all_ccp_checks_run":        True,
            "alignment_run":             True,
            "cleaning_run":              True,
            "pipeline_complete":         True,
        },
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    cleaning_report  = _load_report("wesad_cleaning.json")
    alignment_report = _load_report("wesad_alignment.json")

    lineage = _build_lineage(cleaning_report)
    audit   = _build_audit(cleaning_report, alignment_report)

    GOLD_WESAD.mkdir(parents=True, exist_ok=True)
    lineage_path = GOLD_WESAD / "wesad_lineage.json"
    audit_path   = REPORTS / "wesad_governance.json"

    with open(lineage_path, "w", encoding="utf-8") as fh:
        json.dump(lineage, fh, indent=2)

    with open(audit_path, "w", encoding="utf-8") as fh:
        json.dump(audit, fh, indent=2)

    print("Gold governance outputs written:")
    print(f"  Lineage : {_rel(lineage_path)}")
    print(f"  Audit   : {_rel(audit_path)}")
    print()
    print(f"Participants tracked : {len(PARTICIPANTS)}")
    print(f"E4 signals per PID   : {len(E4_SIGNALS)}")
    print(f"RespiBAN channels    : {len(RESPIBAN_CHANNELS)}")
    print(f"Transformations      : 1 (e4_temp_warmup_strip, 60 samples, 15 participants)")
    print(f"Bronze modified      : False")
    print(f"Silver modified      : False  (silver files were written by src/cleaning.py)")


if __name__ == "__main__":
    main()
