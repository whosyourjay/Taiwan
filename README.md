# Taiwan university admission difficulty

Ranks Taiwanese universities and departments by how hard they are to get into as
a bachelor student. Nothing here reflects research output or reputation.

Covers both admission systems, on one scale: 141 institutions, 3,040 departments.

## Admission paths

For scale, 114學年度 had 121,181 學測 takers and 66,311 統測 takers; 39,190
of the academic-track students also took 分科測驗.

| Path | How it works | 114學年度 national scale | Coverage here |
| --- | --- | ---: | --- |
| 一般大學 分發入學 | 指考 + ranked preferences | 32,497 admitted | Full, 108–114 |
| 一般大學 繁星推薦 | High-school rank + 學測; school nomination | 14,543 admitted | 64 schools, 110–111 |
| 一般大學 申請入學 | 學測 screen, then review/interview | 44,025 admitted | 62 schools, 110–111 |
| 一般大學 其他管道 | Special selection and school-run admissions | 5,087 admitted | Not handled |
| 四技二專 聯合登記分發 | 統測 score + ranked preferences | 16,229 admitted | Full general intake, 108–114 |
| 四技二專 甄選入學 | 統測 screen, then review/interview | 24,426 admitted | Count only; not scored |
| 四技日間部 申請入學 | 學測 screen, then review/interview | 5,490 admitted | Not handled |
| 四技二專 技優保送 / 甄審 | Competition results; direct or screened placement | 228 / 3,078 admitted | Not handled |
| 四技二專 特殊選才 | Skills, experience, or talent | 512 admitted | Not handled |
| 科技校院 繁星推薦 | School recommendation + rank | 1,976 admitted | Not handled |

The two final-cutoff routes contain 48,394 named admissions in 114. The partial
繁星 and 個申 samples add rank evidence only where a row passes validation and
matches a 分發 department. `admission-totals.tsv` audits missing coverage; those
counts do not affect `score` yet.

