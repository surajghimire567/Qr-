from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("<int:order_id>/cancel/", views.cancel_order, name="cancel_order"),
    path("<int:order_id>/", views.order_detail, name="order_detail"),
]
