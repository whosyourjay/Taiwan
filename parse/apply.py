"""OCR the 個人申請 篩選標準 images in apply/ into a TSV, one row per 校系.

個人申請 screens applicants down to a multiple of the intake (篩選倍率) before
interviewing them, so what CAC prints is a first-stage threshold, not a final
cutoff. It is still a real number on the 學測 15-級分 scale: 篩選順序一, 順序二…
are applied in turn, each cutting to its own 倍率, so the last order that fired
is the tightest bar and its 倍率 is what the intake was screened to.

`norm` puts that bar on 0-1 the way `parse.uac` does, dividing by the maximum
attainable under the subjects it names. `admitted` scales 招生名額 by the year's
national fill rate, since these tables count places offered, not places taken.

Every row is fully ruled, so the grid is found per row rather than per page,
which survives the repeated headers and the 【APCS校系】 block at the foot. Cells
are then OCR'd a column at a time: one pass over 80 stacked 招生名額 cells under
a digits-only alphabet is both far faster and more accurate than a pass per cell
or per row, because nothing in the image can be read as the wrong kind of thing.
"""

import argparse
import csv
import difflib
import glob
import io
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image

from lib import tsvio
from lib.paths import data_path, source_path


N_ORDERS = 6
GATE_0 = 4

# 學測 split 數學 into 數學A and 數學B for 111, which adds a 篩選倍率 column, so
# the layout is keyed by how many cells a row has. `空` is an unused spacer.
LAYOUTS = {
    24: (("國文", "英文", "數學", "社會", "自然", "空", "英聽"),
         ("國文", "英文", "數學", "社會", "自然", "組合")),
    25: (("國文", "英文", "數學A", "數學B", "社會", "自然", "英聽"),
         ("國文", "英文", "數學A", "數學B", "社會", "自然", "組合")),
}

SUBJECT_CHARS = "國文英數學社會自然聽測科目組合AB"
BAND_CHARS = "頂前均後底標"
DIGITS = "0123456789"

SCALE = 4
CHUNK = 25
MARGIN = 20     # white border trim() leaves around the ink
MIN_INK = 6     # original px; `--` is about 3 tall, any character at least 12


def alphabet(gates, ratios):
    """What each cell of a row may contain, by column index.

    Index 2 (校系名稱) is open vocabulary; the last column (同線分超額篩選) is a
    bare asterisk and is not read at all.
    """
    r0 = GATE_0 + len(gates)
    o0 = r0 + len(ratios)
    return ({0: DIGITS, 1: "無男女", 2: None, 3: DIGITS}
            | {j: BAND_CHARS for j in range(GATE_0, r0)}
            | {j: DIGITS + "." for j in range(r0, o0)}
            | {j: SUBJECT_CHARS + DIGITS + "()+" for j in range(o0, o0 + N_ORDERS)})

MAX_LEVEL = 15.0
BANDS = ("頂標", "前標", "均標", "後標", "底標")
# A 篩選順序 names its subjects either spelled out and joined with + inside
# brackets, `(國文+英文+社會)43`, or run together as initials, `國英數社54`.
SPELLED = re.compile(r"國文|英文|數學[AB]?|社會|自然|英聽")
INITIALS = re.compile(r"(?:[國英數社自][AB]?){2,}")
SUBJECT_CHAR = re.compile(r"[國英數社自]")

# 招生名額 is places offered. CAC's own totals give what share was taken:
# 獲分發人數 over 招生名額總數, from {year}_member_statistics.php.
FILL = {"110": 49279 / 55541, "111": 45518 / 55810}
STAT_NUMBER = r".*?<font\s+color\s*=\s*red[^>]*>([\d,]+)</font>"

# Fixed on 2026-08-29: the top seven of 68 general universities in the combined
# ranking. Historical names keep 陽明交通 in the same longitudinal selection.
TOP_DECILE = {
    "國立臺灣大學", "國立政治大學", "國立陽明交通大學", "國立陽明大學",
    "國立交通大學", "國立清華大學", "國立成功大學", "國立臺北大學",
    "國立中央大學",
}


