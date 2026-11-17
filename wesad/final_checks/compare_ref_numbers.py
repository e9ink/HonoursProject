"""Compare current pipeline report outputs against the locked reference numbers."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
REF = json.loads((ROOT / "final_checks" / "reference_numbers.json").read_text(encoding="utf-8"))
REPORTS = ROOT / "reports"


def _load(name: str) -> dict:
    p = REPORTS / name
    if not p.exists():
        print(f"MISSING: {p}")
        sys.exit(1)
    return json.loads(p.read_text(encoding="utf-8"))


failures = []


def check(label: str, actual, expected) -> None:
    if actual != expected:
        failures.append(f"  MISMATCH {label}: got {actual!r}, expected {expected!r}")
    else:
        print(f"  OK  {label} = {actual!r}")


# Conformance before
c = _load("wesad_conformance.json")["summary"]
ref = REF["conformance_before"]["summary"]
check("conformance_before.total_range_violations", c["total_range_violations"], ref["total_range_violations"])
check("conformance_before.overall_range_violation_rate", c["overall_range_violation_rate"], ref["overall_range_violation_rate"])
check("conformance_before.total_range_cells_checked", c["total_range_cells_checked"], ref["total_range_cells_checked"])

# Conformance after
ca = _load("wesad_conformance_post_cleaning.json")["summary"]
rca = REF["conformance_after"]["summary"]
check("conformance_after.total_range_violations", ca["total_range_violations"], rca["total_range_violations"])
check("conformance_after.overall_range_violation_rate", ca["overall_range_violation_rate"], rca["overall_range_violation_rate"])

# Completeness before
comp = _load("wesad_completeness.json")["summary"]
rcomp = REF["completeness_before"]["summary"]
check("completeness_before.e4_overall_missingness_rate", comp["e4_overall_missingness_rate"], rcomp["e4_overall_missingness_rate"])
check("completeness_before.e4_total_nan_cells", comp["e4_total_nan_cells"], rcomp["e4_total_nan_cells"])

# Completeness after
compa = _load("wesad_completeness_post_cleaning.json")["summary"]
rcompa = REF["completeness_after"]["summary"]
check("completeness_after.e4_overall_missingness_rate", compa["e4_overall_missingness_rate"], rcompa["e4_overall_missingness_rate"])
check("completeness_after.e4_total_nan_cells", compa["e4_total_nan_cells"], rcompa["e4_total_nan_cells"])
check("completeness_after.e4_intentional_removals", compa["e4_intentional_removals"], rcompa["e4_intentional_removals"])

# Plausibility before
p = _load("wesad_plausibility.json")["summary"]
rp = REF["plausibility_before"]["summary"]
check("plausibility_before.total_violations", p["total_violations"], rp["total_violations"])
check("plausibility_before.overall_failure_rate", p["overall_failure_rate"], rp["overall_failure_rate"])
check("plausibility_before.total_samples_checked", p["total_samples_checked"], rp["total_samples_checked"])

# Plausibility after
pa = _load("wesad_plausibility_post_cleaning.json")["summary"]
rpa = REF["plausibility_after"]["summary"]
check("plausibility_after.total_violations", pa["total_violations"], rpa["total_violations"])
check("plausibility_after.overall_failure_rate", pa["overall_failure_rate"], rpa["overall_failure_rate"])

# Cleaning
cl = _load("wesad_cleaning.json")["summary"]
rcl = REF["cleaning"]["summary"]
check("cleaning.total_samples_replaced", cl["total_samples_replaced"], rcl["total_samples_replaced"])
check("cleaning.n_participants_cleaned", cl["n_participants_cleaned"], rcl["n_participants_cleaned"])

# Alignment
al = _load("wesad_alignment.json")["summary"]
ral = REF["alignment"]["summary"]
check("alignment.max_offset_after_s", al["max_offset_after_s"], ral["max_offset_after_s"])
check("alignment.n_pass_threshold", al["n_pass_threshold"], ral["n_pass_threshold"])
check("alignment.n_fail_threshold", al["n_fail_threshold"], ral["n_fail_threshold"])
check("alignment.mean_offset_before_s", al["mean_offset_before_s"], ral["mean_offset_before_s"])

print()
if failures:
    print("FAIL -- reference numbers changed:")
    for f in failures:
        print(f)
    sys.exit(1)
else:
    print(f"PASS -- all {20} reference numbers match.")
