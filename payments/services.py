from django.db import transaction
from django.utils import timezone

from orders.models import Order


def mark_paid(order_id, ref):
    """Idempotent: a double callback / refresh can't pay twice."""
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)
        if order.status == Order.Status.PAID:
            return order
        order.status = Order.Status.PAID
        order.payment_ref = ref
        order.paid_at = timezone.now()
        order.save(update_fields=["status", "payment_ref", "paid_at", "updated_at"])
        return order


def mark_failed(order_id):
    Order.objects.filter(pk=order_id, status=Order.Status.PENDING).update(
        status=Order.Status.FAILED, updated_at=timezone.now())