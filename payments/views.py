import logging
import uuid
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from orders.models import Order
from orders.services import LifecycleError

from . import gateways as gw
from .services import (
    claim_payment_start,
    reconcile_payment,
    record_payment_reference,
)

logger = logging.getLogger(__name__)


def _order_detail(order):
    return redirect("orders:order_detail", order_id=order.pk)


def _check_and_report(request, order):
    try:
        result = reconcile_payment(order)
    except (gw.GatewayError, LifecycleError):
        logger.warning(
            "Payment reconciliation needs review order_id=%s gateway=%s",
            order.pk,
            order.payment_gateway or "unknown",
        )
        messages.warning(
            request,
            "We could not verify payment yet. Your order remains on hold; do not pay again.",
        )
    else:
        if result.status == Order.Status.PAID:
            messages.success(request, "Payment verified. Your order is paid.")
        elif result.stock_released_at:
            messages.info(request, "The order is closed and its reserved stock was released.")
        else:
            messages.info(request, "Payment is not confirmed yet. Check its status again later.")
    return _order_detail(order)


@login_required
@require_POST
def khalti_start(request, order_id):
    if not settings.KHALTI_SECRET_KEY:
        messages.error(request, "Khalti is not configured for this demo.")
        return redirect("store:product_list")

    order = get_object_or_404(
        Order,
        pk=order_id,
        user=request.user,
        status=Order.Status.PENDING,
        stock_released_at__isnull=True,
    )
    try:
        claim_payment_start(order.pk, owner_id=request.user.pk, gateway=Order.Gateway.KHALTI)
        data = gw.khalti_initiate(
            order=order,
            return_url=request.build_absolute_uri(reverse("payments:khalti_return")),
            website_url=request.build_absolute_uri("/"),
        )
        parsed_url = urlsplit(data["payment_url"])
        if (parsed_url.scheme != "https" or not parsed_url.hostname
                or parsed_url.username or parsed_url.password
                or parsed_url.port not in (None, 443)
                or not (parsed_url.hostname == "khalti.com"
                        or parsed_url.hostname.endswith(".khalti.com"))):
            raise gw.GatewayError("Khalti returned an unsafe payment URL.")
        record_payment_reference(
            order.pk,
            gateway=Order.Gateway.KHALTI,
            reference=data["pidx"],
        )
    except (gw.GatewayError, LifecycleError, KeyError, TypeError, ValueError):
        logger.warning("Khalti initiation needs review order_id=%s", order.pk)
        messages.error(
            request,
            "Payment start could not be confirmed. Do not retry this order; contact support.",
        )
        return _order_detail(order)
    return redirect(data["payment_url"])


@login_required
@require_GET
def khalti_return(request):
    pidx = request.GET.get("pidx", "")
    if not pidx:
        messages.error(request, "Missing payment reference.")
        return redirect("store:product_list")
    order = get_object_or_404(
        Order,
        payment_ref=pidx,
        payment_gateway=Order.Gateway.KHALTI,
        user=request.user,
    )
    return _check_and_report(request, order)


@login_required
@require_POST
def esewa_start(request, order_id):
    if not settings.ESEWA_PRODUCT_CODE or not settings.ESEWA_SECRET_KEY:
        messages.error(request, "eSewa is not configured for this demo.")
        return redirect("store:product_list")

    order = get_object_or_404(
        Order,
        pk=order_id,
        user=request.user,
        status=Order.Status.PENDING,
        stock_released_at__isnull=True,
    )
    try:
        claim_payment_start(order.pk, owner_id=request.user.pk, gateway=Order.Gateway.ESEWA)
        transaction_uuid = f"{order.pk}-{uuid.uuid4().hex[:12]}"
        fields = gw.esewa_form_fields(
            order=order,
            transaction_uuid=transaction_uuid,
            success_url=request.build_absolute_uri(reverse("payments:esewa_success")),
            failure_url=request.build_absolute_uri(
                reverse("payments:esewa_failure", args=[order.pk])
            ),
        )
        record_payment_reference(
            order.pk,
            gateway=Order.Gateway.ESEWA,
            reference=transaction_uuid,
        )
    except (gw.GatewayError, LifecycleError):
        logger.warning("eSewa initiation needs review order_id=%s", order.pk)
        messages.error(
            request,
            "Payment start could not be confirmed. Do not retry this order; contact support.",
        )
        return _order_detail(order)
    return render(request, "payments/esewa_redirect.html", {
        "fields": fields,
        "action": settings.ESEWA_FORM_URL,
    })


@login_required
@require_GET
def esewa_success(request):
    try:
        data = gw.esewa_decode_and_verify(request.GET.get("data", ""))
    except gw.GatewayError:
        messages.error(request, "Untrusted payment callback rejected.")
        return redirect("store:product_list")

    reference = data.get("transaction_uuid")
    if not isinstance(reference, str) or not reference:
        messages.error(request, "Payment callback does not identify an order.")
        return redirect("store:product_list")
    order = get_object_or_404(
        Order,
        payment_ref=reference,
        payment_gateway=Order.Gateway.ESEWA,
        user=request.user,
    )
    if (data.get("status") != "COMPLETE"
            or gw.parse_amount(data.get("total_amount")) != order.total_amount):
        messages.warning(request, "Payment is not confirmed. Check its status before taking action.")
        return _order_detail(order)
    return _check_and_report(request, order)


@login_required
@require_GET
def esewa_failure(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    messages.warning(
        request,
        "Payment is not confirmed. Reserved stock remains on hold; check its status.",
    )
    return _order_detail(order)


@login_required
@require_POST
def check_payment(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    return _check_and_report(request, order)
