"""Parse 技專校院入學測驗中心 統測 score distributions into a TSV of score counts.

The 成績人數累計表 (open data report B2) gives, for every subject, how many
candidates scored in each one-point band from 0 to 100. 共同科目 國文/英文 are sat
by everyone; 數學 splits into four papers and 專業科目(一)(二) into one per
群(類), so those subjects are named with the 群 they belong to.

Absentees (缺考) are reported apart from the distribution and are left out, which
is the denominator the published percentages already use.

Output columns match `parse.ceec`: year exam subject score seats.
"""

import collections
import glob
import os
import re
import sys
import unicodedata

from lib.paths import data_path, path as repo_path
from parse.ceec import mark_midpoint
from parse.uac import pdf_text

SCORES = "tech/tcte-*-scores.pdf"

# pdftotext -layout leaves the year floating away from the rest of the heading,
# and in 114 onto a line of its own, so the year is taken from the filename.
TITLE = re.compile(r"學年度成績人數累計表-四技二專-(共同科目|專業科目\([一二]\))-(\S+)")
# Each page prints two half-tables side by side, so a line holds up to two bands.
BAND = re.compile(r"(\d+(?:\.\d+)?\s*[~〜～]\s*\d+|0\.00)\s+([\d,]+)\s+\d")
BANDS_PER_SUBJECT = 101  # 100 one-point bands, plus a row for exactly zero


WRAPPED = re.compile(r"^[ \t]*[~〜～](\d+)[ \t]*\n([ \t]*)(\d+(?:\.\d+)?)", re.M)


def clean(text):
    """Fold the compatibility ideographs and fullwidth digits the PDFs mix in.

    From 114 the top band's label wraps, leaving ～100 alone on a line above the
    99.01 that belongs with it; rejoin the two before anything reads them.
    """
    return WRAPPED.sub(r"\2\3~\1", unicodedata.normalize("NFKC", text))


# 專業科目(一) is set for a whole 群 where 專業科目(二) splits it into 類, and the
# 商管 and 外語 群 share one 專業科目(一) paper. 四技二專聯合登記分發 names a
# department's 群 at the 類 level throughout, so the coarser paper is looked up by
# dropping the 類, then by this table.
SHARED_FIRST_PAPER = {"商業與管理群": "商管外語群", "外語群": "商管外語群"}
MATH = "數學"


def professional_subject(group, part, known):
    """Name the 專業科目 paper a 群(類) sits, or None if the tables lack it."""
    stem = re.sub(r"(?<=群).+$", "", group)
    for name in (group, stem, SHARED_FIRST_PAPER.get(stem, "")):
        subject = f"{part}-{name}"
        if name and subject in known:
            return subject
    return None


def subject_of(part, tail):
    """Name the distribution a page reports, keyed by 群 where it varies.

    共同科目 數學 is four different papers, and every 專業科目 is written per
    群(類), so those names carry the 群. 國文 and 英文 are one paper nationally.
    """
    if part == "共同科目":
        return tail
    return f"{part.replace('科目', '')}-{tail}"


def parse_page(text, year, carried=None):
    """Yield (year, subject, score, count) for one 成績人數累計表 page.

    From 113 a subject can overflow onto an untitled page, so a page with no
    heading of its own continues `carried`.
    """
    body = clean(text)
    title = TITLE.search(body)
    subject = subject_of(*title.groups()) if title else carried
    if subject is None:
        return
    for line in body.splitlines():
        for band, count in BAND.findall(line):
            # 48.01～49 is the same shape of band as CEEC's 48.01-49, once the
            # tilde — three codepoints across the years — is spelled its way.
            score = mark_midpoint(re.sub(r"\s*[~〜～]\s*", "-", band))
            if score is not None:
                yield year, subject, score, float(count.replace(",", ""))


def parse(path):
    year = re.search(r"tcte-(\d+)-", os.path.basename(path)).group(1)
    rows, subject = [], None
    for page in pdf_text(path).split("\f"):
        got = list(parse_page(page, year, subject))
        if got:
            subject = got[-1][1]
        rows.extend(got)
    return rows


def pooled_maths(rows):
    """Add a 數學 subject holding all four papers' candidates together.

    四技二專聯合登記分發 writes 數學*1.00 in a formula without saying which of
    數學(A)(B)(C)(S) the 群 sits, and the assignment is not in these tables. The
    papers' medians span about twelve points, so pooling them costs a little
    accuracy on one term of a five-subject weighted total.
    """
    totals = collections.Counter()
    for year, subject, score, count in rows:
        if subject.startswith(f"{MATH}("):
            totals[(year, score)] += count
    return [(year, MATH, score, count) for (year, score), count in totals.items()]


def short(rows):
    """How many subjects came out with the wrong number of bands, and by how much.

    Where a band label wraps across two lines and the rejoin misses it, the band
    is dropped. In 114 that costs the top 99.01～100 band, which nobody reaches.
    """
    counts = collections.Counter(s for _, s, _, _ in rows)
    missed = {s: BANDS_PER_SUBJECT - n for s, n in counts.items()
              if n != BANDS_PER_SUBJECT}
    if not missed:
        return ""
    return f"   {len(missed)} subjects short by {sorted(set(missed.values()))}"


def main(out_path):
    rows = []
    for source in sorted(glob.glob(repo_path(SCORES))):
        got = parse(source)
        subjects = {r[1] for r in got}
        takers = sum(r[3] for r in got if r[1] == "國文")
        print(f"{os.path.basename(source):<24} {len(got):>6} rows, "
              f"{len(subjects):>2} subjects, {takers:>7,.0f} 國文 takers" + short(got),
              file=sys.stderr)
        rows.extend(got + pooled_maths(got))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("year\texam\tsubject\tscore\tseats\n")
        for year, subject, score, count in rows:
            f.write(f"{year}\ttongce\t{subject}\t{score}\t{count}\n")
    print(f"wrote {len(rows)} rows to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main(data_path("tongce-scores.tsv"))
