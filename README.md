# Taiwan university admission difficulty

Ranks Taiwanese universities and departments by how hard they are to get into as
a bachelor student. Nothing here reflects research output or reputation.

Covers both admission systems, on one scale: 141 institutions, 3,040 departments.

## Admission paths

For scale, 114學年度 had 121,181 學測 takers and 66,311 統測 takers; 39,190
of the academic-track students also took 分科測驗.

| Path | How it works | 114學年度 national scale | Coverage here |
| --- | --- | ---: | --- |
| 一般大學 分發入學 | Exam score + ranked preferences | 32,497 admitted | Full: 230,962 admits, 108–114 |
| 一般大學 繁星推薦 | High-school rank + 學測; school nomination | 15,689 quota | Partial: 3,121 admits at 8 schools, 110–111 |
| 一般大學 申請入學 | 學測 screen, then review/interview | 44,025 placed / 50,854 quota | Partial: ~6,932 filled seats at 8 schools, 110–111 |
| 四技二專 聯合登記分發 | 統測 score + ranked preferences | 15,897 admitted | Full: 143,366 admits, 108–114 |
| 四技二專 甄選入學 | 統測 screen, then review/interview | Largest tech channel | Not handled |
| 四技日間部 申請入學 | 學測 screen, then review/interview | — | Not handled |
| 技優、特殊選才、科大繁星、單招等 | Skills, talent, recommendation, or school-specific selection | — | Not handled |

