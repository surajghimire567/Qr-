"""Server-side adapters for the Khalti and eSewa payment gateways."""

import base64
import hashlib
import hmac
import json
import math
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings

TIMEOUT = 15


class GatewayError(Exception):
    """A provider response could not be safely verified or used."""


def response_object(response):
    try:
        data = response.json()
    except ValueError as exc:
        raise GatewayError("Gateway returned invalid JSON.") from exc
    if not isinstance(data, dict):
        raise GatewayError("Gateway returned an invalid response shape.")
    return data


def to_paisa(amount):
    return int((Decimal(amount) * 100).quantize(Decimal("1")))


def khalti_initiate(*, order, return_url, website_url):
    payload = {
        "return_url": return_url,
        "website_url": website_url,
        "amount": to_paisa(order.total_amount),
        "purchase_order_id": str(order.pk),
        "purchase_order_name": f"Order #{order.pk}",
        "customer_info": {"name": order.full_name, "phone": order.phone},
    }
    try:
        response = requests.post(
            settings.KHALTI_BASE_URL + "epayment/initiate/",
            json=payload,
            headers={
                "Authorization": f"Key {settings.KHALTI_SECRET_KEY}",
                "Content-Type": "application/json",
            },
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        raise GatewayError("Khalti could not be reached.") from exc
    if response.status_code != 200:
        raise GatewayError("Khalti could not start the payment.")

    data = response_object(response)
    if (not isinstance(data.get("pidx"), str) or not data["pidx"].strip()
            or not isinstance(data.get("payment_url"), str)
            or not data["payment_url"].strip()):
        raise GatewayError("Khalti returned incomplete initiation data.")
    return data


def khalti_lookup(pidx):
    """Ask Khalti for the status; never trust callback query parameters."""
    try:
        response = requests.post(
            settings.KHALTI_BASE_URL + "epayment/lookup/",
            json={"pidx": pidx},
            headers={
                "Authorization": f"Key {settings.KHALTI_SECRET_KEY}",
                "Content-Type": "application/json",
            },
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        raise GatewayError("Khalti could not be reached.") from exc
    # The documented expired/cancelled outcomes can use HTTP 400. Unknown
    # references may return 404; their payload remains an untrusted, held state.
    if response.status_code not in {200, 400, 404}:
        raise GatewayError("Khalti status lookup failed.")
    return response_object(response)


def esewa_sign(message):
    digest = hmac.new(
        settings.ESEWA_SECRET_KEY.encode(),
        message.encode(),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("ascii")


def esewa_amount(amount):
    return f"{Decimal(amount):.2f}"


def esewa_form_fields(*, order, transaction_uuid, success_url, failure_url):
    total = esewa_amount(order.total_amount)
    code = settings.ESEWA_PRODUCT_CODE
    signed = "total_amount,transaction_uuid,product_code"
    message = f"total_amount={total},transaction_uuid={transaction_uuid},product_code={code}"
    return {
        "amount": total,
        "tax_amount": "0",
        "product_service_charge": "0",
        "product_delivery_charge": "0",
        "total_amount": total,
        "transaction_uuid": transaction_uuid,
        "product_code": code,
        "success_url": success_url,
        "failure_url": failure_url,
        "signed_field_names": signed,
        "signature": esewa_sign(message),
    }


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key.")
        result[key] = value
    return result


def esewa_decode_and_verify(data_b64):
    """Decode and verify the exact eSewa success response contract."""
    required = {
        "transaction_code",
        "status",
        "total_amount",
        "transaction_uuid",
        "product_code",
        "signed_field_names",
    }
    try:
        if not isinstance(data_b64, str) or len(data_b64) > 8192:
            raise ValueError("Invalid callback size.")
        raw = base64.b64decode(data_b64, validate=True)
        payload = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_json_object,
        )
        if not isinstance(payload, dict):
            raise ValueError("Callback is not an object.")

        names = payload["signed_field_names"]
        signature = payload["signature"]
        if not isinstance(names, str) or not isinstance(signature, str):
            raise ValueError("Invalid signature metadata.")
        fields = names.split(",")
        if len(fields) != len(set(fields)) or set(fields) != required:
            raise ValueError("Unexpected signed fields.")

        for field in fields:
            value = payload[field]
            if isinstance(value, (dict, list, bool)) or value is None:
                raise ValueError("Invalid signed value.")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("Invalid signed number.")

        message = ",".join(f"{field}={payload[field]}" for field in fields)
        if not hmac.compare_digest(esewa_sign(message), signature):
            raise ValueError("Invalid signature.")
        if payload["product_code"] != settings.ESEWA_PRODUCT_CODE:
            raise ValueError("Wrong merchant.")
    except (ValueError, KeyError, TypeError, UnicodeError) as exc:
        raise GatewayError("Malformed or untrusted eSewa callback.") from exc
    return payload


def esewa_status(*, transaction_uuid, total_amount):
    """Query eSewa independently after a browser return."""
    params = {
        "product_code": settings.ESEWA_PRODUCT_CODE,
        "total_amount": total_amount,
        "transaction_uuid": transaction_uuid,
    }
    try:
        response = requests.get(
            settings.ESEWA_STATUS_URL,
            params=params,
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        raise GatewayError("eSewa status could not be checked.") from exc
    if response.status_code != 200:
        raise GatewayError("eSewa status lookup failed.")
    return response_object(response)


def parse_amount(value):
    try:
        amount = Decimal(str(value).replace(",", ""))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not amount.is_finite() or amount < 0:
        return None
    return amount
