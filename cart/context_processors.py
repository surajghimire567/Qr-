from .cart import Cart
def cart(request):
# runs on EVERY render(): keep it cheap. len(Cart) reads the session only -- no query.
 return {"cart_count": len(Cart(request))}
