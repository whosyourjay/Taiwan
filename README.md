# Taiwan university admission difficulty

Ranks Taiwanese universities and departments by how hard they are to get into as
a bachelor student. Nothing here reflects research output or reputation.

Covers both admission systems, on one scale: 141 institutions, 3,040 departments.

Known limitations and planned work live in `TODO.md`.

## Admission paths

For scale, 114學年度 had 121,181 學測 takers and 66,311 統測 takers; 39,190
of the academic-track students also took 分科測驗.

| Path | How it works | Seats | Our coverage |
| --- | --- | ---: | --- |
| 一般大學 分發入學 | 指考 + ranked preferences | 32,497 | Full, 107–114 |
| 一般大學 繁星推薦 | High-school rank + 學測; school nomination | 14,543 | Full, 108–114 |
| 一般大學 申請入學 | 學測 screen, then review/interview | 44,025 | Top decile, 108–114; full 110 |
| 一般大學 其他管道 | Special selection and school-run admissions | 5,087 | Not handled |
| 四技二專 聯合登記分發 | 統測 score + ranked preferences | 16,229 | Full general intake, 107–115 |
| 四技二專 甄選入學 | 統測 screen, then review/interview | 24,426 | Count only; not scored |
| 四技日間部 申請入學 | 學測 screen, then review/interview | 5,490 | Bridge evidence, 107–114 |
| 四技二專 技優保送 / 甄審 | Competition results; direct or screened placement | 228 / 3,078 | Not handled |
| 四技二專 特殊選才 | Skills, experience, or talent | 512 | Not handled |
| 科技校院 繁星推薦 | School recommendation + rank | 1,976 | Not handled |

The two final-cutoff routes contain 48,394 named admissions in 114. 繁星 and the
top-decile 個申 panel add rank evidence only where a row passes validation and
matches a 分發 department. Every named seat still enters `rank-history.tsv`:
missing ability is imputed, and annual MOE totals calibrate assignable gaps
instead of limiting the ranking weight to rows with readable cutoffs.

