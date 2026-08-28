# 個人申請 OCR plan

This is high-value evidence with high engineering complexity. We should explore
ways to reduce the work and prove accuracy before committing to a full parse.

## Current position

- The official 108–114 corpus is cached locally: 465 university PNGs, 170 MB.
- The original parser took 37.2 seconds on one large university.
- The score-focused prototype took 6.0 seconds on the same image.
- At that rate the full corpus still takes 46.5 minutes, before validation or
  retries. That is too long for a normal rebuild.
- The speedup may trade away accuracy: it uses smaller images, combines columns,
  omits fields we do not currently score, and infers many program names from
  text sources.
- 繁星 is already complete for these years: 20,986 program-year records.

Do not run a full-corpus OCR job until a faster design passes an accuracy gate.

## First deliverable: the top 10%

**Rolled out 2026-08-29.** The eight trusted 110 images matched on all 329
program rows and every score-critical field. The remaining 39 images completed
in 4 minutes 6 seconds; all 52 longitudinal selections are now checkpointed.

Start with the top decile of general universities in the current combined
ranking. Filter that list to universities present in each year's CAC archive,
and carry predecessor names through mergers. The union should be stable across
years rather than selecting a different set from each annual result.

This reduces roughly 465 images to about 45–50. Even the current prototype would
take about five minutes, which can be split into short, cached batches. It also
puts the first effort where combined admission routes matter most: competitive
programs with many applicants and strong 繁星/個申 overlap.

The top-decile result is a product slice, not an accuracy sample. Validation
should also include a few small, low-resolution, and unusual-layout universities
without adding them to the published ranking evidence.

## Treat coverage as three separate products

1. **Source coverage:** the official university image exists locally.
2. **Parsed coverage:** its program rows and seats were read successfully.
3. **Scored coverage:** a valid binding threshold joins to a known program.

The report can show complete source coverage now without implying that every
image has been parsed or scored.

## Preferred parser design

Use a fast-first cascade rather than choosing between a fast parser and an
accurate parser:

1. Read only program code, seats, binding subject combination, and binding score.
2. Infer program names by exact year and CAC code from 繁星 or 分發.
3. Apply automatic validity checks to every row.
4. Re-read only failed cells with the old 4×, isolated-column method.
5. Try a second OCR engine only when both readings remain questionable.
6. Cache each university result by source hash and parser version.

This makes expensive OCR proportional to the ambiguous tail instead of the
whole corpus. It also keeps uncertain names from silently producing scored joins.

## Accuracy gates

Use 110–111 as the existing comparison corpus. A candidate parser should pass
before expanding beyond the top decile:

- Every detected table row yields one record or an explicit rejection.
- Program codes have the expected shape and are unique within a year.
- Seats are positive and annual totals are plausible.
- Scores do not exceed 15 times the number of subjects.
- Subject labels contain only valid GSAT subjects.
- Fast readings reproduce trusted 110–111 fields at an agreed rate.
- Join rates to 繁星 and 分發 do not fall unexpectedly.
- Aggregate seats reconcile with CAC's annual statistics.
- Every fallback and unresolved row is counted by year and university.

## Options to explore before implementation

| Option | Expected value | Complexity | Main question |
| --- | --- | --- | --- |
| Fast OCR plus selective fallback | High | Medium | How small is the ambiguous tail? |
| Exact program-code joins | High | Low | What share avoids name OCR entirely? |
| One OCR pass for several score fields | High | Medium | Does cell accuracy survive batching? |
| Apple Vision or another OCR engine | Medium | Medium | Is it faster and accurate on Traditional Chinese? |
| Find a CAC workbook or data endpoint | Very high | Uncertain | Can OCR be removed altogether? |
| Parse only UAC-joinable programs | High | Medium | Can we identify targets before expensive OCR? |
| Full archival extraction of every column | Low for now | High | Does any planned analysis need those fields? |

The HTML report wrappers expose only PNGs. A focused search for an official
workbook, database response, or downloadable package is still worthwhile because
finding one would dominate every OCR optimization.

## Rollout

1. Define the stable top-decile university set.
2. Benchmark alternative methods on trusted and adversarial images.
3. Set field-level accuracy and fallback thresholds.
4. Parse the top decile in resumable batches under one minute each.
5. Add its screened-route evidence only after the gates pass.
6. Measure how much rankings and combined-route estimates change.
7. Expand coverage only when the measured value justifies the remaining cost.

The full corpus is a later product decision, not the default next step.
