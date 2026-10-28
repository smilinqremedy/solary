import unittest
import asyncio
from app.services.whatsapp_service import WhatsAppService

class TestConversationalBot(unittest.TestCase):
    def setUp(self):
        self.service = WhatsAppService()
        self.device_info = {
            "site_name": "Victoria Island Commercial Hub",
            "battery_type": "LiFePO4 (48V 300Ah)",
            "battery_capacity_wh": 15000.0
        }
        self.sample_telemetry = {
            "device_id": "NG-INV-00124",
            "timestamp": 1729854000,
            "grid_v": 0.0,
            "grid_on": False,
            "pv_w": 3200,
            "bat_v": 52.1,
            "bat_soc": 78,
            "bat_a": 12.5,
            "load_w": 1400,
            "temp_c": 36.5,
            "fault_code": 0
        }
        self.analytics_summary = {
            "pv_today_kwh": 22.4,
            "pv_month_kwh": 610.0
        }

    def test_conversational_status_query(self):
        response = asyncio.run(self.service.handle_conversational_query(
            sender_phone="2348031234567",
            message_body="Status",
            latest_telemetry=self.sample_telemetry,
            device_info=self.device_info,
            analytics_summary=self.analytics_summary
        ))
        self.assertIn("SOLARY ENERGY STATUS", response)
        self.assertIn("Victoria Island Commercial Hub", response)
        self.assertIn("3,200 W", response)
        self.assertIn("78%", response)
        self.assertIn("1,400 W", response)

    def test_conversational_savings_query(self):
        response = asyncio.run(self.service.handle_conversational_query(
            sender_phone="2348031234567",
            message_body="Savings",
            latest_telemetry=self.sample_telemetry,
            device_info=self.device_info,
            analytics_summary=self.analytics_summary
        ))
        self.assertIn("SOLARY SAVINGS & FUEL DISPLACEMENT", response)
        self.assertIn("22.4 kWh", response)
        self.assertIn("₦", response)

    def test_conversational_health_query(self):
        response = asyncio.run(self.service.handle_conversational_query(
            sender_phone="2348031234567",
            message_body="Health",
            latest_telemetry=self.sample_telemetry,
            device_info=self.device_info,
            analytics_summary=self.analytics_summary
        ))
        self.assertIn("SOLARY INVERTER & BATTERY HEALTH", response)
        self.assertIn("LiFePO4", response)

    def test_conversational_help_query(self):
        response = asyncio.run(self.service.handle_conversational_query(
            sender_phone="2348031234567",
            message_body="Hello! Who are you?",
            latest_telemetry=self.sample_telemetry,
            device_info=self.device_info,
            analytics_summary=self.analytics_summary
        ))
        self.assertIn("Welcome to Solary Energy Assistant!", response)
        self.assertIn("👉 *Status*", response)

if __name__ == '__main__':
    unittest.main()
