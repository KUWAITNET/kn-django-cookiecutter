"""Reusable object-level permissions (api-standard.md A5, OWASP API1).

**The two halves rule.** Object-level authorisation has two independent
obligations and both are mandatory:

1. ``get_queryset()`` is filtered to the rows this requester may see. This is the
   only control that protects a *list* endpoint.
2. ``has_object_permission()`` is implemented, and every single-object code path
   goes through ``get_object()`` so DRF actually calls it.

Neither substitutes for the other. Writing one and assuming the other is the most
common serious API bug we can ship.

**The failure mode, both ways round.**

*Queryset unfiltered, permission present* - ``queryset = Note.objects.all()`` with
``IsObjectOwner``: ``GET /api/v1/notes/{uuid}/`` is safe, because ``get_object()``
calls ``check_object_permissions()`` and gets a 403. ``GET /api/v1/notes/``
**returns every row belonging to every customer**: DRF never calls
``has_object_permission()`` for a list - there is no single object to check - so
the permission class ran, ``has_permission()`` returned True because the user is
authenticated, and the paginated response walked the whole table. The endpoint
looks protected in code review and in a manual test of the detail URL, and is a
full data breach on the list URL.

*Queryset filtered, no object permission* - list and detail are both safe, because
``get_object()`` looks the row up inside the filtered queryset. But the first
custom ``@action`` that fetches by id directly
(``Note.objects.get(uuid=request.data["note"])``), the first bulk endpoint, and
the first ``PrimaryKeyRelatedField`` with an unfiltered ``queryset`` bypass
``get_queryset()`` entirely, and there is nothing left to stop them.

Every rule here needs a test asserting that a *different* user gets 403 or 404 on
both the list and the detail path. An untested authorisation rule is an
assumption.
"""

from rest_framework import permissions


class IsObjectOwner(permissions.BasePermission):
    """The requester must own the object.

    Half two of the rule above. Pair it with an owner-filtered ``get_queryset()``
    - DRF calls this only from ``get_object()``, never for a list response.

    The owner attribute defaults to ``owner`` and can be overridden per view with
    ``owner_field = "created_by"``. The comparison uses the ``_id`` attribute so
    it never triggers an extra query to load the related user.
    """

    owner_field = "owner"
    message = "You do not have permission to perform this action."

    def has_object_permission(self, request, view, obj):
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return False
        owner_field = getattr(view, "owner_field", self.owner_field)
        return getattr(obj, f"{owner_field}_id", None) == user.pk


class IsObjectOwnerOrStaff(IsObjectOwner):
    """Owner access, plus staff for support and moderation.

    Staff access is an audited, named exception rather than a second code path:
    if a project needs "an administrator can also see it", it is expressed here
    once, not re-derived in each view.
    """

    def has_object_permission(self, request, view, obj):
        user = getattr(request, "user", None)
        if user and user.is_authenticated and user.is_active and user.is_staff:
            return True
        return super().has_object_permission(request, view, obj)


class IsStaffUser(permissions.BasePermission):
    """Active staff only.

    Used for operational surfaces - integration diagnostics, internal reports -
    that must never be reachable by an unguessable URL alone. Unlike DRF's
    ``IsAdminUser`` this also requires ``is_active``, so deactivating an account
    closes the door immediately instead of at the next password rotation.
    """

    message = "You do not have permission to perform this action."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and user.is_active and user.is_staff)
