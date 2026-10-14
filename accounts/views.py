from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import ProfileForm, RegisterForm
from django.utils.http import url_has_allowed_host_and_scheme


def safe_next(request, fallback="store:product_list"):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()},
                                               require_https=request.is_secure()):
        return nxt
    return fallback

def register(request):
    if request.user.is_authenticated:
        return redirect("store:product_list")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()            # password is hashed by UserCreationForm
            login(request, user)          # session key rotates; cart survives
            return redirect(safe_next(request))
    else:
        form = RegisterForm()
    return render(request, "registration/register.html",
                  {"form": form, "next": request.GET.get("next", "")})


@login_required
def profile(request):
    recent_orders = request.user.orders.all()[:5]
    return render(request, "accounts/profile.html", {"recent_orders": recent_orders})


@login_required
def personal_information(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your personal information has been updated.")
            return redirect("accounts:personal_information")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "accounts/personal_information.html", {"form": form})


@login_required
def order_history(request):
    orders = request.user.orders.all()
    return render(request, "accounts/order_history.html", {"orders": orders})
