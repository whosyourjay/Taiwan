"""Current and historical names for institutions that merged."""

import re


SUCCESSORS = {
    "國立陽明大學": "國立陽明交通大學",
    "國立交通大學": "國立陽明交通大學",
    "國立高雄科技大學(原國立高雄第一科技大學)": "國立高雄科技大學",
    "國立高雄科技大學(原國立高雄應用科技大學)": "國立高雄科技大學",
    "國立高雄科技大學(原國立高雄海洋科技大學)": "國立高雄科技大學",
    "慈濟科技大學": "慈濟大學",
    "慈濟學校財團法人慈濟科技大學": "慈濟大學",
}
FORMER = {
    "國立陽明交通大學": ("國立陽明大學", "國立交通大學"),
    "國立高雄科技大學": (
        "國立高雄第一科技大學", "國立高雄應用科技大學", "國立高雄海洋科技大學",
    ),
    "慈濟大學": ("慈濟科技大學",),
}
OFFICIAL_ENGLISH = {
    "國立陽明交通大學": "National Yang Ming Chiao Tung University",
    "國立陽明大學": "National Yang-Ming University",
    "國立交通大學": "National Chiao Tung University",
    "國立高雄科技大學": "National Kaohsiung University of Science and Technology",
    "國立高雄第一科技大學": "National Kaohsiung First University of Science and Technology",
    "國立高雄應用科技大學": "National Kaohsiung University of Applied Sciences",
    "國立高雄海洋科技大學": "National Kaohsiung Marine University",
    "慈濟大學": "Tzu Chi University",
    "慈濟科技大學": "Tzu Chi University of Science and Technology",
}
CAMPUS = re.compile(r"[(（].*")


def current(name):
    """The institution's modern name, preserving ordinary campus labels."""
    return SUCCESSORS.get(name, name)


def without_campus(name):
    """A school name suitable for matching campus-split ministry rows."""
    return CAMPUS.sub("", name).strip()
