# Taiwan university admission difficulty

Ranks Taiwanese universities and departments by how hard they are to get into as
a bachelor student. Nothing here reflects research output or reputation.

Covers both admission systems, on one scale: 141 institutions, 2,992 departments.

## Outputs

- `rank-universities.tsv` — 141 institutions (122 still admitting in 114)
- `rank-departments.tsv` — 2,992 (institution, department) pairs

Columns: `rank school [dept] score years last_year active seats_avg system
men women pct_women`

- `score` — 0-100, the percentile of the 分發入學 seats that were harder to win.
  Averages 108-114, weighted by admitted seats. 科大 are mapped onto this axis
  and the weakest of them land slightly below 0; see Bridging.
- `seats_avg` — admitted seats per year, averaged over the years it ran.
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

Both are text PDFs

一般大學, 繁星推薦 (學測 + 在校學業成績全校排名百分比). 各校系錄取標準一覽表,
split into 第一類至第七類學群 and 第八類學群 (medicine):

    https://www.cac.edu.tw/cacportal/star_his_report/{year}/{year}_result_standard/{one2seven,eight}/{code}/{year}Standard_{code}.pdf

Text PDFs in fixed columns. Downloaded for 8 schools over 110-111 only, into
`star/` -> `star-cutoffs.tsv`. See 繁星 below.

教育部統計處, 大專校院各校科系別學生數, for the gender columns:

    https://stats.moe.gov.tw/files/detail/{year}/{year}_students.csv   # 110-113

Three directories hold data downloaded but not yet used:

- `star/` — 繁星推薦 錄取標準, and `star-cutoffs.tsv` parsed from it. Not in
  `score`, which stays a pure 分發入學 axis.
- `ceec/` — 大考中心 score distributions (級分人數百分比累計表 and friends,
  .xls, back to year 91) for 學測 and 分科測驗. These are what would convert a
  cutoff into a percentile of test-takers.
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

An institution's score is the seat-weighted mean over every one of its rows, in
one pass rather than a mean of department means, so it answers how hard the
typical admitted seat was.

### Curving to percentiles

`norm` is a fraction of a maximum, which assumes the raw scale is linear in
ability. It is not: 級分 distributions are lumpy and asymmetric, and every
department's weight vector composes them differently, so equal `norm` gaps at
different points on the scale are not equal differences in difficulty.

So each (year, system) is curved against its own admitted seats. A row's score
is the percentage of that year's seats that went to a harder cutoff, counting
seats rather than departments, with ties sharing the midpoint of the span they
cover. Only the *ordering* of cutoffs within a year survives, which is the part
the raw scale gets right.

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
dropped. That merges 4,397 rows into 2,992.

Departments also rename themselves between years, most often between 系 and
學系, which would otherwise split one department's history in two. Names are
grouped ignoring that difference — 70 departments are affected — and each is
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

which maps every 科大 onto the 分發入學 axis. Each system is curved against its
own field, so both run 0-100 before bridging; the fit is what says that the two
fields sit at different heights. It puts the 統測 seat pool below the 分科 one
throughout — the strongest 科大 department lands near the 58th percentile of
分發入學 seats, and the weakest few fall slightly below 0, which is an honest
extrapolation rather than a floor to clip.

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

### Gender

An independent source: 教育部 counts who is *enrolled*, where the cutoffs record
who was *admitted*. Ratios use total bachelor headcount over all four years,
since pooling cohorts steadies small departments, and cover day division only.

Departments are matched on the same normalised name the ranking groups by, which
is what makes the join work: 教育部 reports the department, 招生 reports its 組.
That matches 2,371 of 2,992 departments, and 94.5% of both public and private
departments still admitting in 114 — the two sectors agreeing to a tenth of a
point rules out sector bias. Every institution with no gender data at all had
already closed or merged before 113, the latest year 教育部 publishes.

Spot checks land where they should: 幼兒保育 95% women, 車輛工程 2%, 機械工程 9%,
電機工程 12%, 資訊工程 19%, 護理 80%, and 49.1% women across all matched
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
so its counts run to twice the quota and its percentiles are looser. Keep those
rows out of any aggregate with `group=one2seven`.

### 個人申請

A fourth route, OCR'd from CAC's PNGs into `apply-cutoffs.tsv`, same 8 schools
and years. What it reports is a first-stage 篩選標準, not a final cutoff:
applicants are cut to a multiple of the intake (`ratio`, the 篩選倍率) before
interviewing. 篩選順序一, 順序二… apply in turn, so the last one that fired is the
tightest bar, and `norm` divides it by the maximum attainable under the subjects
it names (15 級分 each).

