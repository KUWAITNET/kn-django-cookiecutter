"""Application configuration for the newsroom app."""

from django.apps import AppConfig


class NewsroomConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.newsroom"
    label = "newsroom"
    verbose_name = "Newsroom"
