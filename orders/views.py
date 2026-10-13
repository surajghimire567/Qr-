from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from cart.cart import Cart

from .forms import CheckoutForm
from .models import Order
from .services import OutOfStock, create_order_from_cart


@login_required
def checkout(request):
    cart = Cart(request)
    if len(cart) == 0:
        messages.info(request, "Your cart is empty.")
        return redirect("cart:cart_detail")

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            try:
                order = create_order_from_cart(user=request.user, cart=cart, form=form)
            except OutOfStock as exc:
                messages.error(request, f"Sorry, '{exc}' no longer has enough stock.")
                return redirect("cart:cart_detail")
            cart.clear()
            messages.success(request, f"Order #{order.pk} created. Payment is next.")
            return redirect("orders:order_detail", order_id=order.pk)   # PRG
    else:
        last = request.user.orders.first()            # prefill from the previous order
        initial = ({"full_name": last.full_name, "phone": last.phone, "address": last.address}
                   if last else {"full_name": request.user.get_full_name()})
        form = CheckoutForm(initial=initial)

    return render(request, "orders/checkout.html", {"form": form, "cart": cart})


@login_required
@require_GET
def order_detail(request, order_id):
    # IDOR gate: filter by owner IN THE QUERY. Someone else's id -> 404, not 403.
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product"),
        pk=order_id,
        user=request.user,
    )
    return render(request, "orders/order-detail.html", {"order": order})