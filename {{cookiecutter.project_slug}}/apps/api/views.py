"""Versioned API views, served under ``/api/v1/`` (api-standard.md A1, A5-A8).

``NoteViewSet`` is the reference implementation every new resource is copied
from. Read it as a checklist:

- ``get_queryset()`` is filtered by owner - half one of object-level
  authorisation, and the only thing that protects the *list* endpoint;
- ``IsObjectOwner`` is in ``permission_classes`` - half two, which protects every
  path that fetches a single row;
- read and write serializers are separate and explicit;
- filtering, ordering and search all run against allowlists;
- writes carry the ``write`` throttle scope;
- ``lookup_field`` is the UUID, so nothing external references a sequential id;
- every operation is annotated for drf-spectacular, because a schema warning is
  an endpoint whose contract we cannot describe, which is a client that guesses.
"""

from __future__ import annotations

import logging
import time

from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from apps.api.exceptions import get_request_id
from apps.api.filters import NoteFilterSet, StrictOrderingFilter
from apps.api.models import Note
from apps.api.permissions import IsObjectOwner, IsStaffUser
from apps.api.serializers import (
    APIStatusSerializer,
    IntegrationDiagnosticSerializer,
    NoteReadSerializer,
    NoteWriteSerializer,
    ProblemDetailSerializer,
    TokenPairResponseSerializer,
)
from apps.api.services import ExampleIntegrationClient, UpstreamError
from apps.api.throttling import (
    AuthRateThrottle,
    PublicReadRateThrottle,
    ScopedThrottle,
    WriteRateThrottle,
)

logger = logging.getLogger("{{ cookiecutter.project_slug }}.api")


@extend_schema_view(
    list=extend_schema(
        summary="List the requesting user's notes",
        description="Paginated, filterable and orderable. Only the caller's own notes.",
    ),
    retrieve=extend_schema(summary="Retrieve one of the requesting user's notes"),
    create=extend_schema(
        summary="Create a note",
        responses={201: NoteReadSerializer, 400: ProblemDetailSerializer},
    ),
    update=extend_schema(
        summary="Replace a note",
        responses={200: NoteReadSerializer, 400: ProblemDetailSerializer},
    ),
    partial_update=extend_schema(
        summary="Update part of a note",
        responses={200: NoteReadSerializer, 400: ProblemDetailSerializer},
    ),
    destroy=extend_schema(summary="Delete a note"),
)
class NoteViewSet(viewsets.ModelViewSet):
    """EXAMPLE owned resource. Replace with the project's real resources."""

    permission_classes = [permissions.IsAuthenticated, IsObjectOwner]
    serializer_class = NoteReadSerializer

    # Deliberately empty. The real queryset is built per request in
    # get_queryset(); this only lets the schema generator, which introspects with
    # an anonymous mock request, find the model. Keeping it ".none()" rather than
    # ".all()" means that if get_queryset() were ever deleted the endpoint would
    # return nothing instead of every row in the table.
    queryset = Note.objects.none()

    # External references are UUIDs. The regex keeps the router from swallowing
    # sibling sub-paths and makes the OpenAPI path parameter exact.
    lookup_field = "uuid"
    lookup_value_regex = "[0-9a-fA-F-]{36}"

    filter_backends = [DjangoFilterBackend, StrictOrderingFilter, SearchFilter]
    filterset_class = NoteFilterSet
    # Allowlist. "__all__" would publish every column, including unindexed and
    # expensive ones, and would let a client order by a related password hash.
    ordering_fields = ["created_at", "updated_at", "title", "status"]
    ordering = ["-created_at", "-id"]  # deterministic: unique tiebreaker last
    search_fields = ["title", "body"]

    def get_queryset(self):
        """Half one of object-level authorisation.

        The list endpoint can only ever see this user's rows, and ``get_object()``
        looks a row up *inside* this queryset - which is why another user's note
        is a 404 here rather than a 403. That is deliberate: a 403 would confirm
        the row exists.
        """
        return Note.objects.filter(owner=self.request.user).select_related("owner")

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return NoteWriteSerializer
        return NoteReadSerializer

    def get_throttles(self):
        """Writes are metered on the ``write`` scope, reads on the global default."""
        if self.request.method not in permissions.SAFE_METHODS:
            return [WriteRateThrottle()]
        return super().get_throttles()

    def perform_create(self, serializer):
        # Ownership is assigned by the server, never accepted from the body.
        # HiddenField already supplies it; this is the second line of defence.
        serializer.save(owner=self.request.user)

    def create(self, request, *args, **kwargs):
        write_serializer = self.get_serializer(data=request.data)
        write_serializer.is_valid(raise_exception=True)
        self.perform_create(write_serializer)
        read_serializer = NoteReadSerializer(
            write_serializer.instance, context=self.get_serializer_context()
        )
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        write_serializer = self.get_serializer(instance, data=request.data, partial=partial)
        write_serializer.is_valid(raise_exception=True)
        self.perform_update(write_serializer)
        read_serializer = NoteReadSerializer(
            write_serializer.instance, context=self.get_serializer_context()
        )
        return Response(read_serializer.data)

    @extend_schema(
        summary="Publish a note",
        description="Server-owned status transition. The status is never writable from a body.",
        request=None,
        responses={200: NoteReadSerializer, 404: ProblemDetailSerializer},
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="publish",
        throttle_classes=[WriteRateThrottle],
    )
    def publish(self, request, uuid=None):
        """A documented non-CRUD action, expressed as a sub-path.

        Note that it resolves the object through ``self.get_object()``: the row
        stays inside the owner-filtered queryset *and* ``check_object_permissions``
        runs. A custom action that instead did ``Note.objects.get(uuid=...)``
        would bypass both halves of the rule, and that is the single most common
        way a correct-looking viewset ships a broken-object-level-authorisation
        bug.
        """
        note = self.get_object()
        note.status = Note.Status.PUBLISHED
        note.save(update_fields=["status", "updated_at"])
        serializer = NoteReadSerializer(note, context=self.get_serializer_context())
        return Response(serializer.data)


