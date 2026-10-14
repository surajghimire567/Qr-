"""Keep Django admin authentication separate from storefront authentication."""

import time
from importlib import import_module

from django.conf import settings
from django.contrib.auth import logout
from django.contrib.sessions.exceptions import SessionInterrupted, UpdateError
from django.utils.cache import patch_vary_headers
from django.utils.http import http_date


class AdminSessionMiddleware:
    """Use a separate session cookie for requests served under ``/admin/``."""

    def __init__(self, get_response):
        self.get_response = get_response
        engine = import_module(settings.SESSION_ENGINE)
        self.SessionStore = engine.SessionStore

    def __call__(self, request):
        if not request.path_info.startswith("/admin/"):
            return self.get_response(request)

        storefront_session = request.session
        cookie_name = settings.ADMIN_SESSION_COOKIE_NAME
        admin_session = self.SessionStore(request.COOKIES.get(cookie_name))
        request.session = admin_session
        try:
            response = self.get_response(request)
        except Exception:
            request.session = storefront_session
            raise
        request.session = storefront_session

        accessed = admin_session.accessed
        modified = admin_session.modified
        empty = admin_session.is_empty()
        need_vary_cookie = accessed

        if cookie_name in request.COOKIES and empty:
            response.delete_cookie(
                cookie_name,
                path=settings.ADMIN_SESSION_COOKIE_PATH,
                domain=settings.SESSION_COOKIE_DOMAIN,
                samesite=settings.SESSION_COOKIE_SAMESITE,
            )
            need_vary_cookie = True
        elif (modified or settings.SESSION_SAVE_EVERY_REQUEST) and not empty:
            if response.status_code < 500:
                if admin_session.get_expire_at_browser_close():
                    max_age = None
                    expires = None
                else:
                    max_age = admin_session.get_expiry_age()
                    expires = http_date(time.time() + max_age)

                try:
                    admin_session.save()
                except UpdateError as exc:
                    raise SessionInterrupted(
                        "The admin session was deleted before the request completed."
                    ) from exc

                response.set_cookie(
                    cookie_name,
                    admin_session.session_key,
                    max_age=max_age,
                    expires=expires,
                    domain=settings.SESSION_COOKIE_DOMAIN,
                    path=settings.ADMIN_SESSION_COOKIE_PATH,
                    secure=settings.SESSION_COOKIE_SECURE or None,
                    httponly=settings.SESSION_COOKIE_HTTPONLY or None,
                    samesite=settings.SESSION_COOKIE_SAMESITE,
                )
                need_vary_cookie = True

        if need_vary_cookie:
            patch_vary_headers(response, ("Cookie",))
        return response


class StorefrontStaffLogoutMiddleware:
    """Do not treat an admin/staff identity as a signed-in shop customer."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (not request.path_info.startswith("/admin/")
                and request.user.is_authenticated and request.user.is_staff):
            # This only flushes the storefront session. The admin uses its own
            # separate cookie and session store.
            logout(request)
        return self.get_response(request)
