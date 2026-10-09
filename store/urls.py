from django.urls import path
from . import views
app_name = "store" # namespace -> {% url 'store:product_detail' ... %}
urlpatterns = [
 path("", views.product_list, name="product_list"),
 path("category/<slug:category_slug>/", views.product_list, name="product_list_by_category"),
 path("product/<slug:slug>/", views.product_detail, name="product_detail"),
]
