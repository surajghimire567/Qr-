from django.conf import settings
from django.db import transaction
from django.utils import timezone

from orders.models import Order
from orders.services import LifecycleError, release_unpaid

from . import gateways as gw


def claim_payment_start(order_id, *, owner_id, gateway):
    """Atomically allow one gateway initiation for a pending order."""
    if gateway not in {Order.Gateway.KHALTI, Order.Gateway.ESEWA}:
        raise LifecycleError("Unsupported payment gateway.")
    changed = Order.objects.filter(
        pk=order_id,
        user_id=owner_id,
        status=Order.Status.PENDING,
        payment_ref="",
        payment_gateway="",
        payment_starting=False,
        stock_released_at__isnull=True,
    ).update(
        payment_starting=True,
        payment_gateway=gateway,
        updated_at=timezone.now(),
    )
    if changed != 1:
        raise LifecycleError("Payment was already started or the order is closed.")
    return Order.objects.get(pk=order_id, user_id=owner_id)


def record_payment_reference(order_id, *, gateway, reference):
    if (not isinstance(reference, str) or not reference.strip()
            or len(reference.strip()) > 100):
        raise LifecycleError("Invalid payment initiation reference.")
    changed = Order.objects.filter(
        pk=order_id,
        status=Order.Status.PENDING,
        payment_starting=True,
        payment_gateway=gateway,
        payment_ref="",
        stock_released_at__isnull=True,
    ).update(
        payment_ref=reference.strip(),
        payment_starting=False,
        updated_at=timezone.now(),
    )
    if changed != 1:
        raise LifecycleError("Payment initiation needs review.")
    return Order.objects.get(pk=order_id)


@transaction.atomic
def mark_paid(order_id, *, expected_ref, gateway, receipt):
    """Set paid only after external verification, retaining the initiation ID."""
    order = Order.objects.select_for_update().get(pk=order_id)
    if (not expected_ref or order.payment_ref != expected_ref
            or order.payment_gateway != gateway):
        raise LifecycleError("Payment identity mismatch.")
    if not isinstance(receipt, str) or not receipt.strip() or len(receipt.strip()) > 100:
        raise LifecycleError("Missing or invalid verified transaction receipt.")

    receipt = receipt.strip()
    if order.status == Order.Status.PAID:
        if order.gateway_transaction_id != receipt:
            raise LifecycleError("Conflicting receipt; reconcile manually.")
        return order
    if (order.status != Order.Status.PENDING
            or order.stock_released_at is not None
            or order.payment_starting):
        raise LifecycleError("Order cannot be paid; reconcile manually.")

    order.status = Order.Status.PAID
    order.gateway_transaction_id = receipt
    order.paid_at = timezone.now()
    order.save(update_fields=["status", "gateway_transaction_id", "paid_at", "updated_at"])
    return order


def reconcile_payment(order):
    """Resolve an owned order using only its stored gateway/reference and server APIs."""
    order = Order.objects.get(pk=order.pk)
    if order.status == Order.Status.PAID:
        return order
    if order.stock_released_at is not None:
        return order
    if order.status != Order.Status.PENDING:
        raise LifecycleError("Closed order requires manual reconciliation.")
    if order.payment_starting or not order.payment_ref:
        raise LifecycleError("Payment initiation needs review.")

    reference = order.payment_ref
    if order.payment_gateway == Order.Gateway.KHALTI:
        info = gw.khalti_lookup(reference)
        amount = info.get("total_amount")
        if (info.get("pidx") != reference or type(amount) is not int
                or amount != gw.to_paisa(order.total_amount)):
            raise gw.GatewayError("Khalti identity or amount mismatch.")

        status = info.get("status")
        if status == "Completed":
            receipt = info.get("transaction_id")
            if not isinstance(receipt, str) or not receipt.strip():
                raise gw.GatewayError("Khalti response is missing a transaction receipt.")
            return mark_paid(
                order.pk,
                expected_ref=reference,
                gateway=Order.Gateway.KHALTI,
                receipt=receipt,
            )
        if status in {"Expired", "User canceled"}:
            return release_unpaid(
                order.pk,
                expected_ref=reference,
                terminal=Order.Status.FAILED,
            )
        return order

    if order.payment_gateway == Order.Gateway.ESEWA:
        info = gw.esewa_status(
            transaction_uuid=reference,
            total_amount=gw.esewa_amount(order.total_amount),
        )
        if (info.get("transaction_uuid") != reference
                or info.get("product_code") != settings.ESEWA_PRODUCT_CODE
                or gw.parse_amount(info.get("total_amount")) != order.total_amount):
            raise gw.GatewayError("eSewa identity or amount mismatch.")
        if info.get("status") == "COMPLETE":
            receipt = info.get("ref_id")
            if not isinstance(receipt, str) or not receipt.strip():
                raise gw.GatewayError("eSewa response is missing a transaction receipt.")
            return mark_paid(
                order.pk,
                expected_ref=reference,
                gateway=Order.Gateway.ESEWA,
                receipt=receipt,
            )
        # PENDING, NOT_FOUND, cancellation, refund and unknown states are held
        # until a human reconciles provider state; they never restock on redirect.
        return order

    raise LifecycleError("Unknown gateway; review the legacy order manually.")
