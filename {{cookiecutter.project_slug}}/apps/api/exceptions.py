"""RFC 9457 ``application/problem+json`` error rendering for the whole API.

DRF ships three different error bodies depending on which exception was raised:
``{"detail": "..."}`` for most of them, ``{"field": ["message"]}`` for validation,
and a bare list for a non-field validation error. A client then needs three
parsers, and in practice one of them is always missing. This module collapses all
of them into a single envelope, per api-standard.md A9.

Every error response carries ``type``, ``title``, ``status``, ``detail``,
``instance`` and ``request_id``. Validation failures add ``errors``; a throttled
request adds ``retry_after``.

Wired up in settings as ``REST_FRAMEWORK["EXCEPTION_HANDLER"]``. The
``problem_json_response`` helper is exported so that Django-level error handlers
(``handler400``/``handler403``/``handler404``/``handler500``) can return the same
envelope for requests under ``/api/`` that never reach a DRF view.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from django.conf import settings
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.signals import got_request_exception
from django.http import Http404, JsonResponse
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger("{{ cookiecutter.project_slug }}.api")

PROBLEM_CONTENT_TYPE = "application/problem+json"

# Slugs are appended to the project's problem base URL, so every ``type`` is a
# dereferenceable URI that resolves to a page in the API documentation.
PROBLEM_TYPES = {
    400: "validation-error",
    401: "unauthenticated",
    403: "permission-denied",
    404: "not-found",
    405: "method-not-allowed",
    406: "not-acceptable",
    409: "conflict",
    410: "endpoint-sunset",
    415: "unsupported-media-type",
    429: "rate-limited",
    500: "internal-server-error",
    502: "upstream-unavailable",
    503: "service-unavailable",
}

PROBLEM_TITLES = {
    400: "Validation failed",
    401: "Authentication required",
    403: "Permission denied",
    404: "Resource not found",
    405: "Method not allowed",
    406: "Not acceptable",
    409: "Conflict",
    410: "Endpoint removed",
    415: "Unsupported media type",
    429: "Too many requests",
    500: "Internal server error",
    502: "Upstream service unavailable",
    503: "Service unavailable",
}

GENERIC_5XX_DETAIL = (
    "The request could not be completed. Quote the request_id when contacting support."
)
VALIDATION_DETAIL = "The request body failed validation. See the errors member."


def problem_type_uri(status_code: int) -> str:
    """Stable URI identifying the problem class, under the project's own domain."""
    base = getattr(settings, "API_PROBLEM_BASE_URL", "") or (
        f"{settings.BASE_URL.rstrip('/')}/api/problems"
    )
    return f"{base.rstrip('/')}/{PROBLEM_TYPES.get(status_code, 'error')}"


def get_request_id(request) -> str:
    """Correlation id for this request, generated once and reused.

    A request-id middleware normally supplies ``request.request_id``; when the
    project has none, one is minted here so the member is never absent from the
    envelope and the log line and the response agree on it.
    """
    if request is None:
        return ""
    request_id = getattr(request, "request_id", "") or ""
    if not request_id:
        request_id = uuid.uuid4().hex
        try:
            request.request_id = request_id
        except AttributeError:  # pragma: no cover - only for exotic request objects
            return request_id
    return request_id


def _iter_field_errors(detail, path: str = ""):
    """Flatten a DRF ``ValidationError`` detail into a flat list of field errors.

    ``detail`` is an arbitrarily nested mix of dicts, lists and ``ErrorDetail``
    strings. Nested paths are dotted, list items carry an index, and errors that
    belong to no single field have ``field: null``.
    """
    if isinstance(detail, dict):
        for key, value in detail.items():
            if key in {"non_field_errors", "__all__"}:
                yield from _iter_field_errors(value, path)
            else:
                yield from _iter_field_errors(value, f"{path}.{key}" if path else str(key))
    elif isinstance(detail, (list, tuple)):
        for index, value in enumerate(detail):
            if isinstance(value, (dict, list, tuple)):
                child = f"{path}[{index}]" if path else f"[{index}]"
                yield from _iter_field_errors(value, child)
            else:
                yield from _iter_field_errors(value, path)
    else:
        yield {
            "field": path or None,
            "code": str(getattr(detail, "code", "invalid")),
            "detail": str(detail),
        }


