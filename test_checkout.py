#!/usr/bin/env python
"""Manually verify checkout functionality.

Run with: python manage.py shell < test_checkout.py
"""

from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory

from cart.cart import Cart
from orders.forms import CheckoutForm
from orders.services import create_order_from_cart
from store.models import Product


def main():
    print("=" * 50)
    print("CHECKOUT FUNCTIONALITY TEST")
    print("=" * 50)

    products = Product.objects.filter(is_active=True, stock__gt=0)
    print(f"\n1. Active products with stock: {products.count()}")
    product = products.first()
    if not product:
        print("   No active products with stock; nothing to check.")
        return
    print(
        f"   Sample product: {product.name} "
        f"(stock: {product.stock}, price: Rs.{product.price})"
    )

    user = User.objects.first()
    print(f"\n2. Total users: {User.objects.count()}")
    if not user:
        print("   No users found; create a user before running this script.")
        return
    print(f"   Sample user: {user.username}")

    print("\n3. Testing Cart:")
    request = RequestFactory().post("/fake/")
    SessionMiddleware(lambda response: response).process_request(request)
    request.session.save()
    request.user = user

    cart = Cart(request)
    cart.add(product, quantity=2)
    print(f"   Added {product.name} x2 to cart")
    print(f"   Cart length: {len(cart)}")
    print(f"   Cart total: Rs.{cart.get_total_price()}")

    print("\n4. Testing CheckoutForm:")
    form = CheckoutForm(
        data={
            "full_name": "Test User",
            "phone": "9841234567",
            "address": "Kathmandu, Nepal",
        }
    )
    print(f"   Form valid: {form.is_valid()}")
    if not form.is_valid():
        print(f"   Form errors: {form.errors}")
        return

    print("\n5. Testing Order Creation:")
    try:
        order = create_order_from_cart(user=user, cart=cart, form=form)
        print(f"   Order #{order.pk} created successfully!")
        print(f"   Status: {order.get_status_display()}")
        print(f"   Total: Rs.{order.total_amount}")
        print(f"   Items: {order.items.count()}")
    except Exception as exc:
        print(f"   Error creating order: {exc}")

    print("\n" + "=" * 50)
    print("TEST COMPLETE")
    print("=" * 50)


if __name__ == "__main__":
    main()
