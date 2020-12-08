from .base import *
import os

DATABASES = {
    "default": {
        "ENGINE": os.environ.get("SQL_ENGINE", "django.db.backends.mysql"),
        "NAME": os.environ.get("SQL_DATABASE", "hello_django_dev"),
        "USER": os.environ.get("SQL_USER", "hello_django"),
        "PASSWORD": os.environ.get("SQL_PASSWORD", "hello_django"),
        "HOST": "db",
        "PORT": os.environ.get("SQL_PORT", ""),
    },
}
