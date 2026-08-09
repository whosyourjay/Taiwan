# Taiwan university admission difficulty

Ranks Taiwanese universities and departments by how hard they are to get into as
a bachelor student. Nothing here reflects research output or reputation.

Covers both admission systems, on one scale: 141 institutions, 3,040 departments.

## Admission paths

For scale, 114學年度 had 121,181 學測 takers and 66,311 統測 takers; 39,190
of the academic-track students also took 分科測驗.

| Path | How it works | 114學年度 national scale | Coverage here |
| --- | --- | ---: | --- |
| 一般大學 分發入學 | 指考 + ranked preferences | 32,497 admitted | Rank + denominator: full, 108–114 |
| 一般大學 繁星推薦 | High-school rank + 學測; school nomination | 14,543 admitted | Rank: 64 schools, 110–111; denominator: full, 108–114 |
| 一般大學 申請入學 | 學測 screen, then review/interview | 44,025 admitted | Rank: 62 schools, 110–111; denominator: full, 108–114 |
| 一般大學 其他管道 | Special selection and school-run admissions | 5,087 admitted | Not handled |
| 四技二專 聯合登記分發 | 統測 score + ranked preferences | 16,229 admitted | Rank: full general intake; denominator: full, 108–114 |
| 四技二專 甄選入學 | 統測 screen, then review/interview | 24,426 admitted | Denominator only: full, 108–114 |
| 四技日間部 申請入學 | 學測 screen, then review/interview | 5,490 admitted | Not handled |
| 四技二專 技優保送 / 甄審 | Competition results; direct or screened placement | 228 / 3,078 admitted | Not handled |
| 四技二專 特殊選才 | Skills, experience, or talent | 512 admitted | Not handled |
| 科技校院 繁星推薦 | School recommendation + rank | 1,976 admitted | Not handled |