“Coverage here” counts admitted-seat records that actually enter `score`, not
applicants; the two fully covered routes account for 48,394 admissions in 114.
The 申請入學 count is estimated from quota and the national fill
rate because CAC does not publish final department-level admits. The broader
route lists are maintained by the [大學多元入學升學網](https://nsdua.moe.edu.tw/)
and [技專校院招生策略委員會](https://www.techadmi.edu.tw/edutype.php?type=1).

## Outputs

- `rank-universities.tsv` — 141 institutions (122 still admitting in 114)
- `rank-departments.tsv` — 3,040 (institution, department) pairs

Columns: `rank school school_en [dept dept_en] score years last_year active
seats_avg system men women pct_women`

`school_en` and `dept_en` are intentionally blank join slots. English-name
mappings are maintained outside this repository.

- `score` — 0-100. Each admission path is scored on the common admitted-seat
  axis, then the path scores are averaged by their annual admitted seats.
- `years` — number of distinct admission years represented by any covered path.
- `seats_avg` — the sum of average annual seats in each collected admission path.
- `active` — 1 if it still admitted students in 114.
- `system` — `uac` (一般大學), `tech` (科技大學), or `both` where the entity
  admits through each.
- `men`, `women`, `pct_women` — enrolled bachelor headcount, blank where 教育部
  has no matching department. See Gender below.

## Sources

一般大學, 分發入學 (學測 + 分科測驗). 各系組最低錄取標準及錄取人數一覽表:

    https://www2.uac.edu.tw/{year}data/{year}_04.pdf            # 108-114

科技大學, 四技二專聯合登記分發 (統測). 各校系科組學程錄取總成績統計表:

    https://www.jctv.ntut.edu.tw/downloads/{year}/union42/{year}_up01.pdf

Both are text PDFs.

一般大學, 繁星推薦 (學測 + 在校學業成績全校排名百分比). 各校系錄取標準一覽表,
split into 第一類至第七類學群 and 第八類學群 (medicine):

    https://www.cac.edu.tw/cacportal/star_his_report/{year}/{year}_result_standard/{one2seven,eight}/{code}/{year}Standard_{code}.pdf

Text PDFs in fixed columns. Downloaded for 8 schools over 110-111 only, into
`star/` -> `star-cutoffs.tsv`. See 繁星 below.

一般大學, 個人申請 (學測). 第一階段篩選標準一覽表:

    https://www.cac.edu.tw/cacportal/apply_his_report/{year}/{year}_sieve_standard/report/pict/{code}.png

One PNG per school, downloaded for the same 8 schools and years into `apply/`
and OCR'd into `apply-cutoffs.tsv`. See 個人申請 below.

教育部統計處, 大專校院各校科系別學生數, for the gender columns:

    https://stats.moe.gov.tw/files/detail/{year}/{year}_students.csv   # 110-113

Downloaded inputs and auxiliary tables:

- `star/` — 繁星推薦 錄取標準, and `star-cutoffs.tsv` parsed from it.
  Joined rows contribute to `score` as a separate admission path.
- `apply/` — 個人申請 篩選標準 PNGs, and `apply-cutoffs.tsv` OCR'd from them.
  Only validated rows that match a 分發入學 department contribute to `score`.
- `ceec/` — 大考中心 score distributions (級分人數百分比累計表 and friends,
  .xls, back to year 91) for 學測 and 分科測驗. `parse_ceec.py` extracts
  108-114 into `ceec-scores.tsv`; these distributions refine the ordering of
  分發入學 cutoffs as described below.
- `tech/jctv-*-xuece-screen.pdf` — 科技校院四年制申請入學 第一階段最低篩選標準,
  the 學測 route by which 科大 admit 高中 students. An alternative bridge, but
  it reports a screening threshold rather than a final cutoff.

## Method

Each department picks its own subjects and weights (`國x1.50 英x1.25 歷x1.25
地x1.00`), so raw cutoffs are not comparable across departments. Normalise each
cutoff to a fraction of the maximum score attainable under its own formula:

    norm = cutoff / (max_per_subject * sum_of_weights)

`max_per_subject` is 100 for 指考 (through 110) and 60 for 分科測驗 (111 on),
which scales 學測 級分 by 4 onto the same range. 統測 scores 國文, 英文, 數學,
專業(一) and 專業(二) out of 100 each, so 100 throughout.

術科 is the exception, and gets 100 in every year: it is a separate exam under a
separate committee, which the 指考 to 分科測驗 switch left alone. 45 department-
years admit one intake with 術科 in the formula and another without, at the same
department in the same year, and least squares over those pairs puts the 術科
maximum at 100.0 — matching both the 100.6 implied by the 指考 years alone and
the 100 points each 術科考試 item carries. Scoring it at 60 instead pushed nine
music departments past a perfect score.

Aggregation is hierarchical because the paths have different time coverage.
Rows are seat-weighted across the available years within one path. Path scores
are then weighted by that path's average annual seats. Thus seven downloaded
years of 分發 do not outweigh two years of 繁星 or 個申 simply because the
former has more snapshots, while a path with twice the annual intake still has
twice the influence.

### Subject percentiles

The fraction of the maximum treats one point of 國文 like one point of 數學 and
ignores whether a particular year's exam was bunched or spread out. CEEC's
subject distributions let the 分發入學 rows do better. For subject `i`, let
`Q_i(p)` be the score at percentile `p` among that subject's test-takers. The
published cutoff gives only a weighted total, not its subject components, so the
identifiable approximation is to put the marginal admitted student at the same
percentile in every selected subject and solve

    sum(weight_i * Q_i(p)) = cutoff

The resulting `p` replaces `norm` when ordering 分發入學 rows. It uses the
special 60-level 學測-for-分發 tables from 111 onward, not the distribution
of every 學測 candidate. It covers 12,225 of 12,656 rows (96.6%). The remaining
431 contain 術科, whose separate committee does not publish a distribution in
the CEEC files. Those rows retain their old within-year seat position from
`norm`, mapped onto that year's CEEC-percentile scale; raw fractions and
candidate percentiles are never compared directly.

This is necessarily a marginal model: CEEC publishes each subject separately,
not their joint distribution. As an external check, predicting a department's
year from its other years improves from 8.34 to 7.06 admitted-seat percentile
points of mean absolute error. It changes only the ordering within a year; the
reported `score` remains a percentile of admitted seats, not test-takers.

### Curving to percentiles

The subject percentile is still not a cardinal ability scale, and the fallback
`norm` is only a fraction of a maximum. 級分 distributions are lumpy and
asymmetric, and every department's weight vector composes them differently.

So cutoffs are replaced by where they fall among the seats they compete with:
the percentage of those seats won on an easier cutoff, counting seats rather
than departments, with ties sharing the midpoint of the span they cover. Only
the *ordering* of cutoffs survives, which is the part the raw scale gets right.

This happens twice for the established 分發 and 統測 cohort. Each (year,
admission path) is curved against its own field first, which is what puts the
systems on comparable scales for the bridge to fit. Once 統測 is mapped onto
the 分發 axis, that merged pool is curved again; 0 and 100 are the ends of the
whole year's established admitted cohort rather than one system's. 繁星 and
個申 are mapped onto this fixed result but do not enter its reference CDF,
because only two years at eight schools have been collected. Partial collection
therefore cannot move every pre-existing score.

This also subsumes year-levelling: an exam that ran easy lifts every cutoff
that year, and a percentile is invariant to that by construction. Where the
previous fraction-of-maximum scale drifted 0.664 (108) to 0.551 (111) — wider
than the gap between the 1st and 30th university — the curved scale leaves a
residual of ±3 points on a fixed panel of departments, and that residual is
composition rather than difficulty: new departments entering the field move the
established ones. Subtracting it as well changes rank by 0.96 places on average
and leaves 75 of 141 institutions untouched, so it is not worth asserting that
the average established department cannot move.

### Merging admission groups

Admission splits one department into 組 that differ only in weighting formula
(電機工程學系甲組), subject track (統計學系自然組), specialisation
(法律學系司法組), campus (資訊管理學系(桃園校區)), funding (醫學系(公費)) or
quota (戲劇學系(男)). A graduate says 電機系, and 教育部 counts all of them as
one department, so they collapse to one row: everything after the head noun
(系/科/班/學位學程/學院) and before 組, plus any parenthesised qualifier, is
dropped. Across the current 分發 and 聯登 inputs, this reduces 4,489 distinct
source names to 3,040 reported institution-department pairs.

Departments also rename themselves between years, most often between 系 and
學系, which would otherwise split one department's history in two. Names are
grouped ignoring that difference — 73 departments are affected — and each is
reported under whichever spelling admitted the most students.

### Bridging the two systems

統測 and 分科測驗 are different exams sat by different populations, so their
normalised scores are not comparable as they stand.

Seven universities admit through both systems, and 56 departments at 6 of them
match exactly: the same department at the same university, awarding the same
degree, admitting one intake by 統測 and another by 分科測驗. Because the
institution treats the two intakes as equivalent, matching them needs no
assumption about the relative ability of the 高中 and 高職 pools.

Each department contributes one point per year it ran, weighted by the smaller of
its two intakes, since that is what limits how precisely it locates the line.
Least squares over those 315 department-years gives

    uac = -15.11 + 0.7433 * tech      R2 = 0.412

which maps every 科大 onto the 分發入學 axis. Both systems run 0-100 before this
step, each curved against its own field, so the fit is entirely a statement that
the two fields sit at different heights: it puts the 統測 pool below the 分科 one
throughout, the strongest 科大 department landing near the 58th percentile of
分發入學 seats. Values outside 0-100 are possible here and are not clipped — the
second curve, over the merged pool, is what restores the range.

This bridge deliberately retains the fraction-of-maximum ordering on its UAC
side. Substituting the CEEC-refined ordering improves repeatability within UAC
but worsens the bridge's leave-one-school-out error from 11.60 to 12.63 points.
The refinement is applied after the bridge target is fitted, so it cannot move
the whole 科大 field merely by changing which subjects the six bridge schools use.

The fit is applied to 76 科大 that have no 分發入學 data at all, so estimators
were compared by leave-one-school-out error: fit on five of the six bridge
schools, predict the sixth with no school effect available. Seat weighting helps
(0.0535 against 0.0561 unweighted). Collapsing each department to a single
multi-year mean does not (0.0543), and neither does a department-level random
intercept, which is best at 0.0528 but only by tuning a penalty large enough that
it nearly reproduces the fit above. Letting each department keep a free intercept
is worst of all (0.0562), which says the year-to-year variation left inside a
department is mostly noise. Those figures were measured on the
fraction-of-maximum scale, before curving.

### Bridging admission paths

繁星 and 個申 are curved separately for each year, then matched to the final
score of the same 分發 department-year. The two weighted fits are

    score = 86.87 + 0.0988 * star     R2 = 0.205   n = 355
    score = 87.40 + 0.0910 * apply    R2 = 0.179   n = 258

These paths do not redefine the score distribution: they cover only eight
generally selective schools. Once mapped, each route becomes one path estimate
for its school or department. Its weight in the final average is its average
annual admitted seats, not its number of collected years.

### Gender

An independent source: 教育部 counts who is *enrolled*, where the cutoffs record
who was *admitted*. Ratios use total bachelor headcount over all four years,
since pooling cohorts steadies small departments, and cover day division only.

Departments are matched on the same normalised name the ranking groups by, which
is what makes the join work: 教育部 reports the department, 招生 reports its 組.
That matches 2,407 of 3,040 departments. Among departments still admitting in
114 it matches 2,155 of 2,283 (94.4%): 94.5% at public institutions and 94.3%
at private ones. Every institution with no gender data at all had already
closed or merged before 113, the latest year 教育部 publishes.

Spot checks land where they should: 幼兒保育 95% women, 車輛工程 2%, 機械工程 9%,
電機工程 12%, 資訊工程 19%, 護理 80%, and 49.2% women across all matched
departments.

### 繁星

A third exam route, on its own axis. 繁星 ranks applicants by 比序項目 in a fixed
order starting with 在校學業成績全校排名百分比 — where the applicant sits in their
own high school — so `gpa_r1` is the marginal admittee's percentile and 1% beats
17%. Later items only break ties among applicants level on the earlier ones, and
`tiebreak_r1` records those that came into play.

Covers 001 臺大, 006 政大, 011 清大, 013 交通 (陽明交通 from 111), 025 陽明,
099 臺北大, 109 北醫, for 110 and 111. 110 is the last year 陽明 and 交通 admit
separately and 111 the first as 陽明交通, so the pair spans the merger.

Two things stop `gpa` from being a drop-in third axis:

- **It is censored at 1%**, where 19% of departments sit — including most of
  臺大's. 43 of those 78 print a 學測 tiebreak, which is what separates them.
- **It is rank within a high school**, so it says nothing about how strong that
  school is. A 1% at a rural school and at 建中 are not the same student.

`group=eight` (醫學系, 牙醫學系) reports 通過篩選 ahead of a 甄試, not admission,
so its counts run to twice the quota and its percentiles are looser. It is
excluded. Of the remaining usable rows, 421 join a 分發 department in the
same year and contribute to the path-weighted score.

### 個人申請

A fourth route, OCR'd from CAC's PNGs into `apply-cutoffs.tsv`, same 8 schools
and years. What it reports is a first-stage 篩選標準, not a final cutoff:
applicants are cut to a multiple of the intake (`ratio`, the 篩選倍率) before
interviewing. 篩選順序一, 順序二… apply in turn, so the last one that fired is the
tightest bar, and `norm` divides it by the maximum attainable under the subjects
it names (15 級分 each).

`seats` is 招生名額, places offered. CAC does not publish final department-level
admit counts here, so `admitted` estimates filled seats by multiplying each
quota by the year's national fill rate: 88.7% for 110 and 81.6% for 111, from
CAC's `{year}_member_statistics.php`. It is a coverage weight, not an observed
department fill count.

The unreliable OCR rows are filtered before this path enters `score`:

- **28 rows of 546 (5%) have `norm` above 1**, which is impossible. OCR drops a
  character from composite labels — `(國文+英文)28` reads as `國文英` — so the
  subject count comes out too low and the ratio too high. Every affected row is
  caught by `norm > 1` and dropped.
- **111 of 546 校系名稱 are blank** and others are misread. Recovering those
  rows would require a `dept_code` join. `dept_ocr` holds the raw OCR; `dept` is
  that snapped to a real department name where one matched. The current safe
  same-year name join drops the remainder.

校系代碼, 招生名額, 篩選倍率 and the 檢定標準 bands all check out against the
images. After validation and the same-year department join, 312 rows contribute
to the 個申 path score.

## Caveats

- **The bridge explains under half the variance** (R2 0.42). Every per-school
  slope is positive, and the three schools carrying most of the data agree
  (宜蘭 +0.53, 屏東 +0.48, 師大 +0.58, against a pooled 0.56), but 聯合 gives
  +0.08 and 慈濟 +0.06 on 8 department-years. It rests on 6 universities, of
  which only 臺灣師範大學 reaches the range 臺灣科技大學 occupies, so the top of
  the 科大 ladder is the least certain part. Treat a 科大's position as good to
  roughly ±5 places, not ±1. Averaging over a whole institution's departments
  cancels much of this; single departments do not.
- **Path coverage.** 繁星 and 個申 cover only eight schools in 110-111;
  everyone else is still ranked from 分發/統測 alone. Their bridges are weak,
  and 個申 reports a first-stage screening threshold rather than a final cutoff.
  `seats_avg` includes these extra routes where collected, so it is not a
  complete cross-school intake comparison.
- **`score` is a percentile of admitted seats, not of applicants.** It ranks
  within the people who won a place through these channels, so a department at
  50 beat half the *admitted* field. CEEC's marginal distributions improve the
  ordering, but without joint subject scores they cannot identify the composite
  percentile among all applicants.
- **Each subject has its own candidate field.** The equal-percentile model
  compares a student with the people who took each selected subject. Those
  populations differ, especially between humanities and science subjects.
- **Not all 141 are universities.** 4 are 專科學校 (junior colleges) and 10 are
  學院. The name suffix identifies them if you want to filter.
- **Small departments are noisy.** The department file's top rows include
  2-seat, single-year entries. Filter on `seats_avg`.
- **Thin channels.** Where the partially collected paths are absent, a school's
  score rests only on the students who entered through 分發 or 聯登. It need not
  describe the students admitted through that school's other routes.

## Rebuild

    python3 parse_uac.py     # uac-*-cutoffs.pdf        -> uac-cutoffs.tsv
    python3 parse_tech.py    # tech/union42-*.pdf       -> tech-cutoffs.tsv
    python3 fetch_star.py 110 111   # -> star/,  ~2s and 340KB a year
    python3 parse_star.py           # star/*.pdf -> star-cutoffs.tsv, ~6 pages/s
    python3 fetch_apply.py 110 111   # -> apply/, ~7s and 4.4MB
    python3 parse_apply.py           # OCR apply/*.png -> apply-cutoffs.tsv, ~4min
    python3 fetch_ceec.py    # optional, only refreshes ceec/
    python3 parse_ceec.py    # ceec/*.xls -> ceec-scores.tsv
    python3 rank_uac.py      # all paths, bridge, gender -> rank-*.tsv
    python3 -m unittest

`rank_uac.py` pulls the 教育部 CSV through `gender.py` on first run. The 系組
name normalisation both it and `gender.py` group by lives in `deptname.py`.

`parse_apply.py` needs tesseract with traditional Chinese:

    curl -L https://github.com/tesseract-ocr/tessdata_fast/raw/main/chi_tra.traineddata \
      -o /usr/local/share/tessdata/chi_tra.traineddata
