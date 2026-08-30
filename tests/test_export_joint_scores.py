import random
import unittest

from tools import export_joint_scores


class JointScoreExportFuzzTest(unittest.TestCase):
    def test_subject_and_total_mass_survive_export(self):
        rng = random.Random(271828)
        rows = []
        expected = {}
        for subject in (*export_joint_scores.SUBJECTS, export_joint_scores.TOTAL):
            expected[subject] = 0
            maximum = 3 if subject != export_joint_scores.TOTAL else 16
            for score in range(maximum):
                count = rng.randint(1, 100)
                expected[subject] += count
                rows.append({"year": "107", "exam": "gsat", "subject": subject,
                             "score": str(score), "seats": str(count)})
        subjects, formulas, totals = export_joint_scores.exported_rows(rows)
        found = {}
        for row in subjects:
            found[row["subject"]] = found.get(row["subject"], 0) + int(row["count"])
        self.assertEqual(found, {subject: expected[subject]
                                 for subject in export_joint_scores.SUBJECTS})
        self.assertEqual(sum(int(row["count"]) for row in totals),
                         expected[export_joint_scores.TOTAL])
        self.assertEqual(len(formulas), len(export_joint_scores.SUBJECTS))
