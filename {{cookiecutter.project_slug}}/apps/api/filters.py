"""Filtering and ordering for the example resource (api-standard.md A7).

Both are allowlists. ``filterset_fields = "__all__"`` and
``ordering_fields = "__all__"`` are forbidden for the same reason
``fields = "__all__"`` is: they publish every column, including ones that are
unindexed, expensive, or that leak information through response-time differences.
"""

from __future__ import annotations

import django_filters
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.filters import OrderingFilter

from apps.api.models import Note


class StrictOrderingFilter(OrderingFilter):
    """``?ordering=`` restricted to ``ordering_fields``, and *rejected* otherwise.

    Raw user input never reaches ``order_by()``. Hand-rolled ordering that
    interpolates a query parameter is a rule violation even though Django
    parameterises it: an attacker can order by a related field's password-hash
    column and read it out one bit at a time from the row order.

    DRF's ``OrderingFilter`` already enforces the allowlist, but it does so by
    silently dropping the unknown term and falling back to the default ordering.
    That is safe and invisible: the client gets a 200 and never learns its
    request was ignored, so a typo in a sort key looks like a server bug. Here it
    is a 400 in the standard problem+json envelope, naming the rejected terms.
    """

    def remove_invalid_fields(self, queryset, fields, view, request):
        valid_fields = super().remove_invalid_fields(queryset, fields, view, request)
        rejected = [term for term in fields if term not in valid_fields]
        if rejected:
            raise serializers.ValidationError(
                {
                    self.ordering_param: _("Ordering by %(fields)s is not supported.")
                    % {"fields": ", ".join(sorted(rejected))}
                }
            )
        return valid_fields


class NoteFilterSet(django_filters.FilterSet):
    """Explicit filters for the example resource.

    Parameters are named for the API field rather than the ORM path, and a range
    filter is always ``<field>_after`` / ``<field>_before`` so every resource in
    every project reads the same way.
    """

    status = django_filters.ChoiceFilter(choices=Note.Status.choices)
    is_pinned = django_filters.BooleanFilter()
    created_after = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = Note
        fields = ["status", "is_pinned", "created_after", "created_before"]
