from django.shortcuts import get_object_or_404, render
from .models import Category, Product
def product_list(request, category_slug=None):
 category = None
 categories = Category.objects.all()
 products = Product.objects.filter(is_active=True).select_related("category")
 if category_slug: # same view, two URLs
  category = get_object_or_404(Category, slug=category_slug)
  products = products.filter(category=category)
 context = {
  "category": category,
  "categories": categories,
  "products": products,
 }
 return render(request, "store/product_list.html", context)
def product_detail(request, slug):
 product = get_object_or_404(
 Product.objects.select_related("category"),
 slug=slug,
 is_active=True, # hidden products must 404, not leak
 )
 related = (
 Product.objects.filter(category=product.category, is_active=True)
 .exclude(pk=product.pk)[:4]
 )
 return render(request, "store/product_detail.html",
 {"product": product, "related": related})