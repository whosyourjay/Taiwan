# Taiwan university admission difficulty

Ranks Taiwanese universities and departments by how hard they are to get into as
a bachelor student. Nothing here reflects research output or reputation.

Covers both admission systems, on one scale: 141 institutions, 2,992 departments.

## Outputs

- `rank-universities.tsv` — 141 institutions (122 still admitting in 114)
- `rank-departments.tsv` — 2,992 (institution, department) pairs

Columns: `rank school [dept] score score_final score_raw years last_year active
seats_final system men women pct_women`

- `score` — difficulty on the 分發入學 axis, comparable across both systems.
  Averages 108-114, weighted by admitted seats.
- `score_final` — the last year the entity admitted anyone, so `score` and
  `score_final` together show drift.
- `score_raw` — the raw fraction of maximum, before year-leveling or bridging.
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

Both are text PDFs, so `pdftotext -layout` reads them. The UAC archive is on
`www2`; the `www` host 404s.

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

An institution's score is the seat-weighted mean over every one of its rows, in
one pass rather than a mean of department means, so it answers how hard the
typical admitted seat was.

### Levelling the years

An exam that runs easy lifts every cutoff that year. On the same 1,139
departments, the mean 分發入學 cutoff moves 0.664 (108) to 0.551 (111) to 0.618
(114) — a swing wider than the gap between the 1st and 30th university, and
enough to reward whoever happens to admit in the generous years. Each year's
mean is subtracted before pooling, measured over departments admitting in every
year so that a changing mix of departments cannot pose as a change in
difficulty. 統測 is levelled separately, against its own years.

Ranks built from complete 108-114 coverage barely move (mean 1.4 places). The
correction matters for the 25 institutions with partial coverage — ones founded
or closed mid-window — which move 6.8 places on average and up to 15.

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

    uac = 0.1896 + 0.5570 * tech      R2 = 0.419

which maps every 科大 onto the 分發入學 axis. The matched departments span 統測
0.22-0.88, so the map is almost never extrapolating.

The fit is applied to 76 科大 that have no 分發入學 data at all, so estimators
were compared by leave-one-school-out error: fit on five of the six bridge
schools, predict the sixth with no school effect available. Seat weighting helps
(0.0535 against 0.0561 unweighted). Collapsing each department to a single
multi-year mean does not (0.0543), and neither does a department-level random
intercept, which is best at 0.0528 but only by tuning a penalty large enough that
it nearly reproduces the fit above. Letting each department keep a free intercept
is worst of all (0.0562), which says the year-to-year variation left inside a
department after levelling is mostly noise.

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

## Exclusions

- **術科 departments** (431 rows). The arts practical exam is not on the 60/100
  subject scale, and normalising it alongside academic subjects puts four music
  departments above 1.0. No institution loses all its departments, but
  臺灣藝術大學 drops from 14 departments to 6. 統測 has no 術科 component.
- Nothing else. Institutions that have closed or merged are kept and marked
  `active=0`, so 國立陽明大學 and 國立交通大學 appear alongside the
  國立陽明交通大學 they merged into in 110.

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
- **`score` is a fraction of maximum, not a percentile.** The gap between 0.87
  and 0.80 is not a linear difficulty gap. `ceec/` is what would fix this.
- **Not all 141 are universities.** 3 are 專科學校 (junior colleges) and 7 are
  學院. The name suffix identifies them if you want to filter.
- **Small departments are noisy.** The department file's top rows include
  2-seat, single-year entries. Filter on `seats_final`.
- Arts schools stay over-ranked even after the 術科 exclusion: 臺灣藝術大學
  sits in the top 15 on 91 seats.

## Rebuild

    python3 parse_uac.py     # uac-*-cutoffs.pdf        -> uac-cutoffs.tsv
    python3 parse_tech.py    # tech/union42-*.pdf       -> tech-cutoffs.tsv
    python3 rank_uac.py      # both, bridge, gender     -> rank-*.tsv
    python3 fetch_star.py 110 111   # -> star/,  ~2s and 340KB a year
    python3 parse_star.py           # star/*.pdf -> star-cutoffs.tsv, ~6 pages/s
    python3 fetch_ceec.py    # optional, only refreshes ceec/
    python3 -m unittest test_deptname test_star

`rank_uac.py` pulls the 教育部 CSV through `gender.py` on first run. The 系組
name normalisation both it and `gender.py` group by lives in `deptname.py`.
