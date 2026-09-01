"""API URLs, mounted at ``/api/`` by the project URLconf (api-standard.md A1, A3).

Layout:

- ``/api/v1/...`` - every application endpoint. The major version is in the path,
  never in a header, never in a query parameter, never negotiated by media type.
  A version that is not served has no route and therefore 404s, rather than
  silently falling back to the default.
- ``/api/schema/``, ``/api/docs/``, ``/api/redoc/`` - the generated contract and
  its two UIs, registered only when ``settings.API_DOCS_ENABLED``.

A new major version is a **new URL prefix served alongside the old one**, never a
cut-over: add ``path("v2/", include((v2_patterns, "v2")))`` here, keep ``v1``
running for the whole deprecation window, and add "v2" to
``REST_FRAMEWORK["ALLOWED_VERSIONS"]``. There is no ``/api/v1.1/``; additive
evolution is visible in the committed OpenAPI diff, and that is where clients
read it.

Resource paths are plural nouns in kebab-case, with verbs in the HTTP method. The
one permitted exception is a documented non-CRUD action expressed as a sub-path
(``/api/v1/notes/{uuid}/publish/``). Trailing slashes are consistent throughout.
"""

from django.conf import settings
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.routers import SimpleRouter

from apps.api import views

# SimpleRouter, not DefaultRouter: we want neither the browsable API root nor the
# ".json" format-suffix routes, both of which are surface nobody asked for.
router = SimpleRouter()
router.register("notes", views.NoteViewSet, basename="note")

auth_patterns = [
    path("token/", views.ThrottledTokenObtainPairView.as_view(), name="token-obtain"),
    path("token/refresh/", views.RotatingTokenRefreshView.as_view(), name="token-refresh"),
    path("token/verify/", views.DocumentedTokenVerifyView.as_view(), name="token-verify"),
    # Logout. The refresh token is blacklisted; the access token expires on its
    # own, which is why its lifetime is 15 minutes.
    path("token/blacklist/", views.DocumentedTokenBlacklistView.as_view(), name="token-blacklist"),
]

v1_patterns = [
    path("status/", views.APIStatusView.as_view(), name="api-status"),
    # Staff-gated by IsStaffUser on the view - not by this path being obscure.
    path(
        "diagnostics/integration/",
        views.IntegrationDiagnosticView.as_view(),
        name="integration-diagnostic",
    ),
    path("auth/", include(auth_patterns)),
    path("", include(router.urls)),
]

urlpatterns = [
    path("v1/", include((v1_patterns, "v1"))),
]

# The docs UI is on in development and staging and off in production. It is
# gated by a setting, never by an obscure URL: a path is not authentication - it
# leaks through Referer headers, browser history, CDN and proxy access logs and
# Sentry breadcrumbs, and it cannot be revoked. A partner who needs the docs gets
# a rendered copy of the schema out of band, or an account with a docs
# permission; they do not get a secret URL.
if settings.API_DOCS_ENABLED:
    urlpatterns += [
        path("schema/", SpectacularAPIView.as_view(), name="schema"),
        path(
            "docs/",
            SpectacularSwaggerView.as_view(url_name="schema"),
            name="swagger-ui",
        ),
        path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    ]
