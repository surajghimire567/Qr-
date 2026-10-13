from decimal import Decimal

from django.db import transaction
from django.db.models import F

from store.models import Product

from .models import Order, OrderItem


class OutOfStock(Exception):
    pass


def create_order_from_cart(*, user, cart, form):
    """Turn the session cart into an Order. Raises OutOfStock; caller handles it."""
    lines = list(cart)                               # prices re-read from the DB by Cart.__iter__
    if not lines:
        raise ValueError("Cart is empty")

    with transaction.atomic():
        ids = [line["product"].id for line in lines]
        locked = {p.id: p for p in
                  Product.objects.select_for_update().filter(id__in=ids, is_active=True)}

        order = form.save(commit=False)
        order.user = user                            # owner comes from the session, not the form
        order.status = Order.Status.PENDING
        order.save()

        total = Decimal("0.00")
        items = []
        for line in lines:
            product = locked.get(line["product"].id)
            qty = line["quantity"]
            if product is None or product.stock < qty:
                raise OutOfStock(line["product"].name)   # rolls back the whole order
            items.append(OrderItem(order=order, product=product,
                                   price=product.price,  # snapshot
                                   quantity=qty))
            total += product.price * qty
            Product.objects.filter(pk=product.pk).update(stock=F("stock") - qty)

        OrderItem.objects.bulk_create(items)
        order.total_amount = total
        order.save(update_fields=["total_amount"])
    return order