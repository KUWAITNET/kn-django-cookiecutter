"""Which fields hold private files, who may open them, and how a page links to one.

The media storage standard, section 5. A field is private when its storage is
``apps.core.storage.private_media_storage``; nothing else marks it, so there is
no hand-maintained list to forget. Templates link to a file through the
``file_link`` filter, which answers the permission gate for a private field and
the plain ``.url`` for a public one, so a template never needs to know which it
has.
"""

from django.apps import apps
from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.core.storage import private_media_storage


def is_private_field(field):
    """True when ``field`` stores its files on the private storage."""
    return getattr(field, "_storage_callable", None) is private_media_storage


def private_file_fields():
    """``(model, field)`` for every file field on the private storage, found by introspection."""
    return [
        (model, field)
        for model in apps.get_models()
        for field in model._meta.fields
        if isinstance(field, models.FileField) and is_private_field(field)
    ]


def gate_url(instance, field_name):
    """The permission gate for one file: ``/files/<app.model>/<pk>/<field>/``.

    The link on the page never expires; the check happens when it is clicked.
    """
    return reverse("private_file", args=[instance._meta.label_lower, instance.pk, field_name])


def file_link(fieldfile):
    """The ``href`` for an uploaded file, or "" when there is none.

    The gate for a private file, ``.url`` for a public one. With
    ``PRIVATE_FILE_LINKS_ENABLED`` off, a private file gets its signed ``.url``
    instead - the switch for a project rolling the gate out (section 8).
    """
    if not fieldfile:
        return ""
    field = fieldfile.field
    if is_private_field(field) and settings.PRIVATE_FILE_LINKS_ENABLED:
        return gate_url(fieldfile.instance, field.name)
    return fieldfile.url


def user_may_open(request, obj):
    """Whether ``request.user`` may open the private files on ``obj``.

    Decided by ``PRIVATE_FILE_PERMISSIONS``: a permission string, or a callable
    ``(request, obj) -> bool`` where a non-staff user may open their own file. A
    model with no entry is refused - the system check and the tests make sure
    every model with a private field has one, so refusing here only ever
    catches a mistake.
    """
    rule = settings.PRIVATE_FILE_PERMISSIONS.get(obj._meta.label_lower)
    if rule is None:
        return False
    if callable(rule):
        return bool(rule(request, obj))
    return request.user.has_perm(rule)
