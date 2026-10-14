from copy import deepcopy
from decimal import Decimal

from django.conf import settings
from store.models import Product

from .models import SavedCart


class Cart:
    def __init__(self, request):
        self.request = request
        self.session = request.session
        self.user = request.user if request.user.is_authenticated else None

        if self.user is None:
            # Guest carts live in the session until the customer signs in.
            self.saved_cart = None
            self.cart = self.session.get(settings.CART_SESSION_ID, {})
            return

        # The template context processor and views may each create a Cart during
        # one request, so reuse the saved-cart lookup for that request.
        if not hasattr(request, "_saved_cart_record_loaded"):
            request._saved_cart_record = SavedCart.objects.filter(user=self.user).first()
            request._saved_cart_record_loaded = True
        self.saved_cart = request._saved_cart_record
        self.cart = deepcopy(self.saved_cart.items) if self.saved_cart else {}

        # Preserve items collected before login by combining them with the
        # account's saved cart, then remove the old session copy.
        guest_cart = self.session.get(settings.CART_SESSION_ID, {})
        if guest_cart:
            for product_id, item in guest_cart.items():
                old_quantity = self.cart.get(product_id, {}).get("quantity", 0)
                self.cart[product_id] = {
                    "quantity": old_quantity + item.get("quantity", 0)
                }
            self.session.pop(settings.CART_SESSION_ID, None)
            self.session.modified = True
            self.save()

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
        if self.user is None:
            self.session[settings.CART_SESSION_ID] = self.cart
            self.session.modified = True  # nested dict changes aren't auto-detected
            return

        if self.saved_cart is None:
            self.saved_cart = SavedCart.objects.create(user=self.user, items=self.cart)
        else:
            self.saved_cart.items = self.cart
            self.saved_cart.save(update_fields=["items", "updated_at"])
        self.request._saved_cart_record = self.saved_cart
        self.request._saved_cart_record_loaded = True
        if self.session.pop(settings.CART_SESSION_ID, None) is not None:
            self.session.modified = True

    def clear(self):  # Day 4: called after the order is created
        self.cart = {}
        if self.user is None:
            self.session.pop(settings.CART_SESSION_ID, None)
            self.session.modified = True
        else:
            self.save()

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
