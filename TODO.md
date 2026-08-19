# TODO

Each row names remaining work, not something already in the repository. The
first column is impact and the second is labour; H = high, M = medium, and L = low.

| Impact | Complexity | deliverable |
| :---: | :---: | --- |
| H | L | Define a cohort that includes non-enrollees and no-exam students; reconcile its counts with 學測、統測, and 分科 participation and propagate the resulting uncertainty into pool percentiles. |
| M | M | Make the factor fit converge reliably, then run loading-sensitivity checks across density shape, overlap, and starting values. |
| M | H | Re-run pool-model selection on additional years; retain the simplest density model that generalizes across both departments and years. |
| M | L | Publish a screen-evidence table for 個申、統測甄選, and 第八類 with screeners, final seats, allocation rates, and matched department-years. |
| H | H | Test a screen-to-admission correction against that table; keep the current plain-threshold treatment unless it improves a held-out check. |
| L | H | Expand the high-school-to-university destination matrix beyond 北一女, recording coverage and censored cells. |
| M | H | Add school effects to the existing noisy-measurement model for 繁星 and class rank, calibrated from the destination matrix, and report their ranking impact. |
| M | M | Compare correlation-adjusted multi-subject coordinates for 分科 with the current single-subtest coordinate; adopt one only after a ranking and validation diff. |
| L | M | Define comparable 術科 exam groups, rerank within group, and audit the change against the current `norm` fallback. |
| M | L | Classify 其他管道 seats into competition, sports, 特殊選才, and residual categories; state which categories enter the denominator. |
| L | L | Replace the 個申 OCR source |
| L | L | Add diagrams for the year-specific pipeline and the screen-to-admission model when those models are ready. |

Defer
| M | L | Extend the year-specific ranking and the required 學測-path collection to every covered year, then aggregate the yearly scores only at the end. |
| L | L | Build a frozen 110-only seed ranking and make the tiling pipeline use it instead of the current 108–114 aggregate ranking. |
| L | H | Promote the existing 110 tiling/ability prototype into a candidate published ranking: include every 110 seat, fit its curves from final-cutoff routes only, score each route through those curves, and compare it with the current ranking. |

## Deferred until new data exists

- Do not infer an exact percentile or entering-school median from a plus-mark CAP cutoff. Revisit only after obtaining district intake counts, a choice model, and suitable joint score data.
