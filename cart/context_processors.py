from .cart import Cart


def cart(request):
    # Avoid loading product details just to show the count in the header.
    return {"cart_count": len(Cart(request))}
