{% if cookiecutter.stack == "django" and cookiecutter.frontend != "api_only" -%}
"""Public URLs served by the core app.

No ``app_name``: these are the site's own top-level pages, and the project URLconf
includes them at the root, so their names are unprefixed (``{% raw %}{% url 'home' %}{% endraw %}``).
"""

from django.urls import path

from apps.core import views

urlpatterns = [
    path("", views.home, name="home"),
]
{%- endif %}
