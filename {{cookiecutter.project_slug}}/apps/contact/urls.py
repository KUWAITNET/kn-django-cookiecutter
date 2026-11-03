{% if cookiecutter.stack == "django" and cookiecutter.frontend != "api_only" -%}
"""Public URLs for the contact app.

Namespaced, so a template links to it as {% raw %}{% url 'contact:contact' %}{% endraw %} and the path can
move without touching a template. The form posts to its own URL - there is no
separate submit endpoint, so a submission that fails validation re-renders in
place with the visitor's input intact.
"""

from django.urls import path

from apps.contact import views

app_name = "contact"

urlpatterns = [
    path("", views.contact, name="contact"),
]
{%- endif %}
