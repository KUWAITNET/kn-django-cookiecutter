"""The audit-log retention policy.

The security baseline requires at least 12 months of audit history, pruned by a
scheduled job thereafter. Both halves are tested here: that old entries go, and that
a retention period below the floor is refused rather than honoured.
"""

import pytest
from auditlog.models import LogEntry

from apps.tasks import retention

pytestmark = pytest.mark.django_db


def test_deletes_entries_older_than_the_retention_period(audit_entry, settings):
    settings.AUDITLOG_RETENTION_DAYS = 400
    old = audit_entry(days_old=500)

    deleted = retention.prune_audit_log()

    assert deleted == 1
    assert not LogEntry.objects.filter(pk=old.pk).exists()


def test_keeps_entries_inside_the_retention_period(audit_entry, settings):
    settings.AUDITLOG_RETENTION_DAYS = 400
    recent = audit_entry(days_old=399)

    assert retention.prune_audit_log() == 0
    assert LogEntry.objects.filter(pk=recent.pk).exists()


def test_refuses_a_retention_period_below_the_baseline(audit_entry):
    audit_entry(days_old=200)

    with pytest.raises(ValueError, match="12 months"):
        retention.prune_audit_log(days=90)

    assert LogEntry.objects.count() == 1


def test_deletes_across_several_batches(audit_entry, settings):
    """A batch size smaller than the backlog must still empty it."""
    settings.AUDITLOG_RETENTION_DAYS = 400
    for _ in range(5):
        audit_entry(days_old=500)

    assert retention.prune_audit_log(batch_size=2) == 5
    assert LogEntry.objects.count() == 0


def test_running_twice_is_harmless(audit_entry, settings):
    settings.AUDITLOG_RETENTION_DAYS = 400
    audit_entry(days_old=500)

    assert retention.prune_audit_log() == 1
    assert retention.prune_audit_log() == 0


def test_dry_run_count_matches_what_a_prune_would_delete(audit_entry, settings):
    settings.AUDITLOG_RETENTION_DAYS = 400
    audit_entry(days_old=500)
    audit_entry(days_old=500)
    audit_entry(days_old=10)

    assert retention.count_prunable_audit_entries() == 2
    assert LogEntry.objects.count() == 3
{%- if cookiecutter.notifications_app == "yes" %}


def test_send_queued_mail_delivers_what_is_queued():
    """Mail is normally sent inline; this job is what retries a failed send."""
    from post_office import mail
    from post_office.models import STATUS, Email

    mail.send(
        recipients=["queued@example.com"],
        sender="sender@example.com",
        subject="Queued",
        message="Body",
        priority="medium",  # anything but "now" leaves it in the queue
    )
    assert Email.objects.filter(status=STATUS.queued).count() == 1

    sent, failed, requeued = retention.send_queued_mail()

    assert sent == 1
    assert failed == 0
    assert Email.objects.filter(status=STATUS.sent).count() == 1
{%- endif %}
