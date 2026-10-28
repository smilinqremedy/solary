import unittest
from app.services.analytics_service import AnalyticsService

class TestAnalyticsService(unittest.TestCase):
    def test_fuel_savings_calculation(self):
        # 20 kWh generated with fuel at NGN 1,150 / liter
        # 20 * 0.35 L = 7.0 Liters
        # 7.0 * 1150 = 8,050 NGN
        savings = AnalyticsService.calculate_generator_fuel_savings(
            kwh_generated=20.0,
            fuel_price_ngn=1150.0
        )
        self.assertEqual(savings["kwh_generated"], 20.0)
        self.assertEqual(savings["fuel_liters_displaced"], 7.0)
        self.assertEqual(savings["money_saved_naira"], 8050.0)

    def test_monthly_accumulated_savings(self):
        # Typical 5kW Nigerian rooftop system generating 540 kWh / month
        savings = AnalyticsService.calculate_generator_fuel_savings(
            kwh_generated=540.0,
            fuel_price_ngn=1150.0
        )
        expected_liters = 540.0 * 0.35 # 189.0 Liters
        expected_naira = 189.0 * 1150.0 # 217,350 NGN
        self.assertAlmostEqual(savings["fuel_liters_displaced"], expected_liters, places=2)
        self.assertAlmostEqual(savings["money_saved_naira"], expected_naira, places=2)

if __name__ == '__main__':
    unittest.main()