def tess(img, whitelist=None, psm="6", tsv=False):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    cmd = ["tesseract", "stdin", "stdout", "-l", "chi_tra", "--psm", psm]
    if whitelist:
        cmd += ["-c", f"tessedit_char_whitelist={whitelist}"]
    if tsv:
        cmd += ["tsv"]
    out = subprocess.run(cmd, input=buf.getvalue(), capture_output=True).stdout
    text = out.decode("utf-8", "replace")
    return text if tsv else text.strip().replace("\n", "").replace(" ", "")


def group(idx, gap=4):
    """Runs of adjacent indices collapsed to their midpoints."""
    if len(idx) == 0:
        return []
    out, run = [], [int(idx[0])]
    for i in idx[1:]:
        if i - run[-1] <= gap:
            run.append(int(i))
        else:
            out.append(int(np.mean(run)))
            run = [int(i)]
    return out + [int(np.mean(run))]


def grid(dark):
    """Horizontal rules across the image, then vertical rules within each row.

    Sub-column rules stop at every section header, so none of them spans the
    image; looking for them one row at a time finds them all.
    """
    H, W = dark.shape
    hs = group(np.where(dark.sum(axis=1) > 0.5 * W)[0])
    rows = []
    for y0, y1 in zip(hs, hs[1:]):
        if y1 - y0 < 12:
            continue
        band = dark[y0 + 3:y1 - 2]
        rows.append((y0, y1, group(np.where(band.sum(axis=0) > 0.9 * band.shape[0])[0])))
    return rows


def trim(img, margin=20):
    """Crop to the ink and re-pad evenly, or None if the cell is empty.

    Cells are mostly blank — 校系名稱 is 380px wide for three characters — and
    tesseract reads those extreme aspect ratios poorly.
    """
    a = np.array(img)
    ys, xs = np.where(a < 128)
    if len(xs) == 0:
        return None
    cut = img.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    out = Image.new("L", (cut.width + 2 * margin, cut.height + 2 * margin), 255)
    out.paste(cut, (margin, margin))
    return out


def cell_image(im, x0, x1, y0, y1):
    """One cell: upscaled, binarised and trimmed, or None if it holds no text.

    Rows are shaded pink and blue by turn, and left grey that fill costs
    tesseract most of what it would read. A cell holding only `--` trims far
    flatter than one holding text, which rules it out without an OCR pass.
    """
    c = im.crop((x0 + 3, y0 + 3, x1 - 2, y1 - 2))
    c = c.resize((c.width * SCALE, c.height * SCALE), Image.LANCZOS)
    c = trim(c.point(lambda p: 0 if p < 128 else 255))
    if c is None or c.height - 2 * MARGIN < MIN_INK * SCALE:
        return None
    return c


