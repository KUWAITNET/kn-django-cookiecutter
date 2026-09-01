"""Project-level views: operational endpoints, protected media and error pages."""

import logging
from pathlib import Path

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connections
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.template import TemplateDoesNotExist
{%- if cookiecutter.frontend != "api_only" %}
from django.urls import NoReverseMatch, reverse
{%- endif %}
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

logger = logging.getLogger("{{ cookiecutter.project_slug }}")

#: Permission required to download anything under ``PRIVATE_MEDIA_ROOT``. It hangs
#: off ``apps.core.models.PrivateMediaAccess``; grant it to the staff group that
#: legitimately reads submissions, never to everyone with ``is_staff``.
PRIVATE_MEDIA_PERMISSION = "core.access_private_media"


# --- Operational endpoints ---------------------------------------------------
{%- if cookiecutter.frontend != "api_only" %}


@require_safe
def robots_txt(request):
    """``/robots.txt``, pointing crawlers at the sitemap.

    Serves ``Disallow: /`` whenever ``DEBUG`` is on or ``ROBOTS_DISALLOW_ALL`` is
    set. Staging and UAT hosts must never be indexed - a staging copy of a client
    site ranking alongside the real one is a real incident, and the fix after the
    fact is slow.
    """
    try:
        sitemap_url = request.build_absolute_uri(reverse("sitemap"))
    except NoReverseMatch:
        sitemap_url = ""
    context = {
        "sitemap_url": sitemap_url,
        "robots_disallow_all": bool(settings.DEBUG or settings.ROBOTS_DISALLOW_ALL),
    }
    return render(request, "robots.txt", context, content_type="text/plain")
{%- endif %}


@never_cache
@require_safe
def healthz(request):
    """Liveness probe that actually touches the database.

    A probe that only proves Python is running reports "healthy" while every page
    is a 500 because the database is unreachable, so this issues a trivial query.
    """
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        logger.exception("Health check failed: database unreachable")
        return JsonResponse({"status": "error", "database": "unavailable"}, status=503)
    return JsonResponse({"status": "ok", "database": "ok"})
{%- if cookiecutter.sentry == "yes" %}


def trigger_error(request):
    """Raise on purpose, to confirm events reach Sentry.

    ``urls.py`` registers this only when a DSN is configured *and* DEBUG is on, so
    it can never be routable in production - an unauthenticated endpoint that
    forces a 500 is a free log- and quota-flood.
    """
    return 1 / 0
{%- endif %}


# --- Protected media ---------------------------------------------------------


@require_safe
def serve_private_file(request, relative_path):
    """Serve a file from ``PRIVATE_MEDIA_ROOT`` after checking permission.

    Uploads holding personal data are never reachable from ``MEDIA_URL``: in our
    reference project applicant CVs sat under a world-readable ``MEDIA_ROOT``
    with their original filenames, so anyone who guessed a name could read them.
    """
    user = request.user
    if not user.is_authenticated or not user.has_perm(PRIVATE_MEDIA_PERMISSION):
        raise PermissionDenied

    root = Path(settings.PRIVATE_MEDIA_ROOT).resolve()
    # resolve() collapses "..", symlinks and absolute-path injection; comparing
    # the resolved result against the root is what stops ../../etc/passwd.
    target = (root / str(relative_path)).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise Http404

    response = FileResponse(target.open("rb"), as_attachment=True, filename=target.name)
    # Belt and braces with the site-wide setting: a private download must never be
    # interpreted as HTML by a browser that disagrees with our Content-Type.
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response
{%- if cookiecutter.stack == "django" and cookiecutter.frontend != "api_only" %}


# --- Pages -------------------------------------------------------------------


#: Top-level navigation for the server-rendered shell. A list rather than a
#: model because a plain-Django project has no CMS to edit one in; replace it
#: with a query when the project grows real navigable content.
NAV_ITEMS = [
    {"label": "Home", "url_name": "home"},
]


def _nav_items(request):
    items = []
    for entry in NAV_ITEMS:
        try:
            url = reverse(entry["url_name"])
        except NoReverseMatch:
            continue
        items.append({"label": entry["label"], "url": url, "is_active": request.path == url})
    return items


def home(request):
    return render(request, "core/home.html", {"nav_items": _nav_items(request)})
{%- endif %}


# --- Error handlers ----------------------------------------------------------
#
# Rendered from templates so the client's branding survives an error. The
# fallback exists because an API-only project has no HTML templates at all, and a
# TemplateDoesNotExist inside an error handler turns a 404 into a 500.


def _error_response(request, template_name, status):
    try:
        return render(request, template_name, status=status)
    except TemplateDoesNotExist:
        return HttpResponse(f"{status}", status=status, content_type="text/plain")


def bad_request(request, exception=None):
    return _error_response(request, "400.html", 400)


def permission_denied(request, exception=None):
    return _error_response(request, "403.html", 403)


def page_not_found(request, exception=None):
    return _error_response(request, "404.html", 404)


def server_error(request):
    return _error_response(request, "500.html", 500)
