"""The queue wiring itself.

The retention logic is tested in test_retention.py. What is checked here is the part
that silently does nothing when it is wrong: that the task is registered under the
name the schedule refers to, and that invoking it actually runs the work.

Under the test settings tasks run inline, so this exercises the decorator and the
registry without needing {% if cookiecutter.task_queue == "huey" %}a consumer{% else %}a broker or a worker{% endif %}.
"""

import pytest
from auditlog.models import LogEntry
from django.core.management import call_command

from apps.tasks import tasks

pytestmark = pytest.mark.django_db


def test_prune_task_runs_the_retention_policy(audit_entry, settings):
    settings.AUDITLOG_RETENTION_DAYS = 400
    audit_entry(days_old=500)
    audit_entry(days_old=10)

    tasks.prune_audit_log()

    assert LogEntry.objects.count() == 1
{%- if cookiecutter.task_queue == "celery" %}


def test_task_is_registered_under_the_name_the_schedule_uses(settings):
    """A schedule entry naming a task nobody registered fails silently, every run."""
    from {{ cookiecutter.project_slug }}.celery import app

    scheduled_names = {entry["task"] for entry in settings.CELERY_BEAT_SCHEDULE.values()}

    assert scheduled_names <= set(app.tasks)
{%- else %}


def test_task_is_registered_with_the_consumer():
    """A task the consumer never registered is a schedule entry that never fires."""
    from huey.contrib.djhuey import HUEY

    registered = {task.name for task in HUEY._registry.periodic_tasks}

    assert "prune_audit_log" in registered
{%- endif %}


def test_management_command_prunes(audit_entry, settings):
    settings.AUDITLOG_RETENTION_DAYS = 400
    audit_entry(days_old=500)

    call_command("prune_audit_log")

    assert LogEntry.objects.count() == 0


def test_management_command_dry_run_deletes_nothing(audit_entry, settings):
    settings.AUDITLOG_RETENTION_DAYS = 400
    audit_entry(days_old=500)

    call_command("prune_audit_log", "--dry-run")

    assert LogEntry.objects.count() == 1


def test_management_command_refuses_a_period_below_the_baseline(audit_entry):
    from django.core.management.base import CommandError

    audit_entry(days_old=500)

    with pytest.raises(CommandError, match="12 months"):
        call_command("prune_audit_log", "--days", "30")

    assert LogEntry.objects.count() == 1
