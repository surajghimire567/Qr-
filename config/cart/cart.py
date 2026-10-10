from decimal import Decimal

from django.conf import settings
from store.models import Product


class Cart:
    def __init__(self, request):
        self.session = request.session
        # don't create the key yet -- an empty cart costs nothing until add()
        self.cart = self.session.get(settings.CART_SESSION_ID, {})

    def add(self, product, quantity=1, override_quantity=False):
        pid = str(product.id)  # JSON object keys are always strings
        current = self.cart.get(pid, {"quantity": 0})["quantity"]
        new_qty = quantity if override_quantity else current + quantity
        new_qty = min(new_qty, product.stock)  # never more than we can sell

        if new_qty < 1:
            self.cart.pop(pid, None)  # 0 stock or 0 qty -> not in cart
        else:
            self.cart[pid] = {"quantity": new_qty}

        self.save()
        return new_qty

    def remove(self, product_id):
        pid = str(product_id)  # by id: works even if the product was deleted
        if pid in self.cart:
            del self.cart[pid]
            self.save()

    def save(self):
        self.session[settings.CART_SESSION_ID] = self.cart
        self.session.modified = True  # nested dict changes aren't auto-detected

    def clear(self):  # Day 4: called after the order is created
        self.session.pop(settings.CART_SESSION_ID, None)
        self.session.modified = True
        self.cart = {}

    def __iter__(self):
        product_ids = self.cart.keys()
        products = Product.objects.filter(id__in=product_ids, is_active=True)
        found = set()

        for product in products:  # ONE query, prices come from the DB
            pid = str(product.id)
            found.add(pid)
            quantity = self.cart[pid]["quantity"]
            yield {
                "product": product,
                "quantity": quantity,
                "price": product.price,
                "total_price": product.price * quantity,
            }

        stale = set(self.cart) - found  # deleted or deactivated since added
        if stale:
            for pid in stale:
                del self.cart[pid]
            self.save()

    def __len__(self):  # total units -- no DB query
        return sum(item["quantity"] for item in self.cart.values())

    def get_total_price(self):
        return sum((item["total_price"] for item in self), Decimal("0.00"))
