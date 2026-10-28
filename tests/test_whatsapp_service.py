import unittest
import hmac
import hashlib
from app.services.whatsapp_service import WhatsAppService

class TestWhatsAppService(unittest.TestCase):
    def setUp(self):
        self.service = WhatsAppService()
        self.service.app_secret = "test_secret_key_12345"

    def test_hmac_sha256_verification_valid(self):
        payload = b'{"object":"whatsapp_business_account","entry":[]}'
        signature = hmac.new(
            key=b"test_secret_key_12345",
            msg=payload,
            digestmod=hashlib.sha256
        ).hexdigest()

        header = f"sha256={signature}"
        self.assertTrue(self.service.verify_webhook_signature(payload, header))

    def test_hmac_sha256_verification_invalid(self):
        payload = b'{"object":"whatsapp_business_account","entry":[]}'
        header = "sha256=invalid_tampered_signature_hex"
        self.assertFalse(self.service.verify_webhook_signature(payload, header))

    def test_hmac_sha256_verification_missing_header(self):
        payload = b'{}'
        self.assertFalse(self.service.verify_webhook_signature(payload, None))

if __name__ == '__main__':
    unittest.main()
