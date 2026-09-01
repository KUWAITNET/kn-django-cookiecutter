"""Application configuration for the navigation app."""

from django.apps import AppConfig


class NavigationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.navigation"
    label = "navigation"
    verbose_name = "Navigation and site settings"
