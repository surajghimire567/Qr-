from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("SECRET_KEY")  # no default -> crash if missing (good)
DEBUG = config("DEBUG", default=False, cast=bool)  # "True" string -> True bool
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="127.0.0.1,localhost", cast=Csv())

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # local apps
    "store",
    "orders",
    "cart",
    "accounts",
    "payments",
    

    

]
CART_SESSION_ID = "cart" # the key inside request.session
ADMIN_SESSION_COOKIE_NAME = "adminsessionid"
ADMIN_SESSION_COOKIE_PATH = "/admin/"


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "config.middleware.AdminSessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "config.middleware.StorefrontStaffLogoutMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # project-level templates (base.html)
        "APP_DIRS": True,  # also search <app>/templates/
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "cart.context_processors.cart", 
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kathmandu"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]  # project-level CSS/JS

MEDIA_URL = "/media/"  # URL prefix for uploaded files
MEDIA_ROOT = BASE_DIR / "media"  # folder on disk for uploaded files

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "store:product_list"
LOGOUT_REDIRECT_URL = "store:product_list" 

# ---- Day 5: payment gateways (real values live in .env) ----
KHALTI_SECRET_KEY = config("KHALTI_SECRET_KEY", default="")
KHALTI_BASE_URL = config("KHALTI_BASE_URL", default="https://dev.khalti.com/api/v2/")
ESEWA_PRODUCT_CODE = config("ESEWA_PRODUCT_CODE", default="EPAYTEST")
ESEWA_SECRET_KEY = config("ESEWA_SECRET_KEY", default="8gBm/:&EnhH.1/q")  # public sandbox key
ESEWA_FORM_URL = config("ESEWA_FORM_URL", default="https://rc-epay.esewa.com.np/api/epay/main/v2/form")
ESEWA_STATUS_URL = config("ESEWA_STATUS_URL", default="https://rc.esewa.com.np/api/epay/transaction/status/")
