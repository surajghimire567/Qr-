"""Talks to Khalti / eSewa. Views never call requests directly."""
import base64
import hashlib
import hmac
import json
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings

TIMEOUT = 15


class GatewayError(Exception):
    pass


# ---------------- Khalti (ePayment v2) ----------------
def _khalti_headers():
    return {"Authorization": f"Key {settings.KHALTI_SECRET_KEY}",
            "Content-Type": "application/json"}


def to_paisa(amount):
    return int((Decimal(amount) * 100).quantize(Decimal("1")))


def khalti_initiate(*, order, return_url, website_url):
    payload = {
        "return_url": return_url,
        "website_url": website_url,
        "amount": to_paisa(order.total_amount),          # Khalti wants paisa (int)
        "purchase_order_id": str(order.pk),
        "purchase_order_name": f"Order #{order.pk}",
        "customer_info": {"name": order.full_name, "phone": order.phone},
    }
    try:
        r = requests.post(settings.KHALTI_BASE_URL + "epayment/initiate/",
                          json=payload, headers=_khalti_headers(), timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise GatewayError(f"Khalti unreachable: {exc}") from exc
    if r.status_code != 200:
        raise GatewayError(f"Khalti initiate failed: {r.status_code} {r.text[:200]}")
    data = r.json()
    if "pidx" not in data or "payment_url" not in data:
        raise GatewayError("Khalti response missing pidx/payment_url")
    return data                                           # {"pidx", "payment_url", ...}


def khalti_lookup(pidx):
    """Server-to-server truth. Never trust the ?status= in the redirect."""
    try:
        r = requests.post(settings.KHALTI_BASE_URL + "epayment/lookup/",
                          json={"pidx": pidx}, headers=_khalti_headers(), timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise GatewayError(f"Khalti unreachable: {exc}") from exc
    if r.status_code not in (200, 400, 404):
        raise GatewayError(f"Khalti lookup failed: {r.status_code}")
    return r.json()                                       # {"status": "Completed", "total_amount": ...}


# ---------------- eSewa (ePay v2, HMAC-SHA256) ----------------
def esewa_sign(message):
    digest = hmac.new(settings.ESEWA_SECRET_KEY.encode(), message.encode(),
                      hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def esewa_amount(amount):
    return f"{Decimal(amount):.2f}"


def esewa_form_fields(*, order, transaction_uuid, success_url, failure_url):
    total = esewa_amount(order.total_amount)
    code = settings.ESEWA_PRODUCT_CODE
    signed = "total_amount,transaction_uuid,product_code"
    message = f"total_amount={total},transaction_uuid={transaction_uuid},product_code={code}"
    return {
        "amount": total, "tax_amount": "0", "product_service_charge": "0",
        "product_delivery_charge": "0", "total_amount": total,
        "transaction_uuid": transaction_uuid, "product_code": code,
        "success_url": success_url, "failure_url": failure_url,
        "signed_field_names": signed, "signature": esewa_sign(message),
    }


def esewa_decode_and_verify(data_b64):
    """Decode ?data= from eSewa and check its HMAC. Returns dict or raises GatewayError."""
    try:
        payload = json.loads(base64.b64decode(data_b64).decode())
        fields = payload["signed_field_names"].split(",")
        message = ",".join(f"{f}={payload[f]}" for f in fields)
        received = payload["signature"]
    except (ValueError, KeyError, TypeError) as exc:
        raise GatewayError("Malformed eSewa data") from exc
    if not hmac.compare_digest(esewa_sign(message), received):
        raise GatewayError("eSewa signature mismatch")
    return payload


def esewa_status(*, transaction_uuid, total_amount):
    """Second, independent check: ask eSewa directly."""
    params = {"product_code": settings.ESEWA_PRODUCT_CODE,
              "total_amount": total_amount, "transaction_uuid": transaction_uuid}
    try:
        r = requests.get(settings.ESEWA_STATUS_URL, params=params, timeout=TIMEOUT)
        return r.json()                                   # {"status": "COMPLETE", "ref_id": ...}
    except (requests.RequestException, ValueError) as exc:
        raise GatewayError(f"eSewa status check failed: {exc}") from exc


def parse_amount(value):
    try:
        return Decimal(str(value).replace(",", ""))
    except InvalidOperation:
        return None