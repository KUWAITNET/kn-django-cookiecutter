{%- if cookiecutter.task_queue == "huey" %}
"""Scheduled and background tasks.

The module name matters: 'manage.py run_huey' autodiscovers ``tasks`` in every
installed app and nothing else. A task defined anywhere else is invisible to the
consumer, which is the most common reason a task "never runs".

The schedule lives here, in code, reviewed with the code. There is no separate beat
process - the huey consumer runs the schedule itself.

``db_periodic_task`` rather than ``periodic_task``: it closes stale database
connections around the call, which a long-lived worker otherwise accumulates until
Postgres refuses new ones.
"""

from huey import crontab
from huey.contrib.djhuey import db_periodic_task

from apps.tasks import retention


# Sunday 03:30. Off-peak, and weekly rather than nightly because the table it prunes
# only grows by a year-old day's worth of rows per run.
@db_periodic_task(crontab(minute="30", hour="3", day_of_week="0"))
def prune_audit_log():
    """Apply the audit-log retention policy. See apps/tasks/retention.py."""
    return retention.prune_audit_log()
{%- if cookiecutter.notifications_app == "yes" %}


# Every ten minutes: mail is normally sent inline, so this only picks up what a
# failed or unreachable relay left behind. A shorter interval would poll an almost
# always empty table; a longer one delays a retry past the point anyone is waiting.
@db_periodic_task(crontab(minute="*/10"))
def send_queued_mail():
    """Retry anything left in the post-office queue. See apps/tasks/retention.py."""
    return retention.send_queued_mail()
{%- endif %}
{%- else %}
"""Scheduled and background tasks.

The module name matters: ``app.autodiscover_tasks()`` imports ``tasks`` from every
installed app and nothing else. A task defined anywhere else is invisible to the
worker, which is the most common reason a task "never runs".

Task names are set explicitly. The default is derived from the module path, so
moving this file would orphan every message already on the broker naming the old
path - an explicit name makes that a rename you choose rather than one you discover.

The schedule itself is in CELERY_BEAT_SCHEDULE (settings/base.py) - in the
repository, reviewed with the code, rather than in database rows that exist on one
server and appear in no diff. See docs/14-decisions.md.
"""

from celery import shared_task

from apps.tasks import retention


@shared_task(name="tasks.prune_audit_log", ignore_result=True)
def prune_audit_log():
    """Apply the audit-log retention policy. See apps/tasks/retention.py."""
    return retention.prune_audit_log()
{%- if cookiecutter.notifications_app == "yes" %}


@shared_task(name="tasks.send_queued_mail", ignore_result=True)
def send_queued_mail():
    """Retry anything left in the post-office queue. See apps/tasks/retention.py."""
    return retention.send_queued_mail()
{%- endif %}
{%- endif %}
