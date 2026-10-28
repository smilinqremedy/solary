import unittest
import json

class TestPayloadFormat(unittest.TestCase):
    def test_json_payload_structure(self):
        sample_payload = {
            "device_id": "NG-INV-00124",
            "timestamp": 1729854000,
            "grid_v": 224.5,
            "grid_on": True,
            "pv_w": 2450,
            "bat_v": 52.4,
            "bat_soc": 82,
            "load_w": 620,
            "temp_c": 38.2
        }

        # Verify all mandatory fields exist
        required_keys = [
            "device_id", "timestamp", "grid_v", "grid_on",
            "pv_w", "bat_v", "bat_soc", "load_w", "temp_c"
        ]
        for key in required_keys:
            self.assertIn(key, sample_payload)

        # Validate types and values
        self.assertEqual(sample_payload["device_id"], "NG-INV-00124")
        self.assertIsInstance(sample_payload["grid_on"], bool)
        self.assertEqual(sample_payload["grid_on"], True)
        self.assertEqual(sample_payload["grid_v"], 224.5)
        self.assertEqual(sample_payload["pv_w"], 2450)
        self.assertEqual(sample_payload["bat_v"], 52.4)
        self.assertEqual(sample_payload["bat_soc"], 82)
        self.assertEqual(sample_payload["load_w"], 620)
        self.assertEqual(sample_payload["temp_c"], 38.2)

        # Validate JSON serialization round-trip
        serialized = json.dumps(sample_payload)
        deserialized = json.loads(serialized)
        self.assertEqual(sample_payload, deserialized)

if __name__ == '__main__':
    unittest.main()
