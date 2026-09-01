"""Newsletter URLs, mounted at /newsletter/ outside the language prefix.

Confirmation and unsubscribe links live in e-mail that outlives any redesign,
so their paths must not change when the site's language routing does.
"""

from django.urls import path

from apps.newsletter import views

app_name = "newsletter"

urlpatterns = [
    path("subscribe/", views.subscribe, name="subscribe"),
    path("confirm/<uuid:token>/", views.confirm, name="confirm"),
    path("unsubscribe/<uuid:token>/", views.unsubscribe, name="unsubscribe"),
]
