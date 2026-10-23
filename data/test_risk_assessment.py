import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import risk_assessment as ra  # noqa: E402

ASSETS = [{"asset_id": "A01", "name": "Server", "type": "Infrastruttura", "description": ""}]
CONTROLS = [
    {"category": "Backup", "control_id": "A.8.13", "control_name": "Backup",
     "suggested_action": "Regola 3-2-1"},
]


def make_risk(risk_id="R01", asset_id="A01", category="Backup", likelihood="3", impact="5"):
    return {"risk_id": risk_id, "asset_id": asset_id, "category": category,
            "threat": "t", "vulnerability": "v", "likelihood": likelihood, "impact": impact}


class ScoreAndLevelTests(unittest.TestCase):
    def test_score_is_likelihood_times_impact(self):
        self.assertEqual(ra.calculate_score(3, 5), 15)

    def test_level_boundaries(self):
        self.assertEqual(ra.risk_level(6), "Basso")
        self.assertEqual(ra.risk_level(8), "Medio")
        self.assertEqual(ra.risk_level(12), "Medio")
        self.assertEqual(ra.risk_level(15), "Alto")
        self.assertEqual(ra.risk_level(25), "Alto")


class ValidationTests(unittest.TestCase):
    def test_valid_data_passes(self):
        ra.validate(ASSETS, [make_risk()], CONTROLS)

    def test_value_out_of_range(self):
        with self.assertRaises(ValueError):
            ra.validate(ASSETS, [make_risk(likelihood="6")], CONTROLS)

    def test_value_not_a_number(self):
        with self.assertRaises(ValueError):
            ra.validate(ASSETS, [make_risk(impact="alto")], CONTROLS)

    def test_unknown_asset(self):
        with self.assertRaises(ValueError):
            ra.validate(ASSETS, [make_risk(asset_id="A99")], CONTROLS)

    def test_category_without_controls(self):
        with self.assertRaises(ValueError):
            ra.validate(ASSETS, [make_risk(category="Altro")], CONTROLS)


class ReportTests(unittest.TestCase):
    def test_report_is_sorted_from_highest_score(self):
        risks = [make_risk("R01", likelihood="1", impact="2"),
                 make_risk("R02", likelihood="5", impact="5")]
        report = ra.build_report(ASSETS, risks, CONTROLS)
        self.assertEqual([row["risk_id"] for row in report], ["R02", "R01"])

    def test_high_risk_gets_controls(self):
        report = ra.build_report(ASSETS, [make_risk(likelihood="4", impact="4")], CONTROLS)
        self.assertEqual(report[0]["treatment"], "Trattare")
        self.assertIn("A.8.13", report[0]["suggested_controls"])

    def test_low_risk_is_accepted_without_controls(self):
        report = ra.build_report(ASSETS, [make_risk(likelihood="1", impact="2")], CONTROLS)
        self.assertEqual(report[0]["treatment"], "Accettare e monitorare")
        self.assertEqual(report[0]["suggested_controls"], "")


if __name__ == "__main__":
    unittest.main()
