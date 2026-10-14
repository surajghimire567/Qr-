import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from orders.models import Order

from . import gateways as gw
from .services import mark_failed, mark_paid


def _payable_order(request, order_id):
    # IDOR gate again: only the owner, only unpaid orders
    return get_object_or_404(Order, pk=order_id, user=request.user,
                             status__in=[Order.Status.PENDING, Order.Status.FAILED])


# ---------- Khalti ----------
@login_required
@require_POST
def khalti_start(request, order_id):
    order = _payable_order(request, order_id)
    try:
        data = gw.khalti_initiate(
            order=order,
            return_url=request.build_absolute_uri(reverse("payments:khalti_return")),
            website_url=request.build_absolute_uri("/"),
        )
    except gw.GatewayError as exc:
        messages.error(request, f"Could not start Khalti payment. {exc}")
        return redirect("orders:order_detail", order_id=order.pk)
    order.payment_ref = data["pidx"]          # remember which pidx belongs to this order
    order.status = Order.Status.PENDING
    order.save(update_fields=["payment_ref", "status", "updated_at"])
    return redirect(data["payment_url"])


@login_required
@require_GET
def khalti_return(request):
    pidx = request.GET.get("pidx", "")
    order = get_object_or_404(Order, payment_ref=pidx, user=request.user) if pidx else None
    if order is None:
        messages.error(request, "Missing payment reference.")
        return redirect("store:product_list")
    if order.status == Order.Status.PAID:
        return redirect("orders:order_detail", order_id=order.pk)
    try:
        info = gw.khalti_lookup(pidx)           # ignore GET ?status= -- ask Khalti
    except gw.GatewayError as exc:
        messages.error(request, f"Could not verify payment yet. {exc}")
        return redirect("orders:order_detail", order_id=order.pk)

    status = info.get("status")
    amount_ok = info.get("total_amount") == gw.to_paisa(order.total_amount)
    if status == "Completed" and amount_ok:
        mark_paid(order.pk, info.get("transaction_id") or pidx)
        messages.success(request, f"Payment verified. Order #{order.pk} is paid.")
    elif status in ("Pending", "Initiated"):
        messages.info(request, "Payment is still pending at Khalti. Refresh later.")
    else:
        mark_failed(order.pk)
        messages.error(request, f"Payment not completed ({status or 'unknown'}).")
    return redirect("orders:order_detail", order_id=order.pk)


# ---------- eSewa ----------
@login_required
@require_POST
def esewa_start(request, order_id):
    order = _payable_order(request, order_id)
    tx_uuid = f"{order.pk}-{uuid.uuid4().hex[:12]}"   # unique per attempt
    order.payment_ref = tx_uuid
    order.status = Order.Status.PENDING
    order.save(update_fields=["payment_ref", "status", "updated_at"])
    fields = gw.esewa_form_fields(
        order=order, transaction_uuid=tx_uuid,
        success_url=request.build_absolute_uri(reverse("payments:esewa_success")),
        failure_url=request.build_absolute_uri(
            reverse("payments:esewa_failure", args=[order.pk])),
    )
    return render(request, "payments/esewa_redirect.html",
                  {"fields": fields, "action": settings.ESEWA_FORM_URL})


@login_required
@require_GET
def esewa_success(request):
    try:
        data = gw.esewa_decode_and_verify(request.GET.get("data", ""))   # check 1: HMAC
    except gw.GatewayError as exc:
        messages.error(request, f"Payment rejected: {exc}")
        return redirect("store:product_list")

    order = get_object_or_404(Order, payment_ref=data.get("transaction_uuid"), user=request.user)
    if order.status == Order.Status.PAID:
        return redirect("orders:order_detail", order_id=order.pk)

    if gw.parse_amount(data.get("total_amount")) != order.total_amount:
        messages.error(request, "Amount mismatch. Payment not accepted.")
        return redirect("orders:order_detail", order_id=order.pk)

    try:                                                                  # check 2: ask eSewa
        st = gw.esewa_status(transaction_uuid=order.payment_ref,
                             total_amount=gw.esewa_amount(order.total_amount))
    except gw.GatewayError as exc:
        messages.error(request, f"Could not verify payment yet. {exc}")
        return redirect("orders:order_detail", order_id=order.pk)

    if data.get("status") == "COMPLETE" and st.get("status") == "COMPLETE":
        mark_paid(order.pk, st.get("ref_id") or data.get("transaction_code") or order.payment_ref)
        messages.success(request, f"Payment verified. Order #{order.pk} is paid.")
    else:
        messages.error(request, f"Payment not completed ({st.get('status', 'unknown')}).")
    return redirect("orders:order_detail", order_id=order.pk)


@login_required
@require_GET
def esewa_failure(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    mark_failed(order.pk)
    messages.error(request, "eSewa payment was cancelled or failed. You can retry.")
    return redirect("orders:order_detail", order_id=order.pk)