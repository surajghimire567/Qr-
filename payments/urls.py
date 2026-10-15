from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("khalti/<int:order_id>/start/", views.khalti_start, name="khalti_start"),
    path("khalti/return/", views.khalti_return, name="khalti_return"),
    path("esewa/<int:order_id>/start/", views.esewa_start, name="esewa_start"),
    path("esewa/success/", views.esewa_success, name="esewa_success"),
    path("esewa/<int:order_id>/failure/", views.esewa_failure, name="esewa_failure"),
    path("<int:order_id>/check/", views.check_payment, name="check_payment"),
]
