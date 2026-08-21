import base64
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services.esewa_service import (
    UAT_PRODUCT_CODE,
    UAT_SECRET_KEY,
    config,
    create_payment_payload,
    decode_success_response,
    generate_signature,
    verify_response_signature,
)


class EsewaServiceTests(unittest.TestCase):
    def test_uat_defaults_are_available_for_demo(self):
        with patch.dict(os.environ, {"ESEWA_ENVIRONMENT": "uat"}, clear=True):
            settings = config()
            self.assertEqual(settings["product_code"], UAT_PRODUCT_CODE)
            self.assertIn("rc-epay.esewa.com.np", settings["payment_url"])

    def test_payment_payload_is_signed_server_side(self):
        order = SimpleNamespace(amount="100.00", transaction_uuid="CRPP-TEST-123")
        with patch.dict(os.environ, {"ESEWA_ENVIRONMENT": "uat"}, clear=True):
            payment_url, payload = create_payment_payload(
                order,
                "http://localhost/payment/esewa/success",
                "http://localhost/payment/esewa/failure/1",
            )
        self.assertIn("rc-epay.esewa.com.np", payment_url)
        self.assertEqual(payload["product_code"], "EPAYTEST")
        self.assertEqual(payload["total_amount"], "100.00")
        self.assertTrue(payload["signature"])

    def test_signed_callback_round_trip(self):
        callback = {
            "transaction_code": "TESTREF",
            "status": "COMPLETE",
            "total_amount": "100.00",
            "transaction_uuid": "CRPP-TEST-123",
            "product_code": "EPAYTEST",
            "signed_field_names": "transaction_code,status,total_amount,transaction_uuid,product_code,signed_field_names",
        }
        callback["signature"] = generate_signature(
            callback, callback["signed_field_names"], UAT_SECRET_KEY
        )
        encoded = base64.b64encode(json.dumps(callback).encode()).decode()
        decoded = decode_success_response(encoded)
        with patch.dict(os.environ, {"ESEWA_ENVIRONMENT": "uat"}, clear=True):
            verify_response_signature(decoded)
        self.assertEqual(decoded["status"], "COMPLETE")

    def test_callback_decoder_accepts_unpadded_base64(self):
        callback = {"status": "COMPLETE", "transaction_uuid": "CRPP-TEST-123"}
        encoded = base64.b64encode(json.dumps(callback).encode()).decode().rstrip("=")
        self.assertEqual(decode_success_response(encoded), callback)

    def test_callback_requires_critical_signed_fields(self):
        callback = {
            "status": "COMPLETE",
            "transaction_uuid": "CRPP-TEST-123",
            "signed_field_names": "status,transaction_uuid",
        }
        callback["signature"] = generate_signature(
            callback, callback["signed_field_names"], UAT_SECRET_KEY
        )
        with patch.dict(os.environ, {"ESEWA_ENVIRONMENT": "uat"}, clear=True):
            with self.assertRaisesRegex(ValueError, "omits required signed fields"):
                verify_response_signature(callback)


if __name__ == "__main__":
    unittest.main()
