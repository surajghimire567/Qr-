import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from cart.cart import Cart

from .forms import CheckoutForm
from .models import Order
from .services import LifecycleError, OutOfStock, create_order_from_cart, release_unpaid


@login_required
def checkout(request):
    cart = Cart(request)

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            checkout_key = form.cleaned_data["checkout_key"]
            existing = Order.objects.filter(
                user=request.user,
                checkout_key=checkout_key,
            ).first()
            if existing:
                return redirect("orders:order_detail", order_id=existing.pk)

            if str(checkout_key) != request.session.get("checkout_key"):
                form.add_error(None, "This checkout expired. Please review your cart and try again.")
            else:
                try:
                    order = create_order_from_cart(
                        user=request.user,
                        cart=cart,
                        form=form,
                        checkout_key=checkout_key,
                    )
                except OutOfStock as exc:
                    messages.error(request, f"Sorry, '{exc}' no longer has enough stock.")
                    return redirect("cart:cart_detail")
                except ValueError:
                    messages.info(request, "Your cart is empty or no longer has available items.")
                    return redirect("cart:cart_detail")

                cart.clear()
                messages.success(request, f"Order #{order.pk} created. Payment is next.")
                return redirect("orders:order_detail", order_id=order.pk)
    else:
        # Iterating removes products that have since been deleted or deactivated.
        list(cart)
        if len(cart) == 0:
            messages.info(request, "Your cart is empty.")
            return redirect("cart:cart_detail")

        last = request.user.orders.first()
        initial = {
            "full_name": last.full_name if last else request.user.get_full_name(),
            "phone": last.phone if last else "",
            "address": last.address if last else "",
        }
        checkout_key = request.session.get("checkout_key")
        if checkout_key and Order.objects.filter(
                user=request.user, checkout_key=checkout_key).exists():
            checkout_key = None
        if not checkout_key:
            checkout_key = str(uuid.uuid4())
            request.session["checkout_key"] = checkout_key
        initial["checkout_key"] = checkout_key
        form = CheckoutForm(initial=initial)

    return render(request, "orders/checkout.html", {"form": form, "cart": cart})


@login_required
@require_GET
def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product"),
        pk=order_id,
        user=request.user,
    )
    return render(request, "orders/order-detail.html", {
        "order": order,
        "khalti_enabled": bool(settings.KHALTI_SECRET_KEY),
        "esewa_enabled": bool(settings.ESEWA_PRODUCT_CODE and settings.ESEWA_SECRET_KEY),
    })


@login_required
@require_POST
def cancel_order(request, order_id):
    try:
        order = release_unpaid(
            order_id,
            owner_id=request.user.pk,
            terminal=Order.Status.CANCELLED,
        )
    except LifecycleError:
        messages.warning(request, "This order cannot be cancelled safely. Check its payment status.")
    else:
        messages.success(request, f"Order #{order.pk} cancelled; its reserved stock was released.")
    return redirect("orders:order_detail", order_id=order_id)
