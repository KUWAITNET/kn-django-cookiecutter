# 13. Scheduled tasks

Everything that runs without a person triggering it. Undocumented scheduled tasks are the classic
cause of a migrated site that works perfectly for a week and then quietly stops publishing.

{% if cookiecutter.task_queue == "none" -%}
**There is no background worker and no task queue in this project.** Everything below is a cron
entry or a systemd timer on the server. That is a deliberate choice recorded in
[14-decisions.md](14-decisions.md): a queue is one more process to keep alive, and this project does
not have work that justifies it.
{%- else -%}
This project has **two kinds** of scheduled work, and confusing them is how a job ends up running
twice or not at all.

1. **Tasks on the queue.** Defined in `apps/*/tasks.py`, run by the background
   {% if cookiecutter.task_queue == "huey" %}consumer{% else %}worker on a schedule fired by beat{% endif %}. They are code, reviewed with the code.
2. **Cron entries and systemd timers.** Everything the application does not own: backups,
   certificate renewal, off-server copies.

A job belongs on the queue when it is application logic, and in cron when it is machine
housekeeping. Putting a backup on the application's queue means a broken application takes the
backups with it.

**The {% if cookiecutter.task_queue == "huey" %}consumer{% else %}worker{% endif %} must be restarted by every deploy.** It is a second process running the same
code; a deploy that misses it leaves the old code running your tasks against a migrated database,
silently. See [07-deployment.md](07-deployment.md).
{%- endif %}

To see what management commands actually exist in the deployed version:

```bash
uv run python manage.py help
```
{%- if cookiecutter.task_queue != "none" %}

And what the {% if cookiecutter.task_queue == "huey" %}consumer{% else %}worker{% endif %} believes it can run — the authoritative list, because a task that is not
in it will never fire whatever this document says:

{% if cookiecutter.task_queue == "huey" -%}
```bash
# The consumer prints every registered task when it starts.
journalctl -u {{ cookiecutter.project_slug }}-worker --since '1 hour ago' | head -40
```
{%- elif cookiecutter.task_broker == "sqs" -%}
```bash
# 'celery inspect' does NOT work over SQS: there is no remote control channel.
# The worker's own startup log is the list.
journalctl -u {{ cookiecutter.project_slug }}-worker --since '1 hour ago' | head -40
```
{%- else -%}
```bash
uv run celery -A {{ cookiecutter.project_slug }} inspect registered
```
{%- endif %}
{%- endif %}

{% if cookiecutter.task_queue != "none" -%}
## On the queue

These are defined in `apps/tasks/tasks.py` and scheduled {% if cookiecutter.task_queue == "huey" %}by the decorator on each one{% else %}in `CELERY_BEAT_SCHEDULE`
(`settings/base.py`){% endif %}. They ship with the release, so a new server gets them by starting the
{% if cookiecutter.task_queue == "huey" %}consumer{% else %}worker and beat{% endif %} — there is nothing to copy across by hand.

| Task | What it does | Schedule | Failure impact |
|---|---|---|---|
| `prune_audit_log` | Deletes audit-log entries past `AUDITLOG_RETENTION_DAYS` | Sunday 03:30 | The audit table grows for the life of the site, and "we keep everything" is not a retention policy |
{%- if cookiecutter.notifications_app == "yes" %}
| `send_queued_mail` | Delivers anything the inline send could not | Every 10 minutes | Mail that failed once is never retried, and looks to the sender exactly like mail that was never sent |
{%- endif %}

The retention job refuses to run with a period below 365 days: the security baseline requires at
least 12 months of audit history, so a mistyped `AUDITLOG_RETENTION_DAYS` stops the job rather than
quietly destroying evidence.

Run either by hand, against the deployed code, before trusting the schedule:

```bash
uv run python manage.py prune_audit_log --dry-run   # counts, deletes nothing
uv run python manage.py prune_audit_log
```

{% endif -%}
## The schedule