National counts are actual admissions from the annual MOE Education Statistics
tables A1-17/A1-18; the [current edition is here](https://stats.moe.gov.tw/files/ebook/Education_Statistics/115/115edu_EXCEL.htm).
Its technical-college table includes additional quotas but excludes admissions
run separately by individual schools, for which it gives no central total. The
broader route lists are maintained by the [大學多元入學升學網](https://nsdua.moe.edu.tw/)
and [技專校院招生策略委員會](https://www.techadmi.edu.tw/edutype.php?type=1).

## Outputs

- `rank-universities.tsv` — 141 institutions (122 still admitting in 114)
- `rank-departments.tsv` — 3,040 (institution, department) pairs
- `rank-application-groups.tsv` — 4,489 raw 分發/聯登 系組 names before
  department merging

Columns: `rank school school_en [dept dept_en [application_group
application_group_en]] score years last_year seats_avg uac tech star apply men
women pct_women`

`school_en`, `dept_en` and `application_group_en` are intentionally blank join
slots. English-name mappings are maintained outside this repository.

- `score` — 0-100 difficulty percentile among usable rows, combined across
  paths by average annual admitted seats.
- `years` — number of distinct admission years represented by any covered path.
- `seats_avg` — the sum of average annual seats in each collected admission path.
- `uac`, `tech`, `star`, `apply` — the entity's score within each available path.
- `men`, `women`, `pct_women` — enrolled bachelor headcount, blank where 教育部
  has no matching department and for every application group. See Auxiliary
  gender join below.

## Method

1. Keep raw 系組 names for the application-group output. Remove group, track,
   campus, funding, and quota suffixes for department and school aggregation.
   Only 分發 and 聯登 have stable application-group boundaries.

2. Compute one ordering value per source row. Parsers first normalize weighted
   cutoffs:

    norm = cutoff / sum(weight_i * maximum_i)

   Use 100 for 指考, 統測, and 術科; use 60 for academic scores in 分發 from
   111. The [111 UAC guide](https://www2.uac.edu.tw/111data/111recruit.pdf)
   defines both scales.

| Path | Row basis |
| --- | --- |
| 分發入學 | CEEC equal-subject percentile; calibrated `norm` fallback for 術科 rows |
| 聯合登記分發 | `norm` |
| 繁星推薦 | `100 - high-school rank percentile` |
| 個人申請 | National 學測 percentile at the last binding first-stage screen |

   For 分發, let `Q_i(p)` be subject `i`'s CEEC score at percentile `p`, then
   solve

    sum(weight_i * Q_i(p)) = cutoff

   This covers 12,225 of 12,656 rows. The 431 術科 rows retain their within-year
   `norm` position. 繁星 excludes pre-interview 第八類 rows. 個申 drops
   non-binding screens and OCR failures. Both partial paths require a same-year
   分發 department match.

3. Convert 分發 and 聯登 rows to seat-weighted midranks within `(year, path)`:

    pct(r) = 100 * (seats below r + 0.5 * seats tied with r) / seats in G

   繁星 and 個申 already use national percentiles. Fit bridges on matched
   `(year, school, department)` rows, weighted by the smaller intake:

| Source path | Target | Fit |
| --- | --- | --- |
| 聯合登記分發 | 分發入學 | `uac = -15.11 + 0.7433 * tech` (`R² = 0.412`, `n = 315`) |
| 繁星推薦 | Provisional UAC rank | `rank = -54.85 + 1.5107 * star` (`R² = 0.709`, `n = 1,571`) |
| 個人申請 | Provisional UAC rank | `rank = -12.02 + 1.0870 * apply` (`R² = 0.713`, `n = 1,078`) |

   Fit the tech bridge on `norm` order; CEEC order raises leave-one-school-out
   error from 11.60 to 12.63. Curve CEEC-ordered 分發 and bridged 聯登 together
   by year, then map 繁星 and 個申 onto that reference.

4. Aggregate each entity within path, then across paths:

    path_score_j = sum(seats_r * score_r) / sum(seats_r)
    annual_seats_j = sum(seats_r) / number_of_years_j
    score_e = sum(annual_seats_j * path_score_j) / sum(annual_seats_j)

   `seats_avg` is `sum(annual_seats_j)`. Years weight rows within a path, not the
   path itself.

`admission-totals.tsv` reports unscored coverage gaps; it does not change the
denominator. Gender also does not affect `score`; `gender.py` joins MOE bachelor
headcounts on normalized department names and matches 2,407 of 3,040 rows.

## Caveats

- The tech bridge has `R² = 0.412` across 315 matched department-years at six
  universities. Treat close 科大 ranks as ties, especially near the top.
- 繁星 and 個申 publish screening-stage evidence, not final admitted cutoffs.
  第八類醫牙 繁星 rows are excluded, and 個申 seat counts use quota times the
  national fill rate. Adding these paths can therefore move well-covered
  non-medical departments relative to medical departments.
- CEEC publishes marginal subject distributions. The 分發 conversion assumes
  one percentile across every selected subject; it cannot recover the admitted
  student's actual subject-score vector.
- Percentiles use only validated named rows. Missing routes and rejected rows
  appear in the coverage audit but not the score denominator.

## Experimental test-pool fit

`python3 -m pool.fit` puts 學測, 統測, and 指考 on one original-cohort
percentile axis for 110. Each exam has an independent three-step count density
`q_e(x)`. Students may take any subset of the exams, so the three densities do
not partition the cohort and need not sum to anything.

For exam `e`, its three bin counts are constrained to sum to the observed number
of test takers `N_e`:

    integral_0^1 q_e(x) dx = N_e

A published threshold gives the fraction `p` of that exam's takers above it.
The conversion finds the original-cohort percentile `x` satisfying

    integral_x^1 q_e(u) du = p * N_e

The fit minimizes seat-weighted disagreement in `x` where the same department
has thresholds from two exams. It uses 1,078 學測–指考, 45 統測–指考, and 38
學測–統測 threshold pairs. Three steps reduce mean disagreement from 19.42 to
9.65 cohort-percentile points. Counts only scale each independent density; they
do not distort its percentile conversion or assert which students took both.

`python3 -m pool.plot` writes `pool-densities.png`. The left panel shows all
three count densities, including the new 統測 curve, and the right panel shows
their conversions from within-exam rank to original-cohort percentile.

## Sources

一般大學, 分發入學 (學測 + 分科測驗). 各系組最低錄取標準及錄取人數一覽表:

    https://www2.uac.edu.tw/{year}data/{year}_04.pdf            # 108-114

科技大學, 四技二專聯合登記分發 (統測). 各校系科組學程錄取總成績統計表:

    https://www.jctv.ntut.edu.tw/downloads/{year}/union42/{year}_up01.pdf

Both are text PDFs, saved by hand as `uac/{year}-cutoffs.pdf` and
`tech/union42-{year}-cutoffs.pdf`.

一般大學, 繁星推薦 (學測 + 在校學業成績全校排名百分比). 各校系錄取標準一覽表,
split into 第一類至第七類學群 and 第八類學群 (medicine):

    https://www.cac.edu.tw/cacportal/star_his_report/{year}/{year}_result_standard/{one2seven,eight}/{code}/{year}Standard_{code}.pdf

Text PDFs in fixed columns. Downloaded for every school listed in 110 and 111,
into `star/` -> `star-cutoffs.tsv`. See Method.

一般大學, 個人申請 (學測). 第一階段篩選標準一覽表:

    https://www.cac.edu.tw/cacportal/apply_his_report/{year}/{year}_sieve_standard/report/pict/{code}.png

One PNG per school, downloaded for the same schools and years into `apply/`
and OCR'd into `apply-cutoffs.tsv`. See Method.

技專校院入學測驗中心, 統測 成績人數累計表 (open data 報表B2). One PDF a year,
saved by hand as `tech/tcte-{year}-scores.pdf` for 108-114.

教育部統計處, 大專校院各校科系別學生數, for the gender columns:

    https://stats.moe.gov.tw/files/detail/{year}/{year}_students.csv   # 110-113

Downloaded inputs and auxiliary tables:

- `uac/` and `tech/union42-*.pdf` — the two 分發 cutoff tables above, next to the
  `pdftotext -layout` dump each parser caches on first run.
- `admission-totals.tsv` — actual 108–114 admissions from the annual MOE
  Education Statistics tables A1-17 (editions 109–114) and A1-18 (edition 115).
  The ranking command reports gaps against these counts; they do not affect scores.
- `star/` — 繁星推薦 錄取標準, and `star-cutoffs.tsv` parsed from it.
  Joined rows contribute to `score` as a separate admission path.
- `apply/` — 個人申請 篩選標準 PNGs, and `apply-cutoffs.tsv` OCR'd from them.
  Only validated rows that match a 分發入學 department contribute to `score`.
- `ceec/` — 大考中心 score distributions (級分人數百分比累計表 and friends,
  .xls, back to year 91) for 學測 and 分科測驗. `parse.ceec` extracts
  108-114 into `ceec-scores.tsv`; these distributions refine the ordering of
  分發入學 cutoffs as described in Method.
- `tech/tcte-*-scores.pdf` — 統測 成績人數累計表, one-point bands over 42
  subjects. `parse.tcte` extracts 108-114 into `tongce-scores.tsv`. The
  experimental pool model uses it; the ranking bridge still uses `norm`.
- `tech/jctv-*-xuece-screen.pdf` — 科技校院四年制申請入學 第一階段最低篩選標準,
  the 學測 route by which 科大 admit 高中 students. An alternative bridge, but
  it reports a screening threshold rather than a final cutoff.

## Rebuild

Run commands from the repository root. Install Python packages with
`python3 -m pip install -r requirements.txt`; the PDF parsers also require
`pdftotext`.

    python3 -m parse.uac       # uac/*-cutoffs.pdf -> uac-cutoffs.tsv
    python3 -m parse.tech      # tech/union42-*.pdf -> tech-cutoffs.tsv
    python3 -m fetch.star 110 111
    python3 -m parse.star      # star/*.pdf -> star-cutoffs.tsv
    python3 -m fetch.apply 110 111
    python3 -m parse.apply     # apply/*.png -> apply-cutoffs.tsv
    python3 -m fetch.ceec      # optional; refresh ceec/
    python3 -m parse.ceec      # ceec/*.xls -> ceec-scores.tsv
    python3 -m parse.tcte      # tech/tcte-*-scores.pdf -> tongce-scores.tsv
    python3 rank_uac.py        # all paths, bridge, gender -> rank-*.tsv
    python3 -m pool.fit        # jointly fit the three independent test pools
    python3 -m pool.plot       # -> pool-densities.png
    python3 -m unittest

Both CAC fetchers take the schools named in their `WANT` list, or every school
the year lists when that list is empty. `star/` and `apply/` hold the whole-year
download; the eight names in `fetch/star.py` cut it to a few seconds.

`rank_uac.py` pulls the 教育部 CSV through `gender.py` on first run. The 系組
name normalisation both it and `gender.py` group by lives in `deptname.py`.

Shared by the pipeline: `lib/tsvio.py` reads and writes the tables, `deptname.py`
normalises 系組 names, `gender.py` joins the 教育部 student counts, and
`ceec_score.py` turns a 級分 bar into a share of that exam's takers.

Off to the side, `diagnose.py` prints path scores for a fixed department sample.
`python3 -m pool.fit` and `python3 -m pool.plot` fit and draw the experimental
exam-population model.

`parse.apply` needs tesseract with traditional Chinese:

    curl -L https://github.com/tesseract-ocr/tessdata_fast/raw/main/chi_tra.traineddata \
      -o /usr/local/share/tessdata/chi_tra.traineddata
