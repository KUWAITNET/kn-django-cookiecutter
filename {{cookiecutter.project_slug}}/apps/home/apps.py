"""Application configuration for the home app."""

from django.apps import AppConfig


class HomeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.home"
    label = "home"
    verbose_name = "Home page"
