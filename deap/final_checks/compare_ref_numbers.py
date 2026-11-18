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


# Completeness
c = _load("deap_completeness.json")
rc = REF["completeness"]
check("completeness.total_nan_all_participants", c["total_nan_all_participants"], rc["total_nan_all_participants"])
check("completeness.total_inf_all_participants", c["total_inf_all_participants"], rc["total_inf_all_participants"])
check("completeness.participant_count", c["participant_count"], rc["participant_count"])

# Conformance
cf = _load("deap_conformance.json")
rcf = REF["conformance"]
check("conformance.total_violations", cf["total_violations"], rcf["total_violations"])
check("conformance.participant_count", cf["participant_count"], rcf["participant_count"])

# Label plausibility (Bronze -- before cleaning)
lp = _load("deap_label_plausibility.json")
rlp = REF["label_plausibility"]
check("label_plausibility.total_out_of_range_all_participants",
      lp["total_out_of_range_all_participants"],
      rlp["total_out_of_range_all_participants"])

# Consistency (Bronze)
cons = _load("deap_consistency.json")
rcons = REF["consistency"]
check("consistency.structure_total_mismatches",
      cons["consistency_structure"]["total_mismatches"],
      rcons["structure_total_mismatches"])
check("consistency.cross_source_total_mismatches",
      cons["consistency_cross_source"]["total_mismatches"],
      rcons["cross_source_total_mismatches"])

# Cleaning
cl = _load("deap_cleaning.json")
rcl = REF["cleaning"]
check("cleaning.total_corrections", cl["total_corrections"], rcl["total_corrections"])
check("cleaning.n_participants_with_corrections",
      cl["n_participants_with_corrections"],
      rcl["n_participants_with_corrections"])

# Post-cleaning (Silver)
post = _load("deap_post_cleaning.json")
rpost = REF["post_cleaning"]
check("post_cleaning.total_label_plausibility_oor",
      post["total_label_plausibility_oor"],
      rpost["total_label_plausibility_oor"])
check("post_cleaning.total_cross_source_mismatches",
      post["total_cross_source_mismatches"],
      rpost["total_cross_source_mismatches"])

# Quality report
qr = _load("deap_quality_report.json")
rqr = REF["quality_report"]
check("quality_report.overall_pass", qr["overall_pass"], rqr["overall_pass"])
check("quality_report.label_plausibility_before_value",
      qr["dimensions"]["label_plausibility"]["before"]["value"],
      rqr["label_plausibility_before_value"])
check("quality_report.label_plausibility_after_value",
      qr["dimensions"]["label_plausibility"]["after"]["value"],
      rqr["label_plausibility_after_value"])
check("quality_report.cross_source_before_value",
      qr["dimensions"]["consistency"]["sub_checks"]["cross_source"]["before"]["value"],
      rqr["cross_source_before_value"])
check("quality_report.cross_source_after_value",
      qr["dimensions"]["consistency"]["sub_checks"]["cross_source"]["after"]["value"],
      rqr["cross_source_after_value"])

# Label audit inversion verification
audit_path = REPORTS / "deap_label_audit.json"
if not audit_path.exists():
    print(f"MISSING: {audit_path}")
    sys.exit(1)
audit = json.loads(audit_path.read_text(encoding="utf-8"))
# Count Valence/Arousal mismatches satisfying mirror + xls = 9
n_inv = sum(
    len([d for d in pp["discrepancies"] if d["dim"] in ("Valence", "Arousal")])
    for pp in audit["v2_mirror"]["xls_comparison"]["per_participant"].values()
)
rla = REF["label_audit"]
check("label_audit.v2_mismatches_satisfying_mirror_plus_xls_eq_9",
      n_inv,
      rla["v2_mismatches_satisfying_mirror_plus_xls_eq_9"])

print()
N_CHECKS = 18
if failures:
    print(f"FAIL -- reference numbers changed:")
    for f in failures:
        print(f)
    sys.exit(1)
else:
    print(f"PASS -- all {N_CHECKS} reference numbers match.")
