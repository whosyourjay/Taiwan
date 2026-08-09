import os
import random
import unittest

import rank_uac
from deptname import normalize
from lib.paths import data_path


CASES = {
    # Nothing to strip.
    "資訊工程學系": "資訊工程學系",
    "工學院學士班": "工學院學士班",
    "國際管理學士學位學程": "國際管理學士學位學程",
    "幼兒保育科": "幼兒保育科",
    # Weighting-formula 組.
    "電機工程學系甲組": "電機工程學系",
    "會計學系A組": "會計學系",
    "經濟學系第1組": "經濟學系",
    "管理學院不分系學士班甲組": "管理學院不分系學士班",
    # Subject-track and specialisation 組.
    "法律學系司法組": "法律學系",
    "材料及資源工程系材料組": "材料及資源工程系",
    "資訊工程學系資訊工程組": "資訊工程學系",
    "統計學系(自然組)": "統計學系",
    "數學系甲組(數學組)": "數學系",
    "物理學系物理組(甲組一般組)": "物理學系",
    # Funding, quota, campus, and 教育部's 專班 suffix.
    "醫學系(公費)": "醫學系",
    "戲劇學系(男)": "戲劇學系",
    "機電工程學系（公費生）": "機電工程學系",
    "資訊管理學系(桃園校區)": "資訊管理學系",
    "藝術史學系【外加】": "藝術史學系",
    "電子工程系(建工校區)_智慧資電系統技優專班": "電子工程系",
    # A name the PDF clipped mid-qualifier.
    "土木工程學系(科技暨基礎建設永續發展": "土木工程學系",
    # A 組 with no department head in front of it stays whole.
    "機械工程組": "機械工程組",
}

PARTS = ["資訊工程", "學系", "系", "科", "學士班", "學位學程", "甲組", "第1組", "自然組",
         "(公費)", "(桃園校區)", "（男）", "工程組", "設計", "學院", "組", "(", "）", "-"]


def dept_names():
    for name in rank_uac.SOURCES.values():
        source = data_path(name)
        if not os.path.exists(source):
            continue
        with open(source, encoding="utf-8") as f:
            col = f.readline().rstrip("\n").split("\t").index("dept")
            for line in f:
                yield line.rstrip("\n").split("\t")[col]


class TestNormalize(unittest.TestCase):
    def test_cases(self):
        for name, want in CASES.items():
            self.assertEqual(normalize(name), want, name)

    def test_idempotent_on_real_names(self):
        names = list(dept_names())
        if not names:
            self.skipTest("cutoff TSVs not built")
        for name in set(names):
            once = normalize(name)
            self.assertEqual(normalize(once), once, name)
            self.assertTrue(once, name)

    def test_fuzz(self):
        rng = random.Random(0)
        for _ in range(20000):
            name = "".join(rng.choice(PARTS) for _ in range(rng.randint(1, 5)))
            out = normalize(name)
            self.assertEqual(normalize(out), out, name)
            self.assertLessEqual(len(out), len(name))
            self.assertTrue(name.startswith(out), name)


if __name__ == "__main__":
    unittest.main()
