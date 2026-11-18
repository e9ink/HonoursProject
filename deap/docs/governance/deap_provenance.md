# DEAP Dataset Provenance

## Mirror 1 (incomplete -- replaced)

- **File name:** archive_DEAP_v1.zip (renamed from archive_DEAP.zip)
- **File size:** 1,093,268,490 bytes (approximately 1.02 GB)
- **SHA-256:** 9a128c46148ca975580c2c72549491882b011685b2051d5e4867592145daa36c
- **Participants:** 12 of 32 (s01, s02, s03, s05, s07, s08, s09, s11, s15, s16, s22, s25)
- **Origin:** Unofficial Kaggle mirror
- **Kaggle URL:** https://www.kaggle.com/datasets/harshilgupta28/deap-dataset
- **Uploader:** harshilgupta28
- **Download date:** 2026-11-16
- **Status:** Replaced by mirror 2 on 2026-11-17 on explicit instruction. Archive kept at project root as archive_DEAP_v1.zip.

## Mirror 2 (current -- in bronze/DEAP/)

- **File name:** archive_DEAP_V2.zip
- **File size:** 2,931,827,475 bytes (approximately 2.73 GB)
- **SHA-256:** c67587d95c355d8c87aee6177a3827ede3656d0002c1b697c35be3e60a0576b7
- **Participants:** 32 of 32 (complete)
- **Origin:** Unofficial Kaggle mirror
- **Kaggle URL:** https://www.kaggle.com/datasets/manh123df/deap-dataset
- **Uploader:** manh123df
- **Download date:** 2026-11-16
- **Status:** Current. Extracted to bronze/DEAP/deap-dataset/ on 2026-11-17.

## Official dataset

- **Official dataset page:** http://www.eecs.qmul.ac.uk/mmv/datasets/deap/
- **Citation:** Koelstra, S. et al. (2012). DEAP: A Database for Emotion Analysis using Physiological Signals. IEEE Transactions on Affective Computing, 3(1), 18-31.
- **Access:** Official access requires a data access agreement with the dataset creators at Queen Mary University of London. Official access form: http://www.eecs.qmul.ac.uk/mmv/datasets/deap/readme.html

## Cross-mirror comparison (overlapping participants)

For the 12 participants present in both mirrors, the physiological `data` arrays
(shape 40 x 40 x 8064) are byte-for-byte identical. The `labels` arrays differ.

The 16-byte file size difference (v1: 103,220,683 bytes; v2: 103,220,699 bytes per file)
is a pickle framing artifact: v1 files use pickle protocol 2, v2 files use pickle protocol 4.

### Label discrepancy

The label audit (deap/src/label_audit.py, output deap/reports/deap_label_audit.json)
compared both mirrors against the reference ratings in
bronze/DEAP/deap-dataset/Metadata/participant_ratings.xls.

Matching method: participant_ratings.xls rows are matched to .dat label arrays
by sorting each participant's XLS rows by Experiment_id (1-40); dat labels[i]
corresponds to XLS row with Experiment_id == i+1.

Results:

| Mirror | Participants | Total entries | XLS match | Inverted (9 - XLS) | Other |
|---|---|---|---|---|---|
| v1 | 12 | 1,920 | 1,920 (100%) | 0 | 0 |
| v2 | 32 | 5,120 | 4,242 (82.9%) | 878 (17.1%) | 0 |

"Inverted" means mirror_value == 9.0 - xls_value within 1e-4 tolerance. This
affects only the Valence and Arousal dimensions, never Dominance or Liking.
All 32 participants in v2 have at least some inverted entries (range: 2 to 48
per participant). The inversions cause 163 label values to fall outside the 1-9
SAM scale in v2 (minimum possible inverted value is 0.0 when XLS = 9.0).

**Conclusion:** Mirror v1 matches the XLS metadata exactly. Mirror v2 has
inverted Valence and Arousal labels for 17.1% of entries. The source of the
inversion in v2 is not explained by any file in the archive. No label values
have been modified in this project; this discrepancy is recorded only.

## Pickle safety inspection

Both mirrors: inspected with `pickletools.dis()` before loading.
- v1 (pickle protocol 2): GLOBAL opcode references only `numpy.core.multiarray._reconstruct`, `numpy.ndarray`, `numpy.dtype`.
- v2 (pickle protocol 4): STACK_GLOBAL opcode references only `numpy.core.multiarray._reconstruct`, `numpy.ndarray`, `numpy.dtype`.

No stdlib, OS, subprocess, eval, exec, or any other class found in any file.
Files loaded with a restricted unpickler whose `find_class` allow-list covers
only those three numpy types. Latin-1 encoding required (Python 2-era pickles).

## Notes

Both archives are unofficial mirrors. Neither has been verified against a checksum
published by the official dataset authors. The discrepancy in the label arrays
between mirrors cannot be resolved without consulting the official dataset
documentation or contacting the dataset creators. Do not redistribute either
archive. Treat all files as read-only.
