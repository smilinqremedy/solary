import unittest
from app.services.rules_engine import RulesEngine

class TestRulesEngine(unittest.TestCase):
    def setUp(self):
        self.engine = RulesEngine()

    def test_battery_depletion_calculation_standard(self):
        # 10,000 Wh (10 kWh) battery, 35% SOC, 10% Cutoff, 2500W Load
        # Usable energy: 10,000 * (0.35 - 0.10) = 2,500 Wh
        # Depletion time: 2500 Wh / 2500 W = 1.0 hour
        hours = self.engine.calculate_depletion_time_hours(
            battery_capacity_wh=10000.0,
            current_soc_pct=35.0,
            cutoff_soc_pct=10.0,
            active_load_w=2500.0
        )
        self.assertAlmostEqual(hours, 1.0, places=2)

    def test_battery_depletion_calculation_heavy_load(self):
        # 5,000 Wh (5 kWh) battery, 40% SOC, 10% Cutoff, 3000W Load
        # Usable energy: 5000 * 0.30 = 1500 Wh
        # Depletion time: 1500 / 3000 = 0.5 hours (30 minutes)
        hours = self.engine.calculate_depletion_time_hours(
            battery_capacity_wh=5000.0,
            current_soc_pct=40.0,
            cutoff_soc_pct=10.0,
            active_load_w=3000.0
        )
        self.assertAlmostEqual(hours, 0.5, places=2)
        formatted = self.engine.format_hours_minutes(hours)
        self.assertEqual(formatted, "30 mins")

    def test_battery_depletion_zero_or_negative_load(self):
        hours = self.engine.calculate_depletion_time_hours(
            battery_capacity_wh=10000.0,
            current_soc_pct=50.0,
            cutoff_soc_pct=10.0,
            active_load_w=0.0
        )
        self.assertEqual(hours, 999.0)

    def test_battery_depletion_already_at_cutoff(self):
        hours = self.engine.calculate_depletion_time_hours(
            battery_capacity_wh=10000.0,
            current_soc_pct=9.0,
            cutoff_soc_pct=10.0,
            active_load_w=1500.0
        )
        self.assertEqual(hours, 0.0)

    def test_format_hours_minutes(self):
        self.assertEqual(self.engine.format_hours_minutes(0.8), "48 mins")
        self.assertEqual(self.engine.format_hours_minutes(1.5), "1h 30m")
        self.assertEqual(self.engine.format_hours_minutes(2.0), "2 hours")

if __name__ == '__main__':
    unittest.main()
