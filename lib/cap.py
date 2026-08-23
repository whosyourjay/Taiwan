"""The 國中教育會考 mark scale and the 基北區 points it converts to.

基北區 gives each subject's mark a whole point and 寫作測驗 a fraction, so five
subjects and one essay make the 36-point score its schools publish as an entry
cutoff. Both conversions are printed in the sources already downloaded here.
"""

import re

CATEGORY = re.compile(r"^\d+A\d+B\d+C$")
SUBJECTS = ("國文", "英語", "數學", "社會", "自然")
MARK_POINTS = {"A++": 7, "A+": 6, "A": 5, "B++": 4, "B+": 3, "B": 2, "C": 1}
MARKS = tuple(MARK_POINTS)
GRADES = {mark: mark[0] for mark in MARK_POINTS}
# Most districts score only the three achievement levels, so five 精熟 make 30
# and the plus marks are left to break ties.
GRADE_POINTS = {"A": 6, "B": 4, "C": 2}
# The national tables pool 三級分以下, which is worth 0.4 at its top and holds
# under 2% of takers, so the whole bucket enters at 0.4.
WRITING_POINTS = {"六級分": 1.0, "五級分": 0.8, "四級分": 0.6, "三級分以下": 0.4}
WRITING = tuple(WRITING_POINTS)
MAX_SCORE = len(SUBJECTS) * max(MARK_POINTS.values()) + max(WRITING_POINTS.values())


def category_of(a_count, b_count, subjects=len(SUBJECTS)):
    """The published five-subject label for a count of A and B marks."""
    return f"{a_count}A{b_count}B{subjects - a_count - b_count}C"