TODO: complete every column. A blank "Where failures show up" means the failure shows up when a
client notices, which is the expensive way to find out.

| Task | What it does | Schedule | Runs as | Failure impact | Where failures show up |
|---|---|---|---|---|---|
{%- if cookiecutter.task_queue != "none" %}
| Audit log prune | On the queue (above), not in cron | Sunday 03:30 | `{{ cookiecutter.project_slug }}` | Retention policy is not applied | TODO: |
{%- endif %}
{%- if cookiecutter.stack == "wagtail" %}
| Scheduled publishing | Publishes and expires pages at their set times | Every 10 minutes | `{{ cookiecutter.project_slug }}` | Pages editors scheduled never appear, silently | TODO: |
| Revision trimming | Removes old page revisions beyond the retention period | Weekly | `{{ cookiecutter.project_slug }}` | The revision table grows without bound | TODO: |
| Search index refresh | Keeps site search current | TODO: | `{{ cookiecutter.project_slug }}` | Search results go stale | TODO: |
{%- endif %}
| E-mail log purge | Deletes sent-mail records past the 90-day retention | Weekly | `{{ cookiecutter.project_slug }}` | Personal data retained beyond policy; the table grows | TODO: |
{%- if cookiecutter.api != "none" %}
| Expired token flush | Removes expired and blacklisted refresh tokens | Daily | `{{ cookiecutter.project_slug }}` | The blacklist table grows with every token refresh | TODO: |
{%- endif %}
{%- if cookiecutter.rate_limiting == "yes" %}
| Access-attempt log purge | Trims old failed-login records | TODO: | `{{ cookiecutter.project_slug }}` | The table grows with attack traffic, not usage, so it grows unpredictably | TODO: |
{%- endif %}
| Database backup | Dumps the database to backup storage | Nightly 02:00 Kuwait | TODO: | The recovery point ages; data loss grows | TODO: |
| Media backup | Copies uploaded files to backup storage | Nightly | TODO: | Uploaded files unrecoverable | TODO: |
| Off-server backup push and prune | Copies backups off the machine and applies retention | Nightly, after the above | TODO: | A backup on the same server is not a backup | TODO: |
| Certificate renewal | Renews the TLS certificate | Twice daily; renews when near expiry | `root` | The site becomes untrusted at expiry | TODO: |
| TODO: project-specific task | | | | | |

## Where they are configured

TODO: record whether these are cron entries or systemd timers, and where the definitions live. Keep
them under configuration management or committed to this repository — a crontab that exists only on
one server is lost with that server.

{% if cookiecutter.deploy_target == "gunicorn_nginx" -%}
```bash
sudo -u {{ cookiecutter.project_slug }} crontab -l
systemctl list-timers --all
```
{%- else -%}
```bash
crontab -l
systemctl list-timers --all
docker compose ps
```
{%- endif %}

Every scheduled command runs with the production settings module and the same environment as the
application. A cron job that inherits an empty environment fails at boot with a missing
`SECRET_KEY`, and cron will not tell anybody.

{% if cookiecutter.deploy_target == "gunicorn_nginx" -%}
```cron
# Example shape. TODO: replace with the real entries and commit them.
PATH=/usr/local/bin:/usr/bin:/bin
DJANGO_SETTINGS_MODULE={{ cookiecutter.project_slug }}.settings.production

{% if cookiecutter.stack == "wagtail" %}*/10 * * * * cd /srv/{{ cookiecutter.project_slug }} && uv run python manage.py publish_scheduled >> /var/log/{{ cookiecutter.project_slug }}/cron.log 2>&1
{% endif %}0 3 * * 0 cd /srv/{{ cookiecutter.project_slug }} && uv run python manage.py cleanup_mail --days=90 >> /var/log/{{ cookiecutter.project_slug }}/cron.log 2>&1
```
{%- else -%}
```cron
# Example shape. TODO: replace with the real entries and commit them.
{% if cookiecutter.stack == "wagtail" %}*/10 * * * * cd /srv/{{ cookiecutter.project_slug }} && docker compose run --rm web python manage.py publish_scheduled >> /var/log/{{ cookiecutter.project_slug }}/cron.log 2>&1
{% endif %}0 3 * * 0 cd /srv/{{ cookiecutter.project_slug }} && docker compose run --rm web python manage.py cleanup_mail --days=90 >> /var/log/{{ cookiecutter.project_slug }}/cron.log 2>&1
```
{%- endif %}