def _safe_detail(exc, status_code: int) -> str:
    """The human-readable explanation of *this* occurrence, safe to show a user.

    A 5xx never describes itself: the exception text can carry SQL, internal
    hostnames and an upstream vendor's own error strings. Anything else uses
    DRF's message, which is already written for an end user - but a dict detail
    (django-rest-framework-simplejwt raises those) is reduced to its ``detail``
    key so the library's internal ``messages`` list is not published.
    """
    if status_code >= 500:
        return GENERIC_5XX_DETAIL
    if isinstance(exc, exceptions.ValidationError):
        return VALIDATION_DETAIL

    fallback = PROBLEM_TITLES.get(status_code, "Error")
    detail = getattr(exc, "detail", None)
    if detail is None:
        return fallback
    if isinstance(detail, dict):
        primary = detail.get("detail")
        return str(primary) if primary is not None else fallback
    if isinstance(detail, (list, tuple)):
        return str(detail[0]) if detail else fallback
    return str(detail)


def _problem(status_code: int, detail: str, request) -> dict[str, Any]:
    return {
        "type": problem_type_uri(status_code),
        "title": PROBLEM_TITLES.get(status_code, "Error"),
        "status": status_code,
        "detail": detail,
        "instance": getattr(request, "path", "") or "",
        "request_id": get_request_id(request),
    }


def problem_json_response(request, status_code: int, detail: str | None = None) -> JsonResponse:
    """A problem+json ``JsonResponse`` for code that is not inside a DRF view.

    Django's ``handler400``/``handler403``/``handler404``/``handler500`` run
    outside DRF, so a bad path under ``/api/`` would otherwise answer with the
    site's HTML error page - a different content type on exactly the responses a
    client is least able to parse.
    """
    if detail is None:
        detail = GENERIC_5XX_DETAIL if status_code >= 500 else PROBLEM_TITLES.get(status_code, "")
    return JsonResponse(
        _problem(status_code, detail, request),
        status=status_code,
        content_type=PROBLEM_CONTENT_TYPE,
    )


def _unhandled_exception_response(exc, request) -> Response:
    """Anything DRF could not classify: a bug, not a client error.

    Returning a response here means Django's ``handler500`` never runs, so the
    exception is re-emitted on ``got_request_exception`` to keep Sentry and
    Django's own error reporting intact. The body is fixed and says nothing
    whatsoever about the exception; the traceback goes to the log.
    """
    logger.exception(
        "api.unhandled_exception",
        extra={"api_path": getattr(request, "path", ""), "api_exception": type(exc).__name__},
    )
    got_request_exception.send(sender=None, request=request)
    return Response(
        _problem(500, GENERIC_5XX_DETAIL, request),
        status=500,
        content_type=PROBLEM_CONTENT_TYPE,
    )


def problem_detail_handler(exc, context):
    """DRF ``EXCEPTION_HANDLER``: one error shape for the whole API.

    Handles validation (400), authentication (401), permission (403), not-found
    (404), method-not-allowed (405), throttling (429 with ``Retry-After``) and
    anything unclassified (500, with no internal detail). A DRF default error
    body never reaches a client.
    """
    request = context.get("request") if context else None

    # Django's own exceptions arrive here on their way through a DRF view;
    # normalising them first means one code path produces every envelope.
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    response = drf_exception_handler(exc, context)
    if response is None:
        return _unhandled_exception_response(exc, request)

    status_code = response.status_code
    problem = _problem(status_code, _safe_detail(exc, status_code), request)
    headers: dict[str, str] = {}

    if isinstance(exc, exceptions.ValidationError):
        problem["errors"] = list(_iter_field_errors(exc.detail))

    if isinstance(exc, exceptions.Throttled) and exc.wait is not None:
        wait = int(exc.wait) + 1  # round up: a client that retries at exactly wait is early
        problem["retry_after"] = wait
        headers["Retry-After"] = str(wait)

    # DRF sets this on NotAuthenticated when an authenticator can name a scheme.
    # Without it the client cannot tell "log in" from "you may not do this".
    auth_header = getattr(exc, "auth_header", None)
    if auth_header:
        headers["WWW-Authenticate"] = auth_header

    if status_code >= 500:
        logger.error(
            "api.error",
            extra={"api_status": status_code, "api_path": problem["instance"]},
        )

    return Response(
        problem,
        status=status_code,
        headers=headers,
        content_type=PROBLEM_CONTENT_TYPE,
    )
