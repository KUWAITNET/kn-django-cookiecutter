"""RFC 9457 ``application/problem+json`` error rendering for the whole API.

DRF ships three different error bodies depending on which exception was raised:
``{"detail": "..."}`` for most of them, ``{"field": ["message"]}`` for validation,
and a bare list for a non-field validation error. A client then needs three
parsers, and in practice one of them is always missing. The API answers with a
single envelope instead, per api-standard.md A9.

Collapsing them is ``drf-standardized-errors``' job, not ours: it is the
KUWAITNET house standard, it already covers every DRF exception path (including
the unhandled ones, which it re-signals so Sentry still sees them), and its
drf-spectacular integration documents an error response on every operation. What
stays ours is the *wire format*: the package's own shape is
``{"type": "validation_error", "errors": [{"code", "detail", "attr"}]}``, so this
module plugs an ``ExceptionFormatter`` into it that emits RFC 9457 instead.

Every error response carries ``type``, ``title``, ``status``, ``detail``,
``instance`` and ``request_id``. Validation failures add ``errors``; a throttled
request adds ``retry_after`` and the matching ``Retry-After`` header.

Wired up in settings as ``REST_FRAMEWORK["EXCEPTION_HANDLER"]`` pointing at the
package's own handler function - the schema generator checks for exactly that
function to decide whether it may document the error responses - with this
module's handler and formatter classes named in ``DRF_STANDARDIZED_ERRORS``.
The ``problem_json_response`` helper is exported so that Django-level error
handlers (``handler400``/``handler403``/``handler404``/``handler500``) can return
the same envelope for requests under ``/api/`` that never reach a DRF view.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import JsonResponse
from drf_standardized_errors.formatter import ExceptionFormatter
from drf_standardized_errors.handler import ExceptionHandler
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.serializers import as_serializer_error
from rest_framework.status import is_server_error

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

    The package ships its own flattener, but it names the member ``attr``, uses a
    different notation for list indices and has no null for a non-field error -
    so using it would change a contract clients are already parsing.
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


def _retry_after(exc) -> int | None:
    """Seconds a throttled client must wait, rounded up.

    The package truncates; a client that retries at exactly the truncated second
    is still early, and is throttled a second time for it.
    """
    wait = getattr(exc, "wait", None)
    return None if wait is None else int(wait) + 1


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


class ProblemDetailExceptionFormatter(ExceptionFormatter):
    """Renders the package's classified exception as an RFC 9457 problem document.

    ``format_error_response`` is the package's documented extension point. The
    ``error_response`` it is handed is the package's own dataclass, in the
    package's own shape; we ignore it and read ``self.exc``, which is the
    exception after the handler has converted Django's exceptions and collapsed
    anything unclassified into a 500.
    """

    def format_error_response(self, error_response) -> dict[str, Any]:  # noqa: ARG002
        exc = self.exc
        status_code = exc.status_code
        request = self.context.get("request")

        problem = _problem(status_code, _safe_detail(exc, status_code), request)

        if isinstance(exc, exceptions.ValidationError):
            problem["errors"] = list(_iter_field_errors(exc.detail))

        retry_after = _retry_after(exc)
        if retry_after is not None:
            problem["retry_after"] = retry_after

        return problem


class ProblemDetailExceptionHandler(ExceptionHandler):
    """The package's handler, taught the four things this envelope needs.

    Everything else - converting ``Http404`` and Django's ``PermissionDenied``,
    the 500 fallback for anything unclassified, ``set_rollback``, and re-sending
    ``got_request_exception`` so Sentry and ``django.request`` still see the
    error - is inherited.
    """

    def convert_known_exceptions(self, exc: Exception) -> Exception:
        """Django's ``ValidationError`` becomes DRF's rather than becoming a 500.

        A model's ``clean()`` or a plain Django validator raises Django's class,
        which DRF does not recognise, so a serializer that calls ``full_clean()``
        would answer 500 to what is a client mistake.
        """
        if isinstance(exc, DjangoValidationError):
            return exceptions.ValidationError(detail=as_serializer_error(exc))
        return super().convert_known_exceptions(exc)

    def get_headers(self, exc: exceptions.APIException) -> dict:
        headers = super().get_headers(exc)
        retry_after = _retry_after(exc)
        if retry_after is not None:
            headers["Retry-After"] = str(retry_after)
        return headers

    def get_response(self, exc: exceptions.APIException, data: dict) -> Response:
        return Response(
            data,
            status=exc.status_code,
            headers=self.get_headers(exc),
            content_type=PROBLEM_CONTENT_TYPE,
        )

    def report_exception(self, exc: exceptions.APIException, response: Response) -> None:
        if is_server_error(exc.status_code):
            # The body deliberately says nothing about the failure, so the log
            # line carrying the same request_id is the whole diagnostic channel.
            logger.error(
                "api.error",
                extra={
                    "api_status": exc.status_code,
                    "api_path": response.data.get("instance", ""),
                    "api_request_id": response.data.get("request_id", ""),
                },
            )
        super().report_exception(exc, response)