def read_column(im, rows, j, whitelist):
    """Text of cell `j` for every row, from one OCR pass per chunk of rows.

    Cells are stacked down a page with gaps wider than their own text, so
    tesseract cannot run two into one line, and a word's vertical position
    says which cell it came from.
    """
    out = []
    for k in range(0, len(rows), CHUNK):
        crops = [cell_image(im, vs[j], vs[j + 1], y0, y1)
                 for y0, y1, vs in rows[k:k + CHUNK]]
        live = [c for c in crops if c]
        if not live:
            out.extend([""] * len(crops))
            continue
        pad = 2 * max(c.height for c in live)
        page = Image.new("L", (max(c.width for c in live) + 2 * pad,
                               sum(c.height for c in live) + pad * (len(crops) + 1)), 255)
        bounds, y = [], pad
        for c in crops:
            if c:
                page.paste(c, (pad, y))
                y += c.height
            y += pad
            bounds.append(y - pad // 2)
        got = [""] * len(crops)
        for line in tess(page, whitelist, tsv=True).splitlines()[1:]:
            f = line.split("\t")
            if len(f) < 12 or not f[11].strip():
                continue
            mid = int(f[7]) + int(f[9]) / 2
            for i, b in enumerate(bounds):
                if mid < b:
                    got[i] += f[11].strip()
                    break
        out.extend(got)
    return out


def read_columns(im, rows, indexes, whitelist):
    """Read only selected columns, isolating each to retain trusted accuracy."""
    return {j: read_column(im, rows, j, whitelist) for j in indexes}


def band_of(text):
    for b in BANDS:
        if b[0] in text:
            return b
    return ""


def number(text):
    m = re.search(r"\d+(?:\.\d+)?", text)
    return m.group() if m else ""


def subjects_of(text):
    """學測 subjects a 篩選順序 names: `國英數社54` -> 4, `(國文+英文)27` -> 2."""
    spelled = SPELLED.findall(text)
    if spelled:
        return len(spelled)
    initials = INITIALS.search(text)
    return len(SUBJECT_CHAR.findall(initials.group())) if initials else 1


def order_cell(text):
    """(label, level, n_subjects) from a 通過倍率篩選最低級分 cell."""
    val = number(text)
    if not val:
        return "", "", 0
    return re.sub(r"[\d.()+]", "", text), float(val), subjects_of(text)


def measure(orders):
    """The binding bar: the last 篩選順序 that fired, normalised to 0-1."""
    fired = [o for o in orders if o[2]]
    if not fired:
        return {"cut_label": "", "cut_level": "", "cut_n": "", "norm": "", "n_orders": 0}
    label, level, n = fired[-1]
    return {"cut_label": label, "cut_level": level, "cut_n": n,
            "norm": round(level / (MAX_LEVEL * n), 4), "n_orders": len(fired)}


def parse(path, colleges, names, code_names=None, fills=None):
    year, code = os.path.basename(path)[:-4].split("-")
    im = Image.open(path).convert("L")
    grid_rows = grid(np.array(im) < 128)
    counts = [len(vs) - 1 for _, _, vs in grid_rows]
    n_cells = max(LAYOUTS, key=counts.count)
    gate_names, ratio_names = LAYOUTS[n_cells]
    r0 = GATE_0 + len(gate_names)
    o0 = r0 + len(ratio_names)
    rows = [row for row in grid_rows if len(row[2]) - 1 == n_cells]
    order_indexes = list(range(o0, o0 + N_ORDERS))
    cols = read_columns(im, rows, (0, 3), DIGITS)
    cols.update(read_columns(
        im, rows, order_indexes, SUBJECT_CHARS + DIGITS + ".()+"
    ))
    college = colleges.get((year, code), "")
    code_names = code_names or {}
    fills = FILL if fills is None else fills
    codes = [number(value) for value in cols[0]]
    missing = [i for i, dept_code in enumerate(codes)
               if len(dept_code) >= 5
               and (year, code, dept_code[:5]) not in code_names]
    read_names = read_column(im, [rows[i] for i in missing], 2, None)
    ocr_names = dict(zip(missing, read_names))
    out, skipped = [], 0
    for i in range(len(rows)):
        cs = [cols[j][i] if j in cols else "" for j in range(n_cells)]
        dept_code = codes[i]
        if len(dept_code) < 5:
            skipped += 1
            continue
        orders = [order_cell(c) for c in cs[o0:o0 + N_ORDERS]]
        seats = number(cs[3])
        ocr_name = ocr_names.get(i, "")
        dept = code_names.get((year, code, dept_code[:5]), "")
        out.append({
            "year": year, "college_code": code, "college": college,
            "dept_code": dept_code,
            "dept": dept or snap(ocr_name, names.get(college, ())),
            "dept_ocr": ocr_name,
            "sex": "",
            "seats": seats,
            "admitted": round(int(seats) * fills[year]) if seats and year in fills else "",
            "ratio": "", "gates": "", "ratios": "",
            "order_1": f"{orders[0][0]}{orders[0][1]:g}" if orders[0][2] else "",
            **measure(orders),
        })
    return out, skipped


def snap(ocr, candidates):
    """OCR'd 校系名稱 replaced by the closest name the school really has.

    tesseract confuses visually close characters (系 for 銷), which a list of
    the school's own department names, read from the text-PDF sources, fixes.
    """
    if not ocr or not candidates:
        return ocr
    text = "".join(char for char in ocr if "\u4e00" <= char <= "\u9fff")
    if not text:
        return ocr
    best, score = ocr, 0.0
    for c in candidates:
        candidate = "".join(char for char in c if "\u4e00" <= char <= "\u9fff")
        if abs(len(candidate) - len(text)) > 2:
            continue
        hit = difflib.SequenceMatcher(None, text, candidate).ratio()
        if hit > score:
            best, score = c, hit
    return best if score >= 0.6 else ocr


def load_colleges():
    with open(source_path("apply", "colleges.tsv"), encoding="utf-8") as f:
        return {(r["year"], r["college_code"]): r["college"]
                for r in csv.DictReader(f, delimiter="\t")}


def fill_rates():
    """Annual CAC placement/quota ratios from cached official statistics."""
    out = dict(FILL)
    for source in glob.glob(source_path("apply", "*-statistics.html")):
        year = os.path.basename(source).split("-", 1)[0]
        with open(source, encoding="utf-8") as handle:
            text = handle.read()
        quota = re.search(r"招生名額總數：" + STAT_NUMBER, text)
        placed = re.search(r"獲分發人數\(招生名額\)：" + STAT_NUMBER, text)
        if quota and placed:
            denominator = int(quota.group(1).replace(",", ""))
            out[year] = int(placed.group(1).replace(",", "")) / denominator
    return out


def load_names():
    """{school: {department names}} from the sources that ship as text."""
    out = {}
    for source, col in ((data_path("uac-cutoffs.tsv"), "dept"),
                        (data_path("star-cutoffs.tsv"), "dept")):
        if not os.path.exists(source):
            continue
        with open(source, encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                out.setdefault(r["college" if "college" in r else "school"],
                               set()).add(r[col])
    return out


def load_code_names():
    """Stable CAC program prefixes mapped to names from the text 繁星 source."""
    source = data_path("star-cutoffs.tsv")
    if not os.path.exists(source):
        return {}
    return {(row["year"], row["college_code"], row["dept_code"]): row["dept"]
            for row in tsvio.read_rows(source)}


def name_cells(source):
    """``(year, college code, department code, OCR name)`` from one image.

    A name-only repair needs two narrow columns instead of the 23 columns a
    complete parse reads. The existing TSV remains the authority for places,
    screens and every other field.
    """
    year, college_code = os.path.basename(source)[:-4].split("-")
    im = Image.open(source).convert("L")
    grid_rows = grid(np.array(im) < 128)
    counts = [len(vs) - 1 for _, _, vs in grid_rows]
    n_cells = max(LAYOUTS, key=counts.count)
    rows = [row for row in grid_rows if len(row[2]) - 1 == n_cells]
    codes = read_column(im, rows, 0, DIGITS)
    names = read_column(im, rows, 2, None)
    return [
        (year, college_code, code, name)
        for code, name in zip(codes, names)
        if len(code) >= 5 and name
    ]


def refresh_names(rows, readings, names):
    """Repair TSV department names when a fresh OCR reading snaps to a source."""
    by_code = {
        (row["year"], row["college_code"], row["dept_code"]): row for row in rows
    }
    changed = missing = 0
    for year, college_code, dept_code, ocr in readings:
        row = by_code.get((year, college_code, dept_code))
        if row is None:
            missing += 1
            continue
        candidate_names = names.get(row["college"], ())
        repaired = snap(ocr, candidate_names)
        if repaired not in candidate_names or repaired == row["dept"]:
            continue
        row["dept"], row["dept_ocr"] = repaired, ocr
        changed += 1
    return changed, missing


def refresh_names_from_images(out_path, years=()):
    """Update trusted names from the source images without re-reading cutoffs."""
    rows = list(tsvio.read_rows(out_path))
    names = load_names()
    wanted = set(years)
    readings = []
    for source in sorted(glob.glob(source_path("apply", "*.png"))):
        year = os.path.basename(source).split("-", 1)[0]
        if wanted and year not in wanted:
            continue
        readings.extend(name_cells(source))
    changed, missing = refresh_names(rows, readings, names)
    written = tsvio.write_rows(out_path, rows)
    print(
        f"refreshed {changed} names; {missing} OCR codes absent from {out_path} "
        f"({written} rows)",
        file=sys.stderr,
    )


def source_key(source):
    return tuple(os.path.basename(source)[:-4].split("-"))


def sources(colleges, top_decile=False, years=()):
    """Selected source images, with historical school names resolved locally."""
    wanted_years = set(years)
    out = []
    for source in sorted(glob.glob(source_path("apply", "*.png"))):
        year, code = source_key(source)
        if wanted_years and year not in wanted_years:
            continue
        if top_decile and colleges.get((year, code)) not in TOP_DECILE:
            continue
        out.append(source)
    return out


def replace_source(rows, key, replacement):
    kept = [row for row in rows if (row["year"], row["college_code"]) != key]
    return sorted(kept + replacement,
                  key=lambda row: (row["year"], row["college_code"], row["dept_code"]))


def audit_rows(trusted, found):
    """Critical-field agreement with the existing slow-parser corpus."""
    fields = ("seats", "cut_label", "cut_level", "cut_n", "norm")
    old = {row["dept_code"]: row for row in trusted}
    new = {row["dept_code"]: row for row in found}
    common = old.keys() & new.keys()
    agreement = {
        field: sum(str(old[key][field]) == str(new[key][field]) for key in common)
        / max(len(common), 1)
        for field in fields
    }
    return len(old), len(new), len(common), agreement


def audit_sources(selected, existing, colleges, names, code_names, fills):
    totals = {field: [0, 0] for field in ("seats", "cut_label", "cut_level", "cut_n", "norm")}
    for source in selected:
        key = source_key(source)
        trusted = [row for row in existing
                   if (row["year"], row["college_code"]) == key]
        if not trusted:
            raise RuntimeError(f"no trusted rows for audit: {os.path.basename(source)}")
        found, _ = parse(source, colleges, names, code_names, fills)
        old_n, new_n, common_n, agreement = audit_rows(trusted, found)
        print(f"audit {os.path.basename(source)}: {old_n}/{new_n} rows, "
              + ", ".join(f"{field}={100 * value:.1f}%"
                          for field, value in agreement.items()), file=sys.stderr)
        for field, value in agreement.items():
            totals[field][0] += round(value * common_n)
            totals[field][1] += common_n
        if common_n != old_n or new_n != old_n or min(agreement.values()) < 0.99:
            raise RuntimeError(f"accuracy gate failed for {os.path.basename(source)}")
    print("accuracy gate passed: " + ", ".join(
        f"{field}={100 * hits / count:.1f}%" for field, (hits, count) in totals.items()
    ), file=sys.stderr)


def main(out_path, selected, refresh=False, audit=False):
    colleges, names, code_names, fills = (
        load_colleges(), load_names(), load_code_names(), fill_rates()
    )
    rows = list(tsvio.read_rows(out_path)) if os.path.exists(out_path) else []
    if audit:
        audit_sources(selected, rows, colleges, names, code_names, fills)
        return
    parsed = {(row["year"], row["college_code"]) for row in rows}
    for index, source in enumerate(selected, 1):
        key = source_key(source)
        if key in parsed and not refresh:
            print(f"{os.path.basename(source)} cached ({index}/{len(selected)})",
                  file=sys.stderr)
            continue
        got, skipped = parse(source, colleges, names, code_names, fills)
        rows = replace_source(rows, key, got)
        tsvio.write_rows(out_path, rows)
        print(f"{os.path.basename(source)}: {len(got)} rows, {skipped} skipped "
              f"({index}/{len(selected)}; checkpointed)", file=sys.stderr)
    print(f"wrote {len(rows)} rows to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("years", nargs="*")
    parser.add_argument("--top-decile", action="store_true")
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--names-only", action="store_true")
    args = parser.parse_args()
    target = data_path("apply-cutoffs.tsv")
    if args.names_only:
        refresh_names_from_images(target, args.years)
    else:
        college_names = load_colleges()
        chosen = sources(college_names, args.top_decile, args.years)
        main(target, chosen, args.refresh or not args.top_decile, args.audit)
