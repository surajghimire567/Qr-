from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from store.models import Product

from .cart import Cart
from .forms import CartAddProductForm


@require_POST
def cart_add(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id, is_active=True)
    form = CartAddProductForm(request.POST)

    if not form.is_valid():
        messages.error(request, "Please choose a quantity between 1 and 20.")
        return redirect(product.get_absolute_url())

    if not product.in_stock:
        messages.error(request, f"Sorry, {product.name} is out of stock.")
        return redirect(product.get_absolute_url())

    cd = form.cleaned_data
    requested = cd["quantity"]
    new_qty = cart.add(product, quantity=requested, override_quantity=cd["override"])

    if new_qty < (requested if cd["override"] else new_qty):
        messages.warning(request, f"Only {product.stock} of {product.name} available.")
    else:
        messages.success(request, f"{product.name} - quantity in cart: {new_qty}.")

    return redirect("cart:cart_detail")


@require_POST
def cart_remove(request, product_id):
    Cart(request).remove(product_id)  # no DB lookup: deleted products can be removed too
    messages.info(request, "Item removed.")
    return redirect("cart:cart_detail")


def cart_detail(request):
    cart = Cart(request)
    items = list(cart)  # evaluate once: 1 query, prunes stale ids

    for item in items:
        item["update_form"] = CartAddProductForm(
            initial={"quantity": item["quantity"], "override": True}
        )

    total = sum((i["total_price"] for i in items), 0)
    return render(request, "cart/detail.html", {"items": items, "total": total})
