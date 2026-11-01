import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import esg  # noqa: E402


class TestESG(unittest.TestCase):
    def setUp(self):
        self.raw = esg.generate()
        self.clean, self.dq = esg.validate(self.raw)
        self.m = esg.metrics(self.clean)

    def test_reproducible(self):
        self.assertTrue(self.raw.equals(esg.generate()))

    def test_gaps_detected_and_filled(self):
        self.assertEqual(self.dq["gaps"], 2)
        self.assertFalse(self.clean[["electricity_mwh", "scope1_t"]].isna().any().any())

    def test_market_below_location_with_renewables(self):
        self.assertTrue((self.m.scope2_market_t < self.m.scope2_location_t).iloc[-1])

    def test_target_path_endpoints(self):
        p = esg.target_path(100.0, [2021, 2030])
        self.assertAlmostEqual(p[0], 100.0); self.assertAlmostEqual(p[1], 58.0)

    def test_intensity_definition(self):
        r = self.m.iloc[0]
        self.assertAlmostEqual(r.intensity_t_per_musd, r.s12_market_t / r.revenue_musd)

    def test_carbon_exposure_math(self):
        e = esg.carbon_exposure(10000, 50.0).set_index("scenario")
        self.assertAlmostEqual(e.loc["Net zero 2050", "cost_musd"], 1.5)
        self.assertAlmostEqual(e.loc["Net zero 2050", "pct_of_ebitda"], 3.0)


if __name__ == "__main__":
    unittest.main()
