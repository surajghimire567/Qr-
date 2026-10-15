from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from store.models import Product

from .models import Order, OrderItem


class OutOfStock(Exception):
    """A cart line no longer has enough active stock to fulfill."""


class LifecycleError(Exception):
    """An order transition is unsafe or conflicts with provider state."""


def create_order_from_cart(*, user, cart, form, checkout_key=None):
    """Create an order and reserve each cart quantity in one transaction."""
    if checkout_key:
        existing = Order.objects.filter(user=user, checkout_key=checkout_key).first()
        if existing:
            return existing

    lines = list(cart)  # Cart re-reads current products and prices from the database.
    if not lines:
        raise ValueError("Cart is empty")

    try:
        with transaction.atomic():
            if checkout_key:
                existing = Order.objects.filter(user=user, checkout_key=checkout_key).first()
                if existing:
                    return existing

            product_ids = [line["product"].id for line in lines]
            locked_products = {
                product.pk: product
                for product in Product.objects.select_for_update()
                .filter(pk__in=product_ids, is_active=True)
                .order_by("pk")
            }

            order = form.save(commit=False)
            order.user = user
            order.checkout_key = checkout_key
            order.status = Order.Status.PENDING
            order.save()

            total = Decimal("0.00")
            items = []
            for line in lines:
                product = locked_products.get(line["product"].pk)
                quantity = line["quantity"]
                if (product is None or not isinstance(quantity, int)
                        or isinstance(quantity, bool) or quantity < 1):
                    raise OutOfStock(line["product"].name)

                changed = Product.objects.filter(
                    pk=product.pk,
                    is_active=True,
                    stock__gte=quantity,
                ).update(stock=F("stock") - quantity)
                if changed != 1:
                    raise OutOfStock(product.name)

                items.append(OrderItem(
                    order=order,
                    product=product,
                    price=product.price,
                    quantity=quantity,
                ))
                total += product.price * quantity

            OrderItem.objects.bulk_create(items)
            order.total_amount = total
            order.save(update_fields=["total_amount", "updated_at"])
        return order
    except IntegrityError:
        # A duplicate checkout POST can race another request. The unique key makes
        # only one order authoritative; the loser returns that same order.
        if checkout_key:
            existing = Order.objects.filter(user=user, checkout_key=checkout_key).first()
            if existing:
                return existing
        raise


@transaction.atomic
def release_unpaid(order_id, *, expected_ref=None, terminal=Order.Status.CANCELLED,
                   owner_id=None):
    """Close an unpaid order and restore its reserved stock exactly once.

    Customer cancellation passes no expected_ref and is therefore allowed only
    before a gateway has claimed or recorded an initiation. Provider outcomes
    must pass the stored reference and an explicitly terminal order status.
    """
    if terminal not in {Order.Status.CANCELLED, Order.Status.FAILED}:
        raise LifecycleError("Only terminal unpaid statuses can release stock.")

    orders = Order.objects.select_for_update()
    if owner_id is not None:
        orders = orders.filter(user_id=owner_id)
    try:
        order = orders.get(pk=order_id)
    except Order.DoesNotExist as exc:
        raise LifecycleError("Order is not available for this account.") from exc

    if order.stock_released_at is not None:
        if (order.status == terminal
                and (expected_ref is None or order.payment_ref == expected_ref)):
            return order
        raise LifecycleError("Order stock was already released in another state.")

    if order.status != Order.Status.PENDING:
        raise LifecycleError("Only pending orders can release stock.")
    if order.payment_starting:
        raise LifecycleError("Payment initiation needs review before stock can be released.")
    if expected_ref is None:
        if order.payment_ref or order.payment_gateway:
            raise LifecycleError("Payment was started; verify it before cancelling.")
    elif not expected_ref or order.payment_ref != expected_ref:
        raise LifecycleError("Payment identity mismatch.")

    for item in order.items.select_related("product").order_by("product_id", "pk"):
        changed = Product.objects.filter(pk=item.product_id).update(
            stock=F("stock") + item.quantity,
        )
        if changed != 1:
            raise LifecycleError("An ordered product is unavailable; reconcile manually.")

    order.status = terminal
    order.stock_released_at = timezone.now()
    order.save(update_fields=["status", "stock_released_at", "updated_at"])
    return order
