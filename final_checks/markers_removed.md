# Markers Removed

Markers scanned: `[KEVIN TO REVIEW: ...]`, `[KEVIN TO COMPLETE: ...]`, `TODO`, `FIXME`, `XXX`, `TBD`, `VERIFY`, `CHECK THIS`, `NEEDS REVIEW`, `PLACEHOLDER`, `[citation needed]`.

Scan covered: all `.md`, `.py`, `.yaml`, `.json`, `.txt`, `.gitignore` files in the repository. No markers found in `src/`, `config/`, `tests/`, or `reports/`.

---

## Markers removed (content kept, wrapper deleted)

### docs/governance/datasheet_wesad.md

1. **Line 148 (original):** Trailing addition `[KEVIN TO REVIEW: suitability for clinical applications.]` after the sentence listing suited tasks. Removal: deleted marker; sentence ends cleanly.

2. **Line 151 (original):** `[KEVIN TO REVIEW: clinical diagnosis; population-level inference beyond the study population; deployment in high-stakes automated decision-making without additional validation.]`. Removal: kept content verbatim, removed wrapper. Now reads as a plain sentence.

### docs/governance/data_impact_assessment_wesad.md

3. **Line 14 (original):** Trailing `[KEVIN TO REVIEW: minimum sample size requirements for the intended downstream application.]`. Removal: deleted marker; sentence about confidence intervals ends cleanly.

4. **Line 30 (original):** Trailing `[KEVIN TO REVIEW: whether affected participants should be flagged or excluded for specific analyses.]`. Removal: deleted marker; sentence about field notes ends cleanly.

5. **Line 40 (original):** Trailing `[KEVIN TO REVIEW: whether the combination of demographic fields in the readme files constitutes sufficient risk to warrant additional controls before sharing derived outputs.]`. Removal: deleted marker; sentence about re-identification ends cleanly.

6. **Line 46 (original):** Trailing `[KEVIN TO REVIEW: whether specific derived features (e.g. heart rate variability derived from IBI, or EDA peaks) carry additional privacy risks in the intended deployment context.]`. Removal: deleted marker; sentence about physiological signal sensitivity ends cleanly.

7. **Line 53 (original):** Trailing `[KEVIN TO REVIEW: severity of this risk for the specific downstream model architecture.]`. Removal: deleted marker; sentence about detection documentation ends cleanly.

### docs/governance/stewardship_roles.md

8. **Line 22 (original):** `[KEVIN TO COMPLETE: the research institution or group that created and maintains WESAD is the data owner of the raw dataset. The access agreement governs what this project may do with the data.]`. Removal: kept content verbatim, removed wrapper.

---

## Markers left (genuinely unresolved or open governance questions)

### docs/governance/datasheet_wesad.md

- **Line 160 (original):** `[KEVIN TO COMPLETE: current repository URL and access request process.]` -- Left because the repository URL and access request process for the external WESAD dataset are not documented in any available source and cannot be supplied from this codebase.

### docs/governance/stewardship_roles.md

- **Line 72 (original):** `[KEVIN TO REVIEW: confirm cloud storage is permitted under the WESAD access terms before relying on OneDrive as the backup mechanism for participant data.]` -- Left because this is an open governance question that requires confirmation from the WESAD data access agreement, which is external to this repository.
