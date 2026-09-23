"""Project-level views: operational endpoints, protected media and error pages."""

import logging
from datetime import timedelta
{%- if cookiecutter.media_storage == "filesystem" %}
from pathlib import Path
{%- else %}
from pathlib import PurePosixPath
{%- endif %}

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connections
{%- if cookiecutter.media_storage == "filesystem" %}
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
{%- else %}
from django.http import FileResponse, Http404, HttpResponse, HttpResponseRedirect, JsonResponse
{%- endif %}
from django.shortcuts import render
from django.template import TemplateDoesNotExist
{%- if cookiecutter.frontend != "api_only" %}
from django.urls import NoReverseMatch, reverse
{%- endif %}
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe
{%- if cookiecutter.media_storage != "filesystem" %}

from apps.core.storage import private_media_storage
{%- endif %}

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


@require_safe
def security_txt(request):
    """``/.well-known/security.txt`` - RFC 9116.

    How someone reports a vulnerability in this site without having to guess.
    The alternative to publishing a contact is not silence; it is a disclosure
    that arrives by whatever route the finder improvises.

    ``Expires`` is mandatory in the RFC and is computed here rather than written
    into the template, because a hand-written date is a date that goes stale
    silently - and a parser may ignore an expired file completely, leaving the
    site looking as though it publishes nothing at all. A year ahead, recomputed
    on every request, so it is always valid and always honest.
    """
    context = {
        "SECURITY_CONTACT": settings.SECURITY_CONTACT_EMAIL,
        "EXPIRES": (timezone.now() + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "BASE_URL": settings.BASE_URL.rstrip("/"),
    }
    return render(request, "security.txt", context, content_type="text/plain")


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


def _private_download_headers(response):
    # Belt and braces with the site-wide setting: a private download must never be
    # interpreted as HTML by a browser that disagrees with our Content-Type.
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response
{%- if cookiecutter.media_storage == "filesystem" %}


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
    return _private_download_headers(response)
{%- else %}


@require_safe
def serve_private_file(request, relative_path):
    """Stream an object out of the private bucket after checking permission.

    The object is streamed through this view rather than redirected to, so the
    permission is re-checked on every request and no URL to the file exists that
    could be forwarded, logged by a proxy or pasted into a ticket. It costs a
    worker for the length of the download.

    The alternative, behind ``PRIVATE_MEDIA_SIGNED_URLS``, is to redirect to a
    short-lived signed URL: the bytes then go straight from the bucket, which is
    much cheaper for large files. The trade-off is that a signed URL, once
    issued, is valid for its whole lifetime to ANYONE holding it - it keeps
    working after the user logs out and after the permission is revoked. Prefer
    streaming; opt into signed URLs per project, for large files, with the expiry
    set as low as the download will tolerate.
    """
    user = request.user
    if not user.is_authenticated or not user.has_perm(PRIVATE_MEDIA_PERMISSION):
        raise PermissionDenied

    name = str(relative_path)
    # Object keys are produced by the upload_to callable, which generates them; a
    # traversal segment or a leading slash means the name did not come from us,
    # and some S3-compatible stores normalise "../" server-side.
    if name.startswith("/") or ".." in PurePosixPath(name).parts:
        raise Http404

    storage = private_media_storage()
    if not storage.exists(name):
        raise Http404

    if settings.PRIVATE_MEDIA_SIGNED_URLS:
        return _private_download_headers(HttpResponseRedirect(storage.url(name)))

    response = FileResponse(
        storage.open(name, "rb"), as_attachment=True, filename=PurePosixPath(name).name
    )
    return _private_download_headers(response)
{%- endif %}
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
{%- if cookiecutter.api != "none" %}
    if request.path.startswith("/api/"):
        # An API client that has to parse an HTML error page is a client that
        # breaks. Everything under /api/ answers in one error shape.
        from apps.api.exceptions import problem_json_response

        return problem_json_response(request, status)
{%- endif %}
    try:
        return render(request, template_name, status=status)
    except TemplateDoesNotExist:
        return HttpResponse(str(status), status=status, content_type="text/plain")


def bad_request(request, exception=None):
    return _error_response(request, "400.html", 400)


def permission_denied(request, exception=None):
    return _error_response(request, "403.html", 403)


def page_not_found(request, exception=None):
    return _error_response(request, "404.html", 404)


def server_error(request):
    return _error_response(request, "500.html", 500)
