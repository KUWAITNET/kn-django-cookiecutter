"""Deployment system checks for the background queue.

Every one of these describes a way the queue can be configured so that it looks
healthy and does nothing. That failure mode is silent by nature - no error, no
exception, just work that never happens - so it is worth a check rather than a
line in a runbook.

Warnings, not errors: they must be loud enough to be seen in CI without stopping an
emergency deploy.
"""

import os

from django.conf import settings
from django.core.checks import Tags, Warning, register


def _is_production_settings() -> bool:
    """True when the process is running the production settings module."""
    module = os.environ.get("DJANGO_SETTINGS_MODULE", "")
    return module.rsplit(".", 1)[-1] == "production"
{%- if cookiecutter.task_queue == "huey" %}


@register(Tags.compatibility)
def check_queue_is_not_immediate(app_configs, **kwargs):
    """Immediate mode runs tasks inline and never starts the schedule."""
    if not _is_production_settings() or not settings.HUEY.get("immediate"):
        return []
    return [
        Warning(
            "The task queue is in immediate mode under the production settings.",
            hint=(
                "Every task runs inline in the web request that triggered it, the "
                "consumer has nothing to consume, and the periodic schedule never "
                "runs at all - so the audit log is never pruned. Unset HUEY_IMMEDIATE."
            ),
            id="tasks.W001",
        )
    ]
{%- if cookiecutter.huey_backend == "sqlite" %}


@register(Tags.database)
def check_queue_storage_is_not_sqlite(app_configs, **kwargs):
    """SQLite storage does not survive more than one worker process."""
    if not _is_production_settings():
        return []
    return [
        Warning(
            "The task queue is stored in SQLite.",
            hint=(
                "It is single-process storage: a second worker, or a worker on a "
                "second machine, sees a different queue. Switch the project to the "
                "PostgreSQL storage before go-live - it needs no new service."
            ),
            id="tasks.W002",
        )
    ]
{%- endif %}
{%- else %}


@register(Tags.compatibility)
def check_tasks_are_not_eager(app_configs, **kwargs):
    """Eager mode runs tasks inline and never sends anything to the broker."""
    if not _is_production_settings() or not settings.CELERY_TASK_ALWAYS_EAGER:
        return []
    return [
        Warning(
            "Celery is in always-eager mode under the production settings.",
            hint=(
                "Every task runs inline in the web request that triggered it and "
                "nothing reaches the broker, so the worker sits idle and beat's "
                "schedule has no effect. Unset CELERY_TASK_ALWAYS_EAGER."
            ),
            id="tasks.W001",
        )
    ]
{%- if cookiecutter.task_broker == "sqs" %}


@register(Tags.compatibility)
def check_sqs_visibility_timeout(app_configs, **kwargs):
    """A visibility timeout shorter than the task time limit means double runs."""
    options = getattr(settings, "CELERY_BROKER_TRANSPORT_OPTIONS", {})
    visibility_timeout = options.get("visibility_timeout")
    if visibility_timeout is None or visibility_timeout > settings.CELERY_TASK_TIME_LIMIT:
        return []
    return [
        Warning(
            f"The SQS visibility timeout ({visibility_timeout}s) is not longer than "
            f"the task time limit ({settings.CELERY_TASK_TIME_LIMIT}s).",
            hint=(
                "SQS makes a message visible again once the timeout expires, whether "
                "or not the task is still running, so any task that takes longer is "
                "handed to a second worker and runs twice. Raise "
                "AWS_SQS_VISIBILITY_TIMEOUT above CELERY_TASK_TIME_LIMIT."
            ),
            id="tasks.W003",
        )
    ]
{%- endif %}
{%- endif %}