Confirm each command name against `manage.py help` on the deployed version before committing the
crontab. A cron entry naming a command that does not exist fails every run, quietly.

Retention periods are passed as arguments rather than hard-coded, so the policy is visible in the
crontab and can be audited without reading the source.

## Running one by hand

Any of them can be run manually to test it, as the application user, from the project directory,
with the production settings module set. Do that once for each entry after the first deploy: a cron
job that has never been observed to succeed is an assumption.

{% if cookiecutter.stack == "wagtail" -%}
```bash
sudo -u {{ cookiecutter.project_slug }} env DJANGO_SETTINGS_MODULE={{ cookiecutter.project_slug }}.settings.production \
     uv run python manage.py publish_scheduled
```
{%- else -%}
```bash
sudo -u {{ cookiecutter.project_slug }} env DJANGO_SETTINGS_MODULE={{ cookiecutter.project_slug }}.settings.production \
     uv run python manage.py <command>
```
{%- endif %}

## How a failure raises an alert

This is the part that is normally missing, and it is why a stopped job goes unnoticed for months.

Each job must do one of:

- Write a completion line to a log that is monitored, and have an alert configured for "no
  completion line within the interval plus 50 %"
  ([09-monitoring.md](09-monitoring.md)).
- Or check in with an external dead-man's-switch service on success, so silence is the alert.

TODO: choose one and configure it for every row in the table. Cron mails failures to the local
user's mailbox by default, which on a modern server means nowhere.
{%- if cookiecutter.task_queue != "none" %}

For the queued tasks there is a second thing to alert on, and it is the one that actually happens:
**the {% if cookiecutter.task_queue == "huey" %}consumer{% else %}worker or beat{% endif %} not running at all**. A stopped {% if cookiecutter.task_queue == "huey" %}consumer{% else %}worker{% endif %} produces no errors,
no failed runs and no log lines — it produces silence, which is indistinguishable from a quiet
week. Monitor the process itself, not only its output; see [09-monitoring.md](09-monitoring.md).
{%- endif %}

## Mail delivery is still not queued

Worth stating explicitly, because it is the first thing an experienced Django administrator will
look for.

Outgoing mail is sent **synchronously** at the moment the application decides to send it
(`POST_OFFICE["DEFAULT_PRIORITY"]` is `"now"`){% if cookiecutter.task_queue != "none" %}, even though this project has a queue{% endif %}. Every send is
recorded in the e-mail log with its outcome, so a failed delivery is visible in the administration
interface rather than lost.

The trade-off is that a slow or unreachable mail relay slows the request that triggered the send.
That is the accepted cost; see [14-decisions.md](14-decisions.md). If this project later sends bulk
mail, that decision has to be revisited rather than worked around.
{%- if cookiecutter.task_queue != "none" and cookiecutter.notifications_app == "yes" %}

What the `send_queued_mail` task above does is narrower, and worth being precise about: it delivers
what the inline attempt **could not**. A relay that was down leaves a message in the queue with
nothing to retry it, which looks to everybody involved exactly like a message that was never sent.
{%- endif %}

{% if cookiecutter.countries_app == "cities" -%}
## One-off imports

Country and city reference data is imported once, and re-run only when the source data changes. It
is not scheduled.

```bash
uv run python manage.py cities_light
```
{%- endif %}

## After moving to a new server

Copy this table across before anything else, and verify each entry has actually run once on the new
machine. A migrated site that works perfectly for a week and then stops publishing is always this.