National counts are actual admissions from the annual MOE Education Statistics
tables A1-17/A1-18; the [current edition is here](https://stats.moe.gov.tw/files/ebook/Education_Statistics/115/115edu_EXCEL.htm).
Its technical-college table includes additional quotas but excludes admissions
run separately by individual schools, for which it gives no central total. The
broader route lists are maintained by the [大學多元入學升學網](https://nsdua.moe.edu.tw/)
and [技專校院招生策略委員會](https://www.techadmi.edu.tw/edutype.php?type=1).

## Outputs

- `rankings/rank-universities.tsv` — 149 institutions under current names
- `rankings/rank-departments.tsv` — 3,583 (institution, department) pairs
- `rankings/rank-application-groups.tsv` — 4,934 raw 分發/聯登 系組 names before
  department merging
- `rankings/rank-history.tsv` — every 107–115 year × school × department × route,
  with estimated seats and ability plus the method used for each value
- `rankings/ability-universities.tsv` — final school scores under current names,
  with predecessor names in `former_schools`
- `rankings/ability-{departments,groups}.tsv` — the same ability scale below
  school level, retaining each source year's school name
- `rankings/ability-report.html` — a self-contained dark visual report with
  interactive seat, exam, route, program, high-school, and coverage figures
- `figures/` — every generated figure, built by `python3 -m viz`
- `data/high-school-destinations.tsv` — 110 北一女 graduate destinations
- `data/high-school-entry-cutoffs.tsv` — high-school entry cutoffs by district
- `data/cap-grade-distributions.tsv` — 107 national CAP A/B/C category counts

Columns: `rank school school_en [dept dept_en [application_group
application_group_en]] score years last_year seats_avg uac tech star star_eight apply men
women pct_women`

`school_en`, `dept_en` and `application_group_en` use the local
`data/name-english.tsv` cache. Ranking builds never contact a translation
service; `python3 translate_names.py` is the explicit, optional cache refresh.

The ability tables' `years` column counts distinct source years. Their filled
exam columns already show which exam readings contributed.

`rank-history.tsv` retains the institution name used in that year under
`school_year_name` while `school` uses the current name. Its `ability` is the
ranking's calibrated within-year difficulty percentile before multi-year
aggregation; the separate `ability-*.tsv` tables place 110 thresholds on the
age-cohort ability scale. `seats_method`, `seat_scale`, and `ability_method`
distinguish direct rows, MOE quotas, structural zeros, interpolation,
   nearest-year estimates, hierarchical fallbacks, and any national calibration.

`data/high-school-destinations.tsv` uses the columns `year high_school destination
destination_type students reporting_floor graduates source_date`. Filter
`destination_type=university` for the high-school-to-university matrix. The 110
北一女 report names 14 universities receiving at least ten students: 675 of
756 domestic destinations. It retains the other 81 domestic students and all
28 overseas students as grouped rows, so missing university cells remain
censored rather than zero. The destination and admission-path tables both total
784 against 793 graduates; the data therefore records one destination per
admitted graduate, not every offer. It does not affect the rankings.

## High-school entry evidence

Students in the 110 university-admission cohort entered high school in 107.
`data/high-school-entry-cutoffs.tsv` holds published marginal 國中教育會考 entry
scores by district and year, from third-party compilations. Every district scores
its own 超額比序 total, so a score orders schools inside a district and needs that
district's conversion before it compares across districts.

`python3 pool/entry_score.py` supplies those conversions. 基北 scores the plus
marks, so reading it needs one latent ability behind five noisy subject readings,
fitted to the national mark shares and to the joint category counts that say how
often the five agree. Districts scoring only 精熟, 基礎 and 待加強 need no model,
because their total is a function of the published category alone.
`python3 pool/high_school.py` then places each cutoff on the ability scale, on
the order of a hundred schools, as a floor rather than a mean.

繁星 is scored against those schools. `pool/ability.py` reads its class-rank bar
and its 學測 gate as one ability rather than the larger of the two: each school is
cut at whichever bar binds it, and the surviving students are averaged over
schools. Away from the most competitive departments the reading runs high,
because it averages everyone the bars leave eligible instead of the pool a
department actually draws from.

`python3 -m fetch.high_school_entry_audit` reads the official 115 school
directory and inventories entrance-report candidates without search-engine
queries. It searches NSS sites through their public full-text endpoint and
records sitemap availability for the remaining sites.
`python3 -m parse.high_school_entry_reports --plan-only` classifies obvious
metadata and selects ambiguous documents for download. After fetching that
plan, rerun the parser with `--prune` to extract text, write the final
classification, and retain only potential entrance evidence under `sources/`.
It reached the whole directory for a couple of usable entrant distributions, so
the cutoff tables above carry the school evidence instead.

- `score` — 0-100 difficulty percentile among usable rows, combined across
  paths by average annual admitted seats.
- `years` — number of distinct admission years represented by any covered path.
- `seats_avg` — the sum of average annual seats in each collected admission path.
- `uac`, `tech`, `star`, `star_eight`, `apply` — the entity's score within each
  available path. `star_eight` is 第八類醫牙's pre-interview 繁星 screen.
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
| 分發入學 | CEEC equal-subject coordinate; `norm` fallback for 術科 |
| 聯合登記分發 | `norm` |
| 繁星推薦（第一至七類） | class-rank percentile and binding 學測 gates |
| 繁星推薦第八類醫牙 | same measurements; pre-interview screen |
| 個人申請 | National 學測 percentile at the last binding first-stage screen |

   For 分發, let `Q_i(p)` be subject `i`'s CEEC score at percentile `p`, then
   solve

    sum(weight_i * Q_i(p)) = cutoff

   This covers 12,225 of 12,656 rows. It gives an equal-subject quantile
   coordinate, not the percentile of the weighted total: CEEC does not publish
   the joint subject scores needed for that distribution. The 431 術科 rows keep
   their within-year `norm` position. 第八類醫牙 uses its final quota as its
   weight and stays a separate path.

3. Convert the full-cutoff routes to seat-weighted midranks within `(year, path)`:

    pct(r) = 100 * (seats below r + 0.5 * seats tied with r) / seats in G

   Fit one weighted, missing-data component over matched department-years:

    measurement = intercept_measurement + slope_type * component + residual

   The measurements are 分發, 聯登, class rank, three 繁星 gate families, and
   three 個申 subject families. Repeated gates within one family collapse to its
   strictest bar. Each type has equal total weight; rows within a type keep seat
   weights. Families share a slope within each path and keep separate
   intercepts. Alternating least squares fits the component and all lines
   together. A row then uses its own calibrated measurements. This keeps
   distinct application-group cutoffs distinct in the output.

   Fit only department-years that link at least two paths; one-path rows cannot
   calibrate a relationship. Current fit: 37,755 observations across 9,700
   department-years and nine measurements; R² .876. Leave universities out,
   compare each held path with its companion paths, and get RMSE .546 component
   standard deviations.

4. Complete the annual department-route panel before aggregation. Raw allocation
   rows supply seats even when their cutoff failed validation. MOE 表7-2 supplies
   initial 115 route quotas. UAC's 107–115 post-return workbooks provide annual
   capacity; completed years retain their stronger actual admission counts, while
   the workbook replaces 115 分發入學. Returned seats come out of 個人申請 first as an explicit
   estimate. A missing row in a complete source is zero; a gap in partial
   coverage is interpolated between the same department-route's surrounding
   years or carried from its nearest year. Ability uses the same series first,
   then department, school, route-year, and national fallbacks. Finally, published
   route totals calibrate the imputed cells where the panel has candidate
   departments for the residual; otherwise the national gap stays unassigned
   rather than altering a published department count. Every factor is retained
   in the output.

    score_e = sum(year_route_seats * year_route_ability) / sum(year_route_seats)
    seats_avg_e = sum(year_route_seats) / number_of_active_years

   Thus a route with seats but no readable score contributes through an explicit
   ability estimate rather than disappearing from both numerator and denominator.
Gender also does not affect `score`; `rank/gender.py` joins MOE bachelor counts on
normalized department names and matches 2,500 of 3,583 rows.

## Ability pool

`python3 -m pool.ability` scores every department by the ability its own
thresholds imply, and is the live model. It reads each exam's curve off the
ranking rather than fitting a density. Every admit takes one seat, so walking
`rankings/rank-departments.tsv` from the best department down and adding up seats
says where a department's admits sit in the pool. Its published cutoff already
says where its marginal admit sits among its own exam's takers, and the two
together are one point on that exam's curve. `pool/tiling.py` pools those points
at each distinct bar, makes the result fall with isotonic regression, and fits a
shape-preserving cubic through ten seat-weighted knots.

The axis runs over the distinct current students who sat 學測 or 統測 rather than
over the seats in hand. `assessment-pool.tsv` estimates that union directly;
指考 sits inside it. Cross-country consumers can place the resulting percentile
on an age cohort with the assessment-pool/population transform.

We hold every 分發 seat but only three quarters of 個申 and a fifth of 四技甄選.
Left alone those missing seats would all sit at the bottom of the axis, so
`path_scales` lifts each path's held seats onto its published intake from
`data/admission-totals.tsv`. `python3 -m pool.coverage` prints that comparison
path by path. What remains below the weakest department is the part of the
assessment pool holding no placeable seat.

`python3 -m pool.percentile YEAR SUBJECTS SCORE` runs one 學測 total through the
same two steps a department's cutoff goes through: the published distribution
says what share of takers it beats, and that exam's curve says what that share is
worth in the pool. A candidate sitting exactly on a bar counts as the middle of
everyone who scored it, which is the convention `rank.ceec_score.midrank_top` applies
to department bars and 繁星 gates alike.

## Experimental test-pool fit

The tiling above superseded this. `pool/complement.py` still holds the density
fit, and nothing in the ability pool calls it.

`python3 pool/fit.py` puts 學測, 統測, and 指考 on one original-cohort
percentile axis for 110. Each exam has an independent three-segment continuous
linear count density `q_e(x)`. Students may take any subset of the exams, so
the densities do not partition the cohort and need not sum to anything.

統測 is three exams here rather than one. Its 共同科目數學 comes in papers
數學(A)(B)(C)(S), one per 群, and nobody sits two, so a percentile inside 統測
as a whole is a percentile inside a population that never sat together. The
paper each 群 sits is not published in these tables; it is the assignment whose
群 sizes reproduce all four paper totals in 108, 109 and 110 at once, within 55
candidates of about 90,000, and `tests/test_tcte.py` holds it to that. 數學(S)
ran to 110 and its 群 sat 數學(A) after, so those two share a pool. That leaves
`tongce_a` (家政, 衛護, 藝術), `tongce_b` (商管, 外語, 餐旅, 設計, 農業, 食品,
水產, 海事) and `tongce_c` (機械, 動力機械, 電機電子, 土木建築, 化工, 工程管理).

For exam `e`, its density integrates to the observed number of test takers
`N_e`:

    integral_0^1 q_e(x) dx = N_e

A published threshold gives the fraction `p` of that exam's takers above it.
The conversion finds the original-cohort percentile `x` satisfying

    integral_x^1 q_e(u) du = p * N_e

The fit minimizes seat-weighted disagreement in `x` where the same department
has thresholds from two exams. It uses 1,171 學測–指考, 48 統測–指考, 594
學測–統測, and 390 統測–統測 threshold pairs. That last kind is what the split
buys: a department admitting from two 群 publishes two cutoffs against two
different papers, which ties the three vocational densities to each other
directly. Splitting also raises the 學測–統測 count from 419, because those two
cutoffs used to average into one bar. On the same rows, the bridge the split
targets improves — 學測–統測 disagreement falls from 14.59 to 13.88 points —
while 學測–指考 gives up a little, 6.95 to 7.16, and the overall mean rises from
8.20 to 8.44 on a pair set that is now a third larger and includes the harder
statistics. The 學測–統測 pairs include 110 四技日間部申請入學: the cutoff report
supplies a weighted 學測 screen and the program workbook supplies its subject
weights and quota. Of 518 joined rows, 441 have a binding screen and carry most
of that bridge. They are bridge evidence only, not final admission cutoffs and
not an added ranking path.

Each density is a linear spline over three segments, and normalising it to its
taker count spends one of the four ordinates, so the five exams carry 15 shape
parameters between them. 指考 is held under 學測 at every ability rather than fit
free, reflecting that it only sits students who already took 學測. Each exam's
density is also capped at the
academic-plus-vocational cohort size; otherwise an unconstrained fit can place
more test takers at one ability level than there are students. On all current
thresholds, direct percentile transfer has 18.63 mean absolute disagreement and
the constrained linear fit has 8.44 points.

`python3 pool/fit.py` reports the fit and writes `figures/pool-densities.png`. The left
panel shows the five count densities and the right panel shows their conversions
from within-exam rank to original-cohort percentile. `python3 -m pool.plot`
redraws the PNG without the text report.

## Experimental noisy-measurement fit

Everything above reads a bar as a place: clear it and you hold that ability.
`python3 -m pool.factor` relaxes that. Ability is standard normal over the
cohort and a measurement is `M = λ A + sqrt(1 - λ²) ε`, so at `λ = 1` the two
readings agree and below it the students at a bar are a mix of ability and luck.
Participation is unchanged and still carries a density per exam.

繁星 is what makes `λ` identifiable, which is why this fit reads it and the
density fits do not. It publishes a class-rank bar and a set of 學測 檢定 gates
for the same admitted group, and the rate at which a stricter gate buys a looser
rank bar is fixed by the correlation between the two measurements. Reshaping a
density moves each bar's implication on its own and cannot touch that trade-off.
Of 2,037 一至七類 rows with a rank bar, all but 7 carry a gate, and gate
severity still varies by 1.51 nats once the rank bar is known.

Conditional independence given ability makes every quantity here one integral
over ability. The cost is squared disagreement over the variance of the levels
it produced, because shrinking every `λ` at once pulls the levels together and
would otherwise buy agreement for nothing.

On 4,752 pairs the loadings come out 指考 0.999, 學測 0.993, 在校排名 0.944 and
統測 0.853, with 8.14 points of disagreement left. Splitting 統測 is what moves
that loading: three pools tied by departments admitting through two 群 give the
fit somewhere to put the vocational disagreement other than everyone's ability.
The fit does recover a planted loading on generated bars, so these numbers are
the data talking, not the estimator.

`python3 -m pool.diagnose` prints the same fit department by department, each one
read twice: once with every bar exact, once under the fitted loadings. Across
2,432 departments the loadings move a level by 1.05 points on average and 10.03
at most, and mean disagreement between a department's paths falls from 13.52
points to 12.95. It also ranks what the 檢定 gates add to a 繁星 rank bar, which
reaches 19.2 points where a loose rank bar sits behind strict gates. That lift is
the evidence the loadings are fitted from.

## Sources

### Parsed coverage

This is coverage in the parsed inputs, not the range a publisher may hold. Full
means the central table was parsed for all schools or programs it reports;
partial means we collected only named schools or districts.

| Use | Publisher and table | Years | Coverage |
| --- | --- | --- | --- |
| Ranking | UAC 分發入學 final cutoffs | 107–114 | Full; 1,720–1,885 admitted 系組 per year |
| Ranking | JCTV 四技二專聯合登記分發 final cutoffs | 107–115 | Full general intake; 2,013–2,713 admitted 系科組 per year |
| Ranking | CAC 繁星推薦 standards | 108–114 | Full; 2,916–3,045 program rows per year |
| Ranking | CAC 個人申請 first-stage screens | 108–114 | Top seven current universities longitudinally; full 110 |
| Ranking and pool | CEEC 學測 native distributions | 95–115 | Five-subject totals through 107; subject or exact combination tables from 107 |
| Ranking and pool | CEEC 指考 / 分科 distributions | 107–115 | Raw-score subjects in 107–110; 60-level subjects in 111–115 |
| Ranking | CEEC 學測使用於分發入學 distributions | 111–115 | Full published subject tables |
| Ranking and pool | TCTE 統測 score distributions, report B2 | 108–114 | Full published subject tables |
| Pool bridge | JCTV 四技日間部申請 first-stage report + rules | 107–114 | 4,704 joined program-years; one 112 row does not join |
| Coverage audit | MOE annual admissions tables A1-17/A1-18 | 108–114 | Five route totals per year |
| Seat completion | MOE 表7-2 approved department intake by route | 115 | 1,600+ department rows; parsed and reconciled to school totals |
| Ranking labels | MOE university department student counts | 113 | Full file; gender columns only |
| High-school model | MOE national CAP mark/category distributions | 107 | Full national distribution |
| High-school model | Published CAP entry cutoffs | 107; 114 | Partial: 52 基北 schools; 157 schools in six districts |
| High-school model | MOE high-school roll and graduate counts | 103–114 | 518–529 schools per year |
| Auxiliary | 北一女 graduate destinations | 110 | One school; grouped cells remain censored |
| Collection infrastructure | MOE 免試入學 district roster | 115 | All 15 districts; it supplies hosts, not school scores |

The 115 high-school website-document inventory is a collection audit, not a
model input, so its 613 candidates are not counted as source coverage here.

一般大學, 分發入學 (學測 + 分科測驗). 各系組最低錄取標準及錄取人數一覽表:

    https://www2.uac.edu.tw/107data/107_02.pdf
    https://www2.uac.edu.tw/{year}data/{year}_04.pdf            # 108-114

科技大學, 四技二專聯合登記分發 (統測). 各校系科組學程錄取總成績統計表:

    https://www.jctv.ntut.edu.tw/downloads/{year}/union42/{year}_up01.pdf

Both are text PDFs, saved by hand as `sources/uac/{year}-cutoffs.pdf` and
`sources/tech/union42-{year}-cutoffs.pdf`.

一般大學, 繁星推薦 (學測 + 在校學業成績全校排名百分比). 各校系錄取標準一覽表,
split into 第一類至第七類學群 and 第八類學群 (medicine):

    https://www.cac.edu.tw/cacportal/star_his_report/{year}/{year}_result_standard/{one2seven,eight}/{code}/{year}Standard_{code}.pdf

Text PDFs in fixed columns. All listed schools for 108–114 are cached in
`sources/star/` and parsed into `data/star-cutoffs.tsv`. See Method.

一般大學, 個人申請 (學測). 第一階段篩選標準一覽表:

    https://www.cac.edu.tw/cacportal/apply_his_report/{year}/{year}_sieve_standard/report/pict/{code}.png

One PNG per school, with every 108–114 source cached in `sources/apply/`. The
score-critical columns are OCR'd for the stable top decile across all seven years;
110 retains the full field. See `docs/apply-ocr.md`.

技專校院入學測驗中心, 統測 成績人數累計表 (open data 報表B2). One PDF a year,
saved by hand as `sources/tech/tcte-{year}-scores.pdf` for 108-114.

科技校院日間部四年制申請入學, 107–114 第一階段最低篩選標準 and the companion
招生學校系(組)、學程 data workbook:

    https://www.jctv.ntut.edu.tw/downloads/{year}/caac/repot_01.pdf
    https://www.jctv.ntut.edu.tw/downloads/{year}/caac/{year}_caac_minute.{xls,xlsx}

北一女中 110 學年度畢業生大學校系錄取人數統計表, in the 111 school-day
handbook, pages 16–17:

    https://www.fg.tp.edu.tw/wp-content/uploads/doc/curricula/111%E5%AD%B8%E6%A0%A1%E6%97%A5%E6%89%8B%E5%86%8A.pdf

國中教育會考, 107 national achievement-category counts:

    https://www.moe.gov.tw/News_Content.aspx?n=9E7AC85F1954DDA8&s=A72AAFB92D320802&sms=169B8E91BB75571F

基北區, 107 historical high-school cutoffs (third-party compilation):

    https://www.tkbgo.com.tw/schoolZone/university/article/toDetail?article_id=1905

教育部統計處, 大專校院各校科系別學生數, for the gender columns:

    https://stats.moe.gov.tw/files/detail/{year}/{year}_students.csv   # 110-113

Downloaded inputs and auxiliary tables:

- `sources/uac/` and `sources/tech/union42-*.pdf` — the two 分發 cutoff tables above, next to the
  gzip-compressed `pdftotext -layout` dump each parser caches on first run.
- `data/admission-totals.tsv` — actual 108–114 admissions from the annual MOE
  Education Statistics tables A1-17 (editions 109–114) and A1-18 (edition 115).
  The ranking command reports gaps and uses the totals to calibrate annual seat estimates.
- `sources/moe/moe-115-quota.pdf` — MOE 表7-2 department intake split by route;
  `data/university-quotas.tsv` is the reconciled 115 allocation table.
- `sources/uac/{107..115}-count.xlsx` — UAC's post-return annual program
  capacities; `data/uac-seats.tsv` reconciles each workbook to its published total
  and supplies full official names to the cutoff parser.
- `sources/star/` — 繁星推薦 錄取標準, and `data/star-cutoffs.tsv` parsed from it.
  Joined rows contribute to `score` as a separate admission path.
- `sources/apply/` — 個人申請 篩選標準 PNGs, and `data/apply-cutoffs.tsv` OCR'd from them.
  Only validated rows that match a 分發入學 department contribute to `score`.
- `sources/ceec/` — 大考中心 score distributions (級分人數百分比累計表 and friends,
  .xls, back to year 91) for 學測 and 分科測驗. `parse.ceec` extracts
  the usable 95–115 tables into `data/ceec-scores.tsv`; these distributions refine the ordering of
  分發入學 cutoffs as described in Method.
- `sources/tech/tcte-*-scores.pdf` — 統測 成績人數累計表, one-point bands over 42
  subjects. `parse.tcte` extracts 108-114 into `data/tongce-scores.tsv`. The
  experimental pool model uses it; the ranking bridge still uses `norm`.
- `sources/tech/jctv-{107..114}-xuece-screen.pdf` and the matching
  `rules.{xls,xlsx}` — 科技校院四年制申請入學
  第一階段最低篩選標準 and its per-program weights and quotas. Together they
  produce `data/tech-apply-cutoffs.tsv` for the experimental test-pool fit.
- `sources/high-school/fg-110-destinations.pdf` — 北一女 110 graduate destinations.
  `parse.high_school` preserves both named university rows and grouped remainder.
- `sources/entry/` — the official 107 CAP statistics page and the 107 基北 cutoff page.
  `parse.cap` and `parse.entry` turn them into the two entry-evidence TSVs.

## Layout

- `fetch/` — downloads a source into `sources/`
- `parse/` — turns a downloaded source into a `data/*.tsv`
- `rank/` — scores every path onto one axis and writes `rankings/*.tsv`
- `pool/` — the experimental exam-population and noisy-measurement fits
- `viz/` — every figure, written to `figures/`
- `lib/` — paths, TSV reading and writing, 系組 name normalisation

## Rebuild

Run commands from the repository root. Install Python packages with
`python3 -m pip install -r requirements.txt`; the PDF parsers also require
`pdftotext`.

    python3 -m fetch.uac_seats
    python3 -m parse.uac_seats  # UAC 107–115 post-return program capacities
    python3 -m parse.uac       # cutoffs plus workbook names -> data/uac-cutoffs.tsv
    python3 -m parse.tech      # sources/tech/union42-*.pdf -> data/tech-cutoffs.tsv
    python3 -m fetch.star 108 109 110 111 112 113 114
    python3 -m parse.star      # sources/star/*.pdf -> data/star-cutoffs.tsv
    python3 -m fetch.apply 108 109 110 111 112 113 114
    python3 -m parse.apply --top-decile  # bounded, checkpointed OCR panel
    python3 -m fetch.university_quotas
    python3 -m parse.university_quotas  # MOE 115 department-route quotas
    python3 -m fetch.ceec      # optional; refresh sources/ceec/
    python3 -m parse.ceec      # sources/ceec/*.xls -> data/ceec-scores.tsv
    python3 -m parse.tcte      # sources/tech/tcte-*-scores.pdf -> data/tongce-scores.tsv
    python3 -m fetch.assessment_pool
    python3 -m parse.assessment_pool  # -> assessment-pool.tsv for compare/
    python3 -m fetch.tech_apply
    python3 -m parse.tech_apply  # 107–114 四技申請 -> data/tech-apply-cutoffs.tsv
    python3 -m fetch.high_school
    python3 -m parse.high_school  # 110 北一女 -> data/high-school-destinations.tsv
    python3 -m fetch.entry
    python3 -m parse.cap          # 107 CAP categories -> data/cap-grade-distributions.tsv
    python3 -m parse.entry        # 107 基北 cutoffs -> data/high-school-entry-cutoffs.tsv
    python3 -m rank.uac        # all paths, bridge, gender -> rankings/rank-*.tsv
    python3 -m pool.ability    # ability curves -> rankings/ability-*.tsv
    python3 -m pool.tiling     # the curves themselves + the tiling figure
    python3 -m pool.coverage   # seats held against published intake, by path
    python3 -m pool.percentile 103 國英數社自 65   # one 學測 total, ranked
    python3 -m pool.fit        # joint fit report + the density figure
    python3 -m pool.plot       # redraw only the density figure
    python3 -m pool.factor     # loadings from the 繁星 rank-and-gate bars, ~2min
    python3 -m pool.diagnose   # the same fit, department by department, ~2min
    python3 -m viz             # every figure -> figures/
    python3 -m pages.report    # interactive report -> rankings/ability-report.html
    python3 -m unittest

Both CAC fetchers cache the official annual index, every listed source, and a
completion marker. `sources/star/` and `sources/apply/` hold the whole-year downloads.

Fetch commands trust saved sources and manifests, so a warm run makes no network
requests. Discovery-based fetchers accept `--refresh` for an intentional upstream
check; single-file fetchers retrieve only missing targets. Local PDF text caches
can be compacted at a 50% duty cycle with
`python3 -m tools.compress_text_caches`; parsers read the resulting `.txt.gz`
files directly.

`rank/uac.py` pulls the 教育部 CSV through `rank/gender.py` on first run. Both
group departments by the 系組 name normalisation in `lib/deptname.py`, and
`rank/ceec_score.py` turns a 級分 bar into a share of that exam's takers.

Off to the side, `rank/diagnose.py` prints path scores for a fixed department
sample. `python3 -m pool.fit` and `python3 -m pool.plot` fit and draw the experimental
exam-population model, `pool/compare.py` ranks its candidates on held-out
departments, and `pool/factor.py` adds a noise level per measurement, reading
the bars `pool/bars.py` builds. `pool/diagnose.py` is to that fit what
`rank/diagnose.py` is to the rankings.

`parse.apply` needs tesseract with traditional Chinese:

    curl -L https://github.com/tesseract-ocr/tessdata_fast/raw/main/chi_tra.traineddata \
      -o /usr/local/share/tessdata/chi_tra.traineddata
