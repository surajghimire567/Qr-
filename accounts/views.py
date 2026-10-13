from django.contrib.auth import login
from django.shortcuts import redirect, render

from .forms import RegisterForm
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