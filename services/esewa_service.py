"""Small eSewa ePay V2 helper module used by the marketplace checkout.

UAT uses eSewa's public test merchant credentials by default so the final-year
project can be demonstrated without storing a private production secret.
Production always requires merchant credentials through environment variables.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class EsewaConfigurationError(RuntimeError):
    """Raised when the eSewa environment/merchant configuration is invalid."""


class EsewaVerificationError(ValueError):
    """Raised when an eSewa response cannot be trusted or validated."""


UAT_PRODUCT_CODE = "EPAYTEST"
UAT_SECRET_KEY = "8gBm/:&EnhH.1/q"


ENDPOINTS = {
    "uat": {
        "payment_url": "https://rc-epay.esewa.com.np/api/epay/main/v2/form",
        "status_url": "https://uat.esewa.com.np/api/epay/transaction/status/",
    },
    "production": {
        "payment_url": "https://epay.esewa.com.np/api/epay/main/v2/form",
        "status_url": "https://epay.esewa.com.np/api/epay/transaction/status/",
    },
}


def money(value) -> str:
    """Return an amount with exactly two decimal places."""
    try:
        return str(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise EsewaVerificationError("Invalid payment amount received.") from error


def config() -> dict:
    """Return eSewa settings.

    UAT intentionally falls back to eSewa's documented public test merchant
    values. Production has no defaults and must be configured explicitly.
    """
    environment = os.environ.get("ESEWA_ENVIRONMENT", "uat").strip().lower()
    if environment == "prod":
        environment = "production"
    if environment not in ENDPOINTS:
        raise EsewaConfigurationError("ESEWA_ENVIRONMENT must be 'uat' or 'production'.")

    defaults = ENDPOINTS[environment]
    if environment == "uat":
        product_code = os.environ.get("ESEWA_PRODUCT_CODE", UAT_PRODUCT_CODE).strip()
        secret_key = os.environ.get("ESEWA_SECRET_KEY", UAT_SECRET_KEY)
    else:
        product_code = os.environ.get("ESEWA_PRODUCT_CODE", "").strip()
        secret_key = os.environ.get("ESEWA_SECRET_KEY", "")

    if not product_code or not secret_key:
        raise EsewaConfigurationError(
            "eSewa production credentials are missing. Set ESEWA_PRODUCT_CODE and ESEWA_SECRET_KEY."
        )

    payment_url = os.environ.get("ESEWA_PAYMENT_URL", defaults["payment_url"]).strip()
    status_url = os.environ.get("ESEWA_STATUS_URL", defaults["status_url"]).strip()
    if not payment_url or not status_url:
        raise EsewaConfigurationError("eSewa payment/status URL is missing.")

    return {
        "environment": environment,
        "product_code": product_code,
        "secret_key": secret_key,
        "payment_url": payment_url,
        "status_url": status_url,
    }


def signature_message(data: dict, signed_field_names: str) -> str:
    """Build eSewa's comma-separated signed-field message in the given order."""
    fields = [item.strip() for item in str(signed_field_names).split(",") if item.strip()]
    if not fields or any(field not in data for field in fields):
        raise EsewaVerificationError("The eSewa signed fields are incomplete.")
    return ",".join(f"{field}={data[field]}" for field in fields)


def generate_signature(data: dict, signed_field_names: str, secret_key: str) -> str:
    message = signature_message(data, signed_field_names)
    digest = hmac.new(secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def create_payment_payload(order, success_url: str, failure_url: str):
    """Create the form payload posted to eSewa ePay V2."""
    settings = config()
    signed_fields = "total_amount,transaction_uuid,product_code"
    amount = money(order.amount)
    payload = {
        "amount": amount,
        "tax_amount": "0",
        "total_amount": amount,
        "transaction_uuid": order.transaction_uuid,
        "product_code": settings["product_code"],
        "product_service_charge": "0",
        "product_delivery_charge": "0",
        "success_url": success_url,
        "failure_url": failure_url,
        "signed_field_names": signed_fields,
    }
    payload["signature"] = generate_signature(payload, signed_fields, settings["secret_key"])
    return settings["payment_url"], payload


def decode_success_response(encoded_data: str) -> dict:
    """Decode the Base64 JSON returned in eSewa's `data` query parameter."""
    if not encoded_data:
        raise EsewaVerificationError("The eSewa success response is missing.")
    try:
        # Some gateways/proxies omit trailing Base64 padding in query strings.
        # Restore it before strict decoding without accepting malformed input.
        encoded_data = str(encoded_data).strip()
        encoded_data += "=" * (-len(encoded_data) % 4)
        raw = base64.b64decode(encoded_data, validate=True).decode("utf-8")
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EsewaVerificationError("The eSewa success response is invalid.") from error
    if not isinstance(data, dict):
        raise EsewaVerificationError("The eSewa success response is invalid.")
    return data


def verify_response_signature(data: dict) -> None:
    """Verify the HMAC signature included in eSewa's successful callback."""
    settings = config()
    signature = str(data.get("signature", ""))
    signed_fields = str(data.get("signed_field_names", ""))
    if not signature or not signed_fields:
        raise EsewaVerificationError("The eSewa response has no verifiable signature.")
    signed_names = {item.strip() for item in signed_fields.split(",") if item.strip()}
    required_names = {
        "transaction_code", "status", "total_amount", "transaction_uuid",
        "product_code", "signed_field_names",
    }
    if not required_names.issubset(signed_names):
        raise EsewaVerificationError("The eSewa response omits required signed fields.")
    expected = generate_signature(data, signed_fields, settings["secret_key"])
    if not hmac.compare_digest(signature, expected):
        raise EsewaVerificationError("The eSewa response signature could not be verified.")


def check_transaction_status(transaction_uuid: str, total_amount) -> dict:
    """Verify a transaction against eSewa's server-side status endpoint."""
    settings = config()
    query = urlencode(
        {
            "product_code": settings["product_code"],
            "total_amount": money(total_amount),
            "transaction_uuid": transaction_uuid,
        }
    )
    separator = "&" if "?" in settings["status_url"] else "?"
    request = Request(
        f"{settings['status_url']}{separator}{query}",
        headers={"Accept": "application/json", "User-Agent": "car-resell-price-prediction-system/1.0"},
    )
    try:
        with urlopen(request, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
    except Exception as error:
        raise EsewaVerificationError(
            "eSewa status verification is temporarily unavailable. Please check the payment again."
        ) from error
    if not isinstance(result, dict):
        raise EsewaVerificationError("eSewa returned an invalid transaction-status response.")
    return result
