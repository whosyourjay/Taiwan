"""Normalise a 系組 name to the department a graduate would name.

Admission splits one department into 組 that differ only in weighting formula,
subject track, campus, funding or intake quota: 電機工程學系甲組, 醫學系(公費),
戲劇學系(男), 資訊管理學系(桃園校區). 教育部 reports all of these as one
department, and a graduate says 電機系, so they collapse to a single name.
"""

import re

# A department name ends at its head noun (系/科/班/學位學程/學院); anything after
# that and before 組 is the qualifier that admission adds.
TAIL = re.compile(r"^(.*[系科班程院])(.+組)$")


def normalize(name):
    name = re.split(r"[(（]", name)[0].strip()
    m = TAIL.match(name)
    return m.group(1) if m else name


def key(name):
    """Grouping key. A department writes itself 資訊工程系 one year, 資訊工程學系
    the next, so the two spellings must land together."""
    return normalize(name).replace("學系", "系")
