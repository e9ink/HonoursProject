| Dimension                    | Threshold | Before (Bronze)          | After (Gold)                         | Gold passes | Note                                                     |
| ---------------------------- | --------- | ------------------------ | ------------------------------------ | ----------- | -------------------------------------------------------- |
| Completeness                 | 0.0       | 0.0                      | 0.0                                  | True        | 60 intentional removals excluded from rate               |
| Validity: conformance        | 0.0       | 1.20e-07 (60 violations) | 0.00e+00 (0 violations)              | True        | TEMP warm-up artefact (60 samples, all participants)     |
| Validity: plausibility       | <= 0.01   | 1.50e-07 (60 failures)   | 0.00e+00 (0 failures)                | True        | Same 60 TEMP samples; BVP and IBI excluded               |
| Timeliness (partly assessed) | <= 1.0 s  | ~1181 s start gap        | 0.107143 s max residual (15/15 pass) | True        | 5-point method; cannot detect single-device clock offset |
| Consistency                  | N/A       | not measured             | not measured                         | N/A         | intentionally unmeasured                                 |
| Accuracy                     | N/A       | not measured             | not measured                         | N/A         | intentionally unmeasured                                 |