`seats` is 招生名額, places offered. `admitted` scales it by the year's national
fill rate — 獲分發人數 over 招生名額總數, 88.7% for 110 and 81.6% for 111, from
CAC's `{year}_member_statistics.php`. No screened-to-admitted guess is needed,
because the table states the intake directly.

**Unfinished, and not wired into `score`.** Two known defects:

- **28 rows of 546 (5%) have `norm` above 1**, which is impossible. OCR drops a
  character from composite labels — `(國文+英文)28` reads as `國文英` — so the
  subject count comes out too low and the ratio too high. Every affected row is
  caught by `norm > 1`. Untreated they inflate 交通 to 1.53 and 臺大 to 1.34, so
  the school-level aggregate is not usable until they are fixed or dropped.
- **111 of 546 校系名稱 are blank** and others are misread. Join on `dept_code`,
  not `dept`. `dept_ocr` holds the raw OCR; `dept` is that snapped to a real
  department name where one matched.

校系代碼, 招生名額, 篩選倍率 and the 檢定標準 bands all check out against the
images. The damage is confined to parsing the composite subject labels.

## Caveats

- **The bridge explains under half the variance** (R2 0.42). Every per-school
  slope is positive, and the three schools carrying most of the data agree
  (宜蘭 +0.53, 屏東 +0.48, 師大 +0.58, against a pooled 0.56), but 聯合 gives
  +0.08 and 慈濟 +0.06 on 8 department-years. It rests on 6 universities, of
  which only 臺灣師範大學 reaches the range 臺灣科技大學 occupies, so the top of
  the 科大 ladder is the least certain part. Treat a 科大's position as good to
  roughly ±5 places, not ±1. Averaging over a whole institution's departments
  cancels much of this; single departments do not.
- **Channel.** 分發入學 is the minority route into 一般大學. Most students enter
  via 個人申請 and 繁星推薦, which are 學測-based. 繁星 is now in `star/` for 8
  schools; 個人申請 is published only as PNG images, so it would need OCR, and
  what it reports is a first-stage 篩選標準 rather than a final cutoff.
- **`score` is a percentile of admitted seats, not of applicants.** It says how
  many admitted students beat a harder cutoff, so it is a percentile within the
  people who got a place through this channel, not within everyone who sat the
  exam. `ceec/` is what would convert a cutoff to a percentile of test-takers.
- **The percentile is within one exam's field.** Curving fixes the raw scale's
  nonlinearity but not the fact that a department's weight vector selects a
  particular set of subjects, whose takers are a particular slice.
- **Not all 141 are universities.** 3 are 專科學校 (junior colleges) and 7 are
  學院. The name suffix identifies them if you want to filter.
- **Small departments are noisy.** The department file's top rows include
  2-seat, single-year entries. Filter on `seats_avg`.
- **Thin channels.** A school where 分發入學 is a small side door is measured on
  whoever came through it. The median institution admits 26% of its intake this
  way; 國立臺灣體育運動大學 admits 11%, and its score rests on that slice.

## Rebuild

    python3 parse_uac.py     # uac-*-cutoffs.pdf        -> uac-cutoffs.tsv
    python3 parse_tech.py    # tech/union42-*.pdf       -> tech-cutoffs.tsv
    python3 rank_uac.py      # both, bridge, gender     -> rank-*.tsv
    python3 fetch_star.py 110 111   # -> star/,  ~2s and 340KB a year
    python3 parse_star.py           # star/*.pdf -> star-cutoffs.tsv, ~6 pages/s
    python3 fetch_apply.py 110 111   # -> apply/, ~7s and 4.4MB
    python3 parse_apply.py           # OCR apply/*.png -> apply-cutoffs.tsv, ~4min
    python3 fetch_ceec.py    # optional, only refreshes ceec/
    python3 -m unittest test_deptname test_star

`rank_uac.py` pulls the 教育部 CSV through `gender.py` on first run. The 系組
name normalisation both it and `gender.py` group by lives in `deptname.py`.

`parse_apply.py` needs tesseract with traditional Chinese:

    curl -L https://github.com/tesseract-ocr/tessdata_fast/raw/main/chi_tra.traineddata \
      -o /usr/local/share/tessdata/chi_tra.traineddata
