"""ASGI entry point. Defaults to production settings."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", "{{ cookiecutter.project_slug }}.settings.production"
)

application = get_asgi_application()
