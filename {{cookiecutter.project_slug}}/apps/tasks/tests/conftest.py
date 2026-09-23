"""Fixtures for the background-task tests."""

from datetime import timedelta

import pytest


@pytest.fixture
def audit_entry(django_user_model, db):
    """Build an audit-log entry with an explicit age in days.

    Entries are created directly rather than by saving a tracked model: which models
    are tracked depends on the options this project was generated with, and the
    retention policy applies to all of them equally.
    """
    from auditlog.models import LogEntry
    from django.contrib.contenttypes.models import ContentType
    from django.utils import timezone

    subject = django_user_model.objects.create_user(username="audited", email="audited@example.com")
    content_type = ContentType.objects.get_for_model(subject)

    def _build(days_old: int):
        return LogEntry.objects.create(
            content_type=content_type,
            object_pk=str(subject.pk),
            object_id=subject.pk,
            object_repr=str(subject),
            action=LogEntry.Action.UPDATE,
            changes={"username": ["before", "after"]},
            timestamp=timezone.now() - timedelta(days=days_old),
        )

    return _build
