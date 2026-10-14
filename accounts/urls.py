from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("profile/", views.profile, name="profile"),
    path("profile/personal-information/", views.personal_information,
         name="personal_information"),
    path("profile/orders/", views.order_history, name="order_history"),
]
