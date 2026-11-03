"""What the scheduled jobs actually do.

Deliberately separate from ``tasks.py``: nothing here imports {% if cookiecutter.task_queue == "huey" %}huey{% else %}Celery{% endif %}, so the work
can be run from a management command, a test or a shell with no worker running, and
the task wrapper stays a one-line adapter. It also means a queue change later is a
change to one small module rather than to the logic.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

#: The KUWAITNET security baseline requires at least 12 months of audit history.
#: Pruning below it is refused rather than warned about: a retention job that
#: quietly deletes evidence is worse than no retention job.
MINIMUM_RETENTION_DAYS = 365

#: Rows deleted per statement. A single unbounded DELETE over a table that has been
#: accumulating for two years takes a long lock; this keeps each statement short.
DELETE_BATCH_SIZE = 1000


def prune_audit_log(days: int | None = None, batch_size: int = DELETE_BATCH_SIZE) -> int:
    """Delete audit-log entries older than the retention period.

    Returns the number of entries deleted. Safe to run twice, and safe to interrupt:
    each batch is its own statement, so a killed worker leaves a partly pruned table
    rather than a half-open transaction, and the next run continues from there.
    """
    from auditlog.models import LogEntry

    if days is None:
        days = settings.AUDITLOG_RETENTION_DAYS
    if days < MINIMUM_RETENTION_DAYS:
        raise ValueError(
            f"Refusing to prune audit entries younger than {MINIMUM_RETENTION_DAYS} days "
            f"(asked for {days}). The security baseline requires at least 12 months of "
            "audit history; raise AUDITLOG_RETENTION_DAYS or record an exception."
        )

    cutoff = timezone.now() - timedelta(days=days)
    total = 0
    while True:
        batch = list(
            LogEntry.objects.filter(timestamp__lt=cutoff).values_list("pk", flat=True)[:batch_size]
        )
        if not batch:
            break
        _, per_model = LogEntry.objects.filter(pk__in=batch).delete()
        total += per_model.get("auditlog.LogEntry", 0)

    logger.info("Pruned %s audit log entries older than %s days (before %s).", total, days, cutoff)
    return total


def count_prunable_audit_entries(days: int | None = None) -> int:
    """How many entries a prune would remove. Used by --dry-run."""
    from auditlog.models import LogEntry

    if days is None:
        days = settings.AUDITLOG_RETENTION_DAYS
    cutoff = timezone.now() - timedelta(days=days)
    return LogEntry.objects.filter(timestamp__lt=cutoff).count()
{%- if cookiecutter.notifications_app == "yes" %}


def send_queued_mail() -> tuple[int, int, int]:
    """Deliver anything still sitting in the post-office queue.

    Mail is normally sent inline, at the moment the application decides to send it
    (POST_OFFICE["DEFAULT_PRIORITY"] is "now"). What lands in the queue is what that
    attempt could not deliver - a relay that was down or refusing. Without this job
    those messages sit in the table with nothing to retry them, which looks exactly
    like mail that was never sent.

    Returns post-office's (sent, failed, requeued) counts.
    """
    from post_office.mail import send_queued

    sent, failed, requeued = send_queued()
    if failed or requeued:
        logger.warning("Queued mail run: %s sent, %s failed, %s requeued.", sent, failed, requeued)
    else:
        logger.info("Queued mail run: %s sent.", sent)
    return sent, failed, requeued
{%- endif %}
