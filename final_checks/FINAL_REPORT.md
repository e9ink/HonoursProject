# Final Tidy-Up and Submission Checks

**Branch:** final-tidy -> master
**Tag:** v1.0-submission
**Date:** 2026-11-14

---

## Step 1: Reference numbers (pre-change pipeline run)

Pipeline ran to completion (10/10 stages, exit code 0, 1832.5s).
Reference numbers saved to `final_checks/reference_numbers.json`.

Key figures:

| Metric | Value |
|---|---|
| Conformance violations (Bronze) | 60 (E4 TEMP warm-up, indices 0-3, all 15 participants) |
| Conformance violation rate | 1.2e-07 |
| Conformance passes threshold (0.0) | False (expected -- violation exists before cleaning) |
| Conformance violations (Gold/post-cleaning) | 0 |
| Completeness missingness rate | 0.0 |
| Plausibility violations (Bronze) | 60 (same warm-up samples) |
| Plausibility violation rate | 1.5e-07 |
| Plausibility passes threshold (0.01) | True |
| Plausibility violations (Gold) | 0 |
| Cleaning: NaN introduced | 60 (4 per participant x 15 participants) |
| Alignment: mean start-time gap | 1181.2 s (range 920-1416 s) |
| Alignment: max within-overlap residual | 0.107 s |
| Alignment: participants pass 1.0 s threshold | 15/15 |
| Fault injection: control records | 3, all any_flag=False |
| Fault injection: non-timeliness dr | 1.0 for all 195 count-based records |
| Fault injection: timeliness | 15 records, all undetected (expected) |

---

## Step 2: Marker removals

8 markers removed (content kept where present). 2 left (open governance questions).
Documented in `final_checks/markers_removed.md`.

Removed from:
- `docs/governance/datasheet_wesad.md`: 2 markers (trailing review note + unwrapped contraindications)
- `docs/governance/data_impact_assessment_wesad.md`: 5 markers (all trailing notes)
- `docs/governance/stewardship_roles.md`: 1 marker (content kept verbatim)

Left in place:
- `docs/governance/datasheet_wesad.md` line 162: WESAD repository URL and access request process -- genuinely unknown
- `docs/governance/stewardship_roles.md` line 72: OneDrive backup permission under WESAD access terms -- open governance question

---

## Step 3: Code tidy-up

- Added `*.pptx` and `docs/sources/` to `.gitignore`.
- Converted `requirements.txt` from UTF-16LE with BOM to UTF-8 without BOM (content and pinned versions unchanged).
- No dead code, debug prints, or unused imports found in `src/`.
- No scratch files found (experiments/scratch/ excluded by .gitignore).

---

## Step 4: Consistency checks

- Added "partly assessed" qualification to timeliness rows in `docs/governance/datasheet_wesad.md` and `docs/governance/data_impact_assessment_wesad.md`.
- Added "Timeliness is therefore partly assessed." to DIA limitations section.
- Changed "false positives"/"fp" to "false detections"/"fd" in `docs/progress_log.md` fault injection section only (lines 311 and 525 are different contexts, unchanged).
- Added `limitation` field to timeliness dimension in `src/report.py` quality report output.
- Updated quality report headline in `src/report.py` to note uniform-shift limitation.
- Accuracy and consistency: confirmed "out of scope" language consistent across all docs.

---

## Step 5: README update

- Added "timeliness (partly assessed)" with explanation to opening paragraph.
- Added "Known limitations" section covering: timeliness partly assessed, within-bounds faults untested, accuracy unmeasured, consistency not assessed.

---

## Step 6: Final verification

**Fresh venv:** `.venv_verify/` created from `requirements.txt` (UTF-8, all 12 packages pinned).

**Test suite:** `python -m pytest tests/ -q` -- 109 passed, 0 failed.

**Bronze checksums:** All 90 signal files in the Gold manifest verified against SHA-256. No mismatches.

**Fault injection quick check:** 3 control records (all any_flag=False), 195 count-based fault records (all dr=1.0), 15 timeliness records (all undetected, as expected).

**Determinism check (second pipeline run):**
Second run completed (10/10 stages, exit code 0, 1738.2s).

Comparison results (compare_ref_numbers.py against final_checks/reference_numbers.json):

```
=== Conformance before ===
  [OK] total_range_violations: got 60, expected 60
  [OK] overall_range_violation_rate: got 1.2e-07, expected 1.2e-07
  [OK] passes_threshold: got False, expected False
  [OK] total_non_numeric_violations: got 0, expected 0
  [OK] n_format_errors: got 0, expected 0
  [OK] n_sampling_violations: got 0, expected 0

=== Conformance after ===
  [OK] total_range_violations: got 0, expected 0
  [OK] overall_range_violation_rate: got 0.0, expected 0.0
  [OK] total_non_numeric_violations: got 0, expected 0

=== Completeness before ===
  [OK] chest_nan_rate: got 0.0, expected 0.0
  [OK] chest_sequence_gap_rate: got 0.0, expected 0.0
  [OK] chest_total_dropped_samples: got 0, expected 0
  [OK] chest_total_expected_samples: got 62935498, expected 62935498
  [OK] chest_total_nan_cells: got 0, expected 0
  [OK] dataset_passes_threshold: got True, expected True
  [OK] e4_overall_missingness_rate: got 0.0, expected 0.0
  [OK] e4_total_cells_checked: got 18073707, expected 18073707
  [OK] e4_total_nan_cells: got 0, expected 0
  [OK] per_participant_passes: all 15 True
  [OK] threshold_max_missingness_rate: got 0.0, expected 0.0

=== Plausibility before ===
  [OK] overall_failure_rate: got 1.5e-07, expected 1.5e-07

=== Alignment ===
  [OK] n_participants: got 15, expected 15
  [OK] mean_offset_before_s: got 1181.2, expected 1181.2
  [OK] max_offset_after_s: got 0.107143, expected 0.107143
  [OK] n_pass_threshold: got 15, expected 15
  [OK] all_pass_threshold: got True, expected True

=== Cleaning ===
  [OK] n_participants_cleaned: got 15, expected 15
  [OK] indices_replaced_per_participant: got [0, 1, 2, 3], expected [0, 1, 2, 3]
  [OK] total_samples_replaced: got 60, expected 60

PASS: all reference numbers match.
```

---

## Step 7: Merge and tag

- Merged `final-tidy` into `master` with a fast-forward merge.
- Tagged `v1.0-submission` on the merge commit.

**Commits on final-tidy:**

1. `chore(step-1)`: record reference numbers before final-tidy changes
2. `docs+src(steps-2+4)`: remove review markers, add timeliness limitation notes
3. `chore(step-3)`: add gitignore entries, convert requirements.txt to UTF-8
4. `docs(step-5)`: update README with timeliness caveat and known limitations
5. `docs`: remove trailing space in datasheet prepared-by line
6. `chore(step-6)`: verify determinism, comparison passes
7. `docs(step-7)`: add FINAL_REPORT.md
