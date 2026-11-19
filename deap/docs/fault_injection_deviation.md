# DEAP Fault Injection: Pre-registration Deviation Note

**Date:** 2026-11-17
**Author:** Kevin Hudoyo (24790848)

---

## Deviation

The pre-registered fault injection design (commit 2108432) stated that the
control case -- no fault applied -- was expected to pass all checks including
`label_plausibility` and `consistency_cross_source`. That expectation was
incorrect.

### Root cause

The fault injection participants (s01 and s25) were selected after the label
audit (commit 9f22f98) had already established that every participant in the
v2 mirror carries label inversions. The audit showed that inverted values
sometimes fall below the SAM floor of 1 (specifically, any trial with an
original XLS rating above 8 produces an inverted value below 1 after
9 - original). The expected outcomes in experiments.yaml were written without
accounting for this pre-existing failure.

Specifically:
- s01 has 5 label values below 1 and 26 cross-source mismatches in the
  unmodified data.
- s25 has 12 label values below 1 and 28 cross-source mismatches in the
  unmodified data.

Both checks therefore fail on the control, which makes the pre-registered
"overall: pass" for the control case impossible to achieve.

### Design oversight, not data modification

The pre-registered file is not changed. The expected outcomes remain as
written in commit 2108432. This document records the deviation and specifies
the alternative evaluation criterion used instead.

---

## Alternative evaluation criterion

Because the control baseline already fails the label checks, fault detection
is assessed relative to the control, not against an absolute pass/fail
standard.

**A fault is counted as detected if:**
1. The check targeted by the fault shows a count change from the control in
   the expected direction (e.g., total_nan increases for nan_in_eeg,
   total_out_of_range increases for label_out_of_range, violation_count
   increases for truncated_data).
2. For the label_out_of_range fault: each injected position that was not
   already out of range in the control data is newly flagged. Injected
   positions that overwrite an already-out-of-range value are excluded from
   the net-new count (the fault is still applied; it cannot be detected as a
   distinct event at that position because the check cannot distinguish which
   violation is which).

**Non-targeted checks:** changes to counts in checks not targeted by a fault
are noted. For nan_in_eeg and truncated_data, the label checks do not change
from the control (expected: NaN injection and shape truncation affect the data
array, not the labels).

---

## Results under the alternative criterion

See deap/reports/experiments/deap_fault_injection_vs_control.json for full
details. Summary:

| Fault | Target check | s01 delta | s25 delta | Detected |
|---|---|---|---|---|
| nan_in_eeg | completeness (total_nan) | +3225 | +3225 | Yes |
| label_out_of_range | label_plausibility (total_out_of_range) | +8 (of 10 injected; 2 overwritten) | +7 (of 10 injected; 3 overwritten) | Yes |
| truncated_data | conformance (violation_count) | +1 | +1 | Yes |

All three injected faults are detected. The positions that show a delta below
10 for label_out_of_range are accounted for by pre-existing out-of-range
values at the same (trial, dimension) location in the original data.

---

## Non-targeted check stability

| Fault | completeness (nan) | conformance (violations) | label_plausibility (oor) | consistency_cross_source (mismatches) |
|---|---|---|---|---|
| nan_in_eeg | +3225 (target) | 0 | 0 | 0 |
| label_out_of_range | 0 | 0 | +8/+7 (target) | +7/+5 |
| truncated_data | 0 | +1 (target) | 0 | 0 |

Note: the label_out_of_range fault increases consistency_cross_source because
the injected values (0.0 and 10.0) also differ from the XLS ratings. This is
expected: any label modification that changes a value will show up in the
cross-source check as well as in label_plausibility.

---

## Supervisor approval (2026-11-18)

The 2026-11-18 supervisor approval (Dr Tobias Cibis) covered three decisions only:
using the Kaggle mirror to obtain the DEAP dataset, setting the quality rules after
Bronze profiling (because peripheral channel units are undocumented), and correcting
the inverted Valence and Arousal ratings in Silver using participant_ratings.xls as
the authoritative source.

The fault-injection design and this deviation note have not been separately reviewed
by the supervisor.

---

## Note on experiments.yaml wording (2026-11-18)

The comment "Temp baseline-corrected" in deap/config/experiments.yaml is
unsourced. The data-only description is: Group A (s01-s23, s25) has a Temp
channel range under 10 per participant; Group B (s24, s26-s32) has a range
over 500 per participant; cause of the split is undocumented. experiments.yaml
is pre-registered and is not changed; this note records the correction.
