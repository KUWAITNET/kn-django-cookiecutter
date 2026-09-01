"""Serializers for the example resource (api-standard.md A6, A12).

Three rules this file exists to demonstrate:

- ``Meta.fields`` is always an **explicit list**. ``fields = "__all__"`` and
  ``exclude`` are forbidden: both are allowlists inverted into denylists, so
  adding a column to a model silently publishes it and the review that would
  have caught it is a migration review, not an API review.
- Server-owned values are read-only. **A client-supplied ``owner``, ``status``,
  ``price``, ``is_staff``, ``role``, ``balance``, ``site`` or ``tenant`` is never
  trusted**, on POST or on PATCH. They are assigned from the authenticated
  request or derived from business logic. A body of
  ``{"title": "x", "owner": 7, "status": "published"}`` must produce a draft note
  owned by the caller - that is OWASP API3, mass assignment, and ``__all__`` is
  how it happens ninety per cent of the time.
- Where the readable shape and the writable shape differ they are two
  serializers, chosen in ``get_serializer_class()``. One serializer contorted
  with per-action ``required=False``/``read_only`` is how a write-only field
  leaks into a read response.
"""

from __future__ import annotations

from datetime import UTC

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.api.models import Note


class UTCDateTimeField(serializers.DateTimeField):
    """Always serialise in UTC with a trailing ``Z``, whatever ``TIME_ZONE`` is.

    DRF renders datetimes in the active timezone, so a project whose
    ``TIME_ZONE`` is Asia/Kuwait would emit ``+03:00`` offsets - and the wire
    format would change the day somebody edits settings for an unrelated reason.
    The API's timestamps are a contract, not a display preference.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("default_timezone", UTC)
        kwargs.setdefault("format", "%Y-%m-%dT%H:%M:%SZ")
        super().__init__(*args, **kwargs)


class OwnerSummarySerializer(serializers.Serializer):
    """A *summary* of the related user - never the whole user record.

    An embedded user is a display name and nothing else: no e-mail, no
    ``is_staff``, no primary key, no "the front-end might need it". That is the
    outbound half of OWASP API3, excessive data exposure.
    """

    username = serializers.CharField(source="get_username", read_only=True)
    display_name = serializers.SerializerMethodField()

    def get_display_name(self, obj) -> str:
        return obj.get_full_name() or obj.get_username()


class NoteReadSerializer(serializers.ModelSerializer):
    """Everything a client may see. Never the internal pk, never audit columns."""

    owner = OwnerSummarySerializer(read_only=True)
    # The label is a separate field, so relabelling a status is not a breaking
    # change to the enum a client switches on.
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    created_at = UTCDateTimeField(read_only=True)
    updated_at = UTCDateTimeField(read_only=True)

    class Meta:
        model = Note
        fields = [
            "uuid",
            "owner",
            "title",
            "body",
            "status",
            "status_display",
            "is_pinned",
            "created_at",
            "updated_at",
        ]
        # Only the non-declared fields go here; DRF rejects a field that is both
        # declared above and listed as read-only.
        read_only_fields = ["uuid", "title", "body", "status", "is_pinned"]


class NoteWriteSerializer(serializers.ModelSerializer):
    """Exactly the fields a client may send.

    ``owner`` is a ``HiddenField``: it is never read from the request body, never
    appears in the schema as an input, and is present in ``validated_data`` for
    ``create()``. ``status`` is absent entirely - it moves through the publish
    action, not through a PATCH.
    """

    owner = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Note
        fields = ["owner", "title", "body", "is_pinned"]

    def validate_title(self, value):
        """Single-field rule. Validation lives here, never in the view."""
        title = value.strip()
        if len(title) < 3:
            raise serializers.ValidationError(_("Title must be at least 3 characters long."))
        return title

    def validate(self, attrs):
        """Cross-field rule.

        Reads through to ``self.instance`` so a PATCH that sets only one of the
        two fields is judged against the row as it will be, not against the
        fragment that happened to be sent.
        """
        is_pinned = attrs.get("is_pinned", getattr(self.instance, "is_pinned", False))
        body = attrs.get("body", getattr(self.instance, "body", ""))
        if is_pinned and not body:
            raise serializers.ValidationError({"body": _("A pinned note must have a body.")})
        return attrs


class ProblemDetailSerializer(serializers.Serializer):
    """RFC 9457 error envelope - documents the one error shape in the schema.

    See ``apps.api.exceptions``; this class only describes the contract, it does
    not produce it.
    """

    type = serializers.URLField(read_only=True)
    title = serializers.CharField(read_only=True)
    status = serializers.IntegerField(read_only=True)
    detail = serializers.CharField(read_only=True)
    instance = serializers.CharField(read_only=True)
    request_id = serializers.CharField(read_only=True)


class APIStatusSerializer(serializers.Serializer):
    """Response of the API status endpoint."""

    status = serializers.CharField(read_only=True)
    version = serializers.CharField(read_only=True)
    time = UTCDateTimeField(read_only=True)


class IntegrationDiagnosticSerializer(serializers.Serializer):
    """Response of the staff-only integration health check.

    ``error_class`` is the *class name* of our own exception, never the upstream
    exception's text: a raw SOAP or HTTP fault can echo back endpoint URLs,
    internal hostnames and credential-shaped configuration.
    """

    integration = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    duration_ms = serializers.IntegerField(read_only=True)
    error_class = serializers.CharField(read_only=True, allow_null=True)
    request_id = serializers.CharField(read_only=True)


class TokenPairResponseSerializer(serializers.Serializer):
    """Both token endpoints return this shape.

    Refresh returns a new refresh token too, because ``ROTATE_REFRESH_TOKENS`` is
    on: the presented token is blacklisted and replaced on every use.
    """

    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)
