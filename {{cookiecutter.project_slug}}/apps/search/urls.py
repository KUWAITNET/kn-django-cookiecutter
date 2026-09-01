"""Search URLs, mounted at /search/ by the project URLconf."""

from django.urls import path

from apps.search import views

app_name = "search"

urlpatterns = [
    path("", views.search, name="search"),
]
