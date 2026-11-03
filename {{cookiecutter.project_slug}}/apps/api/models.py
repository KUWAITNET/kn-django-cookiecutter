"""EXAMPLE resource for the API pack - replace it with the project's own models.

``Note`` exists so the generated project ships a working, tested reference
implementation of every rule in api-standard.md: an owner-filtered queryset, an
object-level permission, explicit serializers, an allowlisted filter and
ordering, a throttle scope and a UUID public identifier. Delete it once the real
resources exist, and delete its serializers, filters, views, routes and tests
with it.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Note(models.Model):
    """A trivial user-owned resource. EXAMPLE - replace."""

    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        PUBLISHED = "published", _("Published")
        ARCHIVED = "archived", _("Archived")

    # External clients address this row by its UUID, never by the primary key.
    # "/notes/1041/" tells a client there is a 1040 and a 1042, tells a
    # competitor how fast rows accrue, and turns any authorisation slip into a
    # bulk extraction rather than one leaked record. The pk stays internal and is
    # never serialised.
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notes",
        verbose_name=_("owner"),
    )
    title = models.CharField(_("title"), max_length=200)
    body = models.TextField(_("body"), blank=True)
    # Server-owned. Business logic moves it; a request body never does.
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    is_pinned = models.BooleanField(_("pinned"), default=False)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("note")
        verbose_name_plural = _("notes")
        # Deterministic ordering, ending in a unique tiebreaker: "-created_at"
        # alone repeats and drops rows across pages when two share a timestamp.
        ordering = ["-created_at", "-id"]
        indexes = [
            # Every filterable and orderable field is backed by an index; an
            # unindexed ordering column is a resource-consumption bug that only
            # shows up once the table is large, which is to say in production.
            models.Index(fields=["owner", "-created_at"], name="note_owner_created_idx"),
            models.Index(fields=["status"], name="note_status_idx"),
        ]
        constraints = [
            # A serializer protects the API; a constraint protects the data.
            models.CheckConstraint(
                condition=models.Q(title__gt=""),
                name="note_title_not_empty",
            ),
        ]

    def __str__(self):
        return self.title
