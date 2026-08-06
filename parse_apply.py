"""OCR the 個人申請 篩選標準 images in apply/ into a TSV, one row per 校系.

個人申請 screens applicants down to a multiple of the intake (篩選倍率) before
interviewing them, so what CAC prints is a first-stage threshold, not a final
cutoff. It is still a real number on the 學測 15-級分 scale: 篩選順序一, 順序二…
are applied in turn, each cutting to its own 倍率, so the last order that fired
is the tightest bar and its 倍率 is what the intake was screened to.

`norm` puts that bar on 0-1 the way parse_uac.py does, dividing by the maximum
attainable under the subjects it names. `admitted` scales 招生名額 by the year's
national fill rate, since these tables count places offered, not places taken.

Every row is fully ruled, so the grid is found per row rather than per page,
which survives the repeated headers and the 【APCS校系】 block at the foot. Cells
are then OCR'd a column at a time: one pass over 80 stacked 招生名額 cells under
a digits-only alphabet is both far faster and more accurate than a pass per cell
or per row, because nothing in the image can be read as the wrong kind of thing.
"""

import csv
import glob
import io
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image

import tsvio

HERE = os.path.dirname(os.path.abspath(__file__))

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
CHUNK = 25      # cells per OCR pass; a whole column makes an unwieldy page
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


def parse(path, colleges, names):
    year, code = os.path.basename(path)[:-4].split("-")
    im = Image.open(path).convert("L")
    grid_rows = grid(np.array(im) < 128)
    counts = [len(vs) - 1 for _, _, vs in grid_rows]
    n_cells = max(LAYOUTS, key=counts.count)
    gate_names, ratio_names = LAYOUTS[n_cells]
    r0 = GATE_0 + len(gate_names)
    o0 = r0 + len(ratio_names)
    rows = [row for row in grid_rows if len(row[2]) - 1 == n_cells]
    cols = {j: read_column(im, rows, j, wl)
            for j, wl in alphabet(gate_names, ratio_names).items()}
    college = colleges.get((year, code), "")
    out, skipped = [], 0
    for i in range(len(rows)):
        cs = [cols[j][i] if j in cols else "" for j in range(n_cells)]
        dept_code = number(cs[0])
        if len(dept_code) < 5:
            skipped += 1
            continue
        gates = [band_of(c) for c in cs[GATE_0:r0]]
        ratios = [number(c) for c in cs[r0:o0]]
        orders = [order_cell(c) for c in cs[o0:o0 + N_ORDERS]]
        seats = number(cs[3])
        used = [float(r) for r in ratios if r]
        out.append({
            "year": year, "college_code": code, "college": college,
            "dept_code": dept_code,
            "dept": snap(cs[2], names.get(college, ())),
            "dept_ocr": cs[2],
            "sex": cs[1],
            "seats": seats,
            "admitted": round(int(seats) * FILL[year]) if seats and year in FILL else "",
            "ratio": min(used) if used else "",
            "gates": " ".join(f"{s}{g}" for s, g in zip(gate_names, gates)
                              if g and s != "空"),
            "ratios": " ".join(f"{s}{r}" for s, r in zip(ratio_names, ratios) if r),
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
    best, score = ocr, 0.0
    for c in candidates:
        if len(c) < len(ocr) - 2 or len(c) > len(ocr) + 2:
            continue
        hit = sum(1 for x, y in zip(ocr, c) if x == y) / max(len(ocr), len(c))
        if hit > score:
            best, score = c, hit
    return best if score >= 0.6 else ocr


def load_colleges():
    with open(os.path.join(HERE, "apply", "colleges.tsv"), encoding="utf-8") as f:
        return {(r["year"], r["college_code"]): r["college"]
                for r in csv.DictReader(f, delimiter="\t")}


def load_names():
    """{school: {department names}} from the sources that ship as text."""
    out = {}
    for path, col in ((os.path.join(HERE, "uac-cutoffs.tsv"), "dept"),
                      (os.path.join(HERE, "star-cutoffs.tsv"), "dept")):
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                out.setdefault(r["college" if "college" in r else "school"],
                               set()).add(r[col])
    return out


def main(out_path):
    colleges, names, rows = load_colleges(), load_names(), []
    for png in sorted(glob.glob(os.path.join(HERE, "apply", "*.png"))):
        got, skipped = parse(png, colleges, names)
        print(f"{os.path.basename(png)}: {len(got)} 校系, {skipped} non-data rows",
              file=sys.stderr)
        rows.extend(got)
    written = tsvio.write_rows(out_path, rows)
    print(f"wrote {written} rows to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main(os.path.join(HERE, "apply-cutoffs.tsv"))
