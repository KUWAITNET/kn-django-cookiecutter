from django.apps import AppConfig


class CitiesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cities"
    # Must equal settings.CITIES_LIGHT_APP_NAME. django-cities-light resolves its
    # concrete models through this *label*, not through the dotted path, so a
    # mismatch fails at import with a confusing "app not found".
    label = "cities"
    verbose_name = "Countries"