class APIStatusView(APIView):
    """Liveness of the API surface itself - deliberately unauthenticated.

    A client needs to distinguish "the API is down" from "my token expired"
    without holding a credential, so this is public. Being public makes it a free
    resource, so it carries a throttle scope; that pairing is not optional.

    It reports nothing an anonymous caller could not already infer, and it does
    not touch the database - the operational health endpoint that does is
    ``/healthz``.
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [PublicReadRateThrottle]

    @extend_schema(
        summary="API status",
        auth=[],
        responses={200: APIStatusSerializer},
    )
    def get(self, request):
        payload = {
            "status": "ok",
            "version": request.version or "v1",
            "time": timezone.now(),
        }
        return Response(APIStatusSerializer(payload).data)


class IntegrationDiagnosticView(APIView):
    """Staff-only integration health check (api-standard.md B7).

    This view replaces an anti-pattern a previous KUWAITNET project shipped: its
    live-market-data diagnostic sat at an unguessable URL prefix, described in a
    comment as "non-guessable", with no login check, no permission check and no
    rate limit - and it rendered ``str(exc)`` from the upstream SOAP failure
    straight into the page along with a full dump of the live data, to anyone who
    asked.

    Two defects, both worth naming because they recur:

    1. **Security through obscurity.** An unguessable path is not
       authentication. It leaks through Referer headers, browser history, proxy
       and CDN access logs and Sentry breadcrumbs; it cannot be revoked, audited
       or rotated without breaking the bookmark of whoever legitimately uses it.
       The gate here is a staff permission check.
    2. **Information disclosure.** A raw upstream exception can echo back
       endpoint URLs, fault details, internal hostnames and credential-shaped
       configuration. This view logs the exception with ``logger.exception`` and
       returns a classified summary - the error class, the duration and the
       request id. The detail goes where the people entitled to it already are.

    A health check that calls upstream is a proxy for calling upstream, so it
    carries its own throttle.
    """

    permission_classes = [IsStaffUser]
    throttle_classes = [ScopedThrottle]
    throttle_scope = "write"

    @extend_schema(
        summary="Integration health check (staff only)",
        description=(
            "Performs one cheap upstream call and reports whether it worked and how "
            "long it took. Never returns the upstream's own error text."
        ),
        responses={
            200: IntegrationDiagnosticSerializer,
            403: ProblemDetailSerializer,
            503: OpenApiResponse(
                response=IntegrationDiagnosticSerializer,
                description="The integration is unconfigured or the upstream is unavailable.",
            ),
        },
    )
    def get(self, request):
        started = time.monotonic()
        payload = {
            "integration": ExampleIntegrationClient.name,
            "status": "ok",
            "duration_ms": 0,
            "error_class": None,
            "request_id": get_request_id(request),
        }

        if not ExampleIntegrationClient.is_configured():
            payload["status"] = "not_configured"
            return Response(
                IntegrationDiagnosticSerializer(payload).data,
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            ExampleIntegrationClient().ping()
        except UpstreamError as exc:
            logger.exception("integration.health_check_failed")
            payload["status"] = "unavailable"
            payload["error_class"] = type(exc).__name__
            payload["duration_ms"] = int((time.monotonic() - started) * 1000)
            return Response(
                IntegrationDiagnosticSerializer(payload).data,
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        payload["duration_ms"] = int((time.monotonic() - started) * 1000)
        return Response(IntegrationDiagnosticSerializer(payload).data)


@extend_schema(
    summary="Obtain an access and refresh token pair",
    auth=[],
    responses={
        200: TokenPairResponseSerializer,
        401: ProblemDetailSerializer,
        429: ProblemDetailSerializer,
    },
)
class ThrottledTokenObtainPairView(TokenObtainPairView):
    """Token obtain, on the tightest scope in the API.

    A login endpoint answers "does this account exist, and is this its
    password?", so it is a credential oracle and is rate-limited per IP. It is
    also covered by django-axes where the project enables it: a lockout after N
    failures is a different control from a rate cap, and both belong on login.
    """

    throttle_classes = [AuthRateThrottle]


@extend_schema(
    summary="Exchange a refresh token for a new pair",
    auth=[],
    responses={200: TokenPairResponseSerializer, 401: ProblemDetailSerializer},
)
class RotatingTokenRefreshView(TokenRefreshView):
    """Refresh, with rotation and blacklist-on-use.

    Every refresh returns a *new* refresh token and blacklists the one presented,
    so a refresh token replayed a second time fails. That failure is also the
    detection signal for a stolen token and is worth alerting on.
    """


@extend_schema(
    summary="Check whether a token is still valid",
    auth=[],
    responses={
        200: OpenApiResponse(description="The token is valid."),
        401: ProblemDetailSerializer,
    },
)
class DocumentedTokenVerifyView(TokenVerifyView):
    """Verification only. It returns an empty body and never issues a token."""


@extend_schema(
    summary="Log out by blacklisting a refresh token",
    auth=[],
    responses={
        200: OpenApiResponse(description="The refresh token has been blacklisted."),
        401: ProblemDetailSerializer,
    },
)
class DocumentedTokenBlacklistView(TokenBlacklistView):
    """Logout.

    The client also discards its access token, but that token stays
    cryptographically valid until it expires. That is a property of JWT, not a
    bug, and it is the reason the access lifetime is 15 minutes - say so to
    clients plainly rather than claiming instant revocation.
    """