“Rank” coverage means a row supplies evidence about a named school and
department. “Denominator” coverage means its admitted seat is counted in the
national percentile cohort. The repository contains named rank evidence for
48,394 general-intake admissions across the two fully collected routes in 114.
The official denominator additionally preserves the unparsed routes, schools,
and rejected rows without attributing their seats to an entity.

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
application_group_en]] score years last_year active seats_avg system men women
pct_women`

`school_en`, `dept_en` and `application_group_en` are intentionally blank join
slots. English-name mappings are maintained outside this repository.

- `score` — 0-100. Each admission path is scored on a common admitted-seat
  axis whose denominator includes all official admissions in the five modeled
  routes, then entity path scores are averaged by their usable annual seats.
- `years` — number of distinct admission years represented by any covered path.
- `seats_avg` — the sum of average annual seats in each collected admission path.
- `active` — 1 if it still admitted students in 114.
- `system` — `uac` (一般大學), `tech` (科技大學), or `both` where the entity
  admits through each.
- `men`, `women`, `pct_women` — enrolled bachelor headcount, blank where 教育部
  has no matching department and for every application group. See Auxiliary
  gender join below.

## Method

`rank_uac.py` performs four transformations, then aggregates by admission path.

### 1. Group departments

The application-group output keeps each source 系組 name from the two fully
collected final-cutoff routes. 繁星 and 個申 do not enter it because their group
boundaries do not consistently match 分發. `deptname.py` then removes group,
track, campus, funding and quota qualifiers for the department output. It also
treats `系` and `學系` as the same name and reports the spelling attached to the
most admitted seats. This collapses 4,489 source names from 分發 and 聯登 into
3,040 institution-department pairs.

### 2. Compute a row basis

For a weighted exam formula, the parsers first compute

    norm = cutoff / sum(weight_i * maximum_i)

Set `maximum_i` to 100 for 指考, 統測 and 術科, and to 60 for the 學測 and
分科採計 scores used by 分發 from 111 onward. The
[111 UAC guide](https://www2.uac.edu.tw/111data/111recruit.pdf) specifies the
60-level academic scale and the 100-point 術科 scale.

Each admission path then supplies one ordering value, called its `basis`:

| Path | `basis` before curving |
| --- | --- |
| 分發入學 | CEEC equal-subject percentile; calibrated `norm` fallback for 術科 rows |
| 聯合登記分發 | `norm` |
| 繁星推薦 | Negative high-school rank percentile; round 1 and 2 values use admitted-seat weights |
| 個人申請 | Last active screening total divided by `15 * number_of_subjects` |

For 分發 subject `i`, let `Q_i(p)` denote CEEC's score at candidate percentile
`p`. The solver assumes the marginal admittee has the same `p` in every selected
subject and finds

    sum(weight_i * Q_i(p)) = cutoff

CEEC publishes marginal rather than joint subject distributions, so the cutoff
cannot identify a separate percentile for each subject. The solver covers
12,225 of 12,656 分發 rows (96.6%). For the 431 rows containing 術科,
`ceec_score.calibrate_fallbacks` preserves the row's seat-weighted position under
`norm` within its year and maps that position onto the supported CEEC values.

繁星 excludes 第八類學群 because its tables report pre-interview screening,
not admission. 個申 uses the last screening order that fired, drops blank names
and `norm > 1` OCR failures, and keeps only same-year department matches to
分發. Its seat weight equals quota times the national fill rate (88.7% in 110;
81.6% in 111), not an observed department admission count.

### 3. Convert each path to seat percentiles

For row `r` within one `(year, path)` group `G`:

    pct(r) = 100 * (seats below r + 0.5 * seats tied with r) / seats in G

This transform uses admitted seats, gives ties the same midpoint, and removes
the exam's absolute level for that year.

### 4. Bridge paths

Weighted least squares matches the same `(year, school, department)` across two
paths. Each match receives the smaller of its two seat counts as weight.

| Source path | Target | Fit |
| --- | --- | --- |
| 聯合登記分發 | 分發入學 | `uac = -15.11 + 0.7433 * tech` (`R² = 0.412`, `n = 315`) |
| 繁星推薦 | Provisional UAC rank | `rank = -54.85 + 1.5107 * star` (`R² = 0.709`, `n = 1,571`) |
| 個人申請 | Provisional UAC rank | `rank = -12.02 + 1.0870 * apply` (`R² = 0.713`, `n = 1,078`) |

The tech bridge uses `norm`-ordered percentiles on both sides. Replacing its UAC
target with the CEEC order raises leave-one-school-out error from 11.60 to 12.63
points, so CEEC changes UAC row order only after fitting this bridge.

The provisional base rank curves CEEC-ordered 分發 rows and bridged 聯登 rows
together within each year. 繁星 and 個申 then map onto that fixed reference.
Only this bridge fit depends on matched rank evidence; missing seats do not.

### 5. Restore missing seats to the denominator

`admission-totals.tsv` records actual national admissions for 分發, 聯登,
繁星, 個申 and 四技二專甄選 in every year 108–114. For year `y` and path `j`,
the unranked residual is

    missing_yj = official_admits_yj - seats in usable rows_yj

“Usable” is deliberately late in the pipeline: a row rejected by OCR checks or
the department join is missing here too. The final yearly curve is

    score(r) = 100 * (anonymous seats_y + ranked seats below r
                      + 0.5 * ranked seats tied with r)
                     / (anonymous seats_y + all ranked seats_y)

where `anonymous seats_y = sum_j missing_yj`. These seats sit below the
top-tail evidence, which is the only placement needed for the intended top-10%
comparison. They receive no score, create no school or department row, and do
not enter `seats_avg`. As more schools and years are parsed successfully, seats
move automatically from the anonymous residual to their inferred positions
without changing the national denominator.

### 6. Aggregate paths

For entity `e` and path `j`, use all collected rows to compute

    path_score_j = sum(seats_r * score_r) / sum(seats_r)
    annual_seats_j = sum(seats_r) / number_of_years_j
    score_e = sum(annual_seats_j * path_score_j) / sum(annual_seats_j)

`seats_avg` equals `sum(annual_seats_j)`. This gives intake size weight without
giving extra weight to a path merely because the repository contains more years
of it.

### Auxiliary gender join

Gender does not enter `score`. `gender.py` joins the downloaded MOE day-division
bachelor headcounts on the same normalised department names and sums all four
cohorts. It matches 2,407 of 3,040 departments and 2,155 of 2,283 departments
active in 114.

## Caveats

- **The bridge explains under half the variance** (R2 0.42). Every per-school
  slope is positive, and the three schools carrying most of the data agree
  (宜蘭 +0.53, 屏東 +0.48, 師大 +0.58, against a pooled 0.56), but 聯合 gives
  +0.08 and 慈濟 +0.06 on 8 department-years. It rests on 6 universities, of
  which only 臺灣師範大學 reaches the range 臺灣科技大學 occupies, so the top of
  the 科大 ladder is the least certain part. Treat a 科大's position as good to
  roughly ±5 places, not ±1. Averaging over a whole institution's departments
  cancels much of this; single departments do not.
- **Each subject has its own candidate field.** The equal-percentile model
  compares a student with the people who took each selected subject. Those
  populations differ, especially between humanities and science subjects.
- **Anonymous seats are a top-tail approximation.** Unprocessed 繁星, 個申 and
  四技二專甄選 seats count nationally but are placed below the ranked tail. This
  avoids shrinking the top-10% cohort, but scores lower in the distribution are
  not empirical placements of those students. Other admission routes shown in
  the first table remain outside even this denominator.

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
  These counts supply denominator-only seats when rank evidence is unavailable.
- `star/` — 繁星推薦 錄取標準, and `star-cutoffs.tsv` parsed from it.
  Joined rows contribute to `score` as a separate admission path.
- `apply/` — 個人申請 篩選標準 PNGs, and `apply-cutoffs.tsv` OCR'd from them.
  Only validated rows that match a 分發入學 department contribute to `score`.
- `ceec/` — 大考中心 score distributions (級分人數百分比累計表 and friends,
  .xls, back to year 91) for 學測 and 分科測驗. `parse_ceec.py` extracts
  108-114 into `ceec-scores.tsv`; these distributions refine the ordering of
  分發入學 cutoffs as described in Method.
- `tech/tcte-*-scores.pdf` — 統測 成績人數累計表, one-point bands over 42
  subjects. `parse_tcte.py` extracts 108-114 into `tongce-scores.tsv`, matching
  the columns `parse_ceec.py` writes. Collected, but no path uses it yet.
- `tech/jctv-*-xuece-screen.pdf` — 科技校院四年制申請入學 第一階段最低篩選標準,
  the 學測 route by which 科大 admit 高中 students. An alternative bridge, but
  it reports a screening threshold rather than a final cutoff.

## Rebuild

    python3 parse_uac.py     # uac/*-cutoffs.pdf        -> uac-cutoffs.tsv
    python3 parse_tech.py    # tech/union42-*.pdf       -> tech-cutoffs.tsv
    python3 fetch_star.py 110 111   # -> star/,  88 PDFs and 3.6MB
    python3 parse_star.py           # star/*.pdf -> star-cutoffs.tsv, ~6 pages/s
    python3 fetch_apply.py 110 111   # -> apply/, 74 PNGs and 21MB
    python3 parse_apply.py           # OCR apply/*.png -> apply-cutoffs.tsv, ~20s an image
    python3 fetch_ceec.py    # optional, only refreshes ceec/
    python3 parse_ceec.py    # ceec/*.xls -> ceec-scores.tsv
    python3 parse_tcte.py    # tech/tcte-*-scores.pdf   -> tongce-scores.tsv
    python3 rank_uac.py      # all paths, bridge, gender -> rank-*.tsv
    python3 -m unittest

Both CAC fetchers take the schools named in their `WANT` list, or every school
the year lists when that list is empty. `star/` and `apply/` hold the whole-year
download; the eight names still in `fetch_star.py` cut it to a few seconds.

`rank_uac.py` pulls the 教育部 CSV through `gender.py` on first run. The 系組
name normalisation both it and `gender.py` group by lives in `deptname.py`.

Shared by the pipeline: `tsvio.py` reads and writes the tables, `deptname.py`
normalises 系組 names, `gender.py` joins the 教育部 student counts, and
`ceec_score.py` turns a 級分 bar into a share of that exam's takers.

Off to the side, not wired into the rankings: `diagnose.py` prints each path's
score for a fixed sample of departments, and `pool.py` / `fit_pool.py` /
`plot_pool.py` fit the taker densities that would let percentiles from
different exams compare without a linear bridge.

`parse_apply.py` needs tesseract with traditional Chinese:

    curl -L https://github.com/tesseract-ocr/tessdata_fast/raw/main/chi_tra.traineddata \
      -o /usr/local/share/tessdata/chi_tra.traineddata
