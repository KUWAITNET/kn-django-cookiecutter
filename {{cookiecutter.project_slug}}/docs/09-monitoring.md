# 9. Monitoring and troubleshooting

## Where to look

| Signal | Where to look | Who is alerted |
|---|---|---|
| Site down | TODO: uptime provider | TODO: |
{%- if cookiecutter.sentry == "yes" %}
| Application errors | Sentry, project TODO: | TODO: |
{%- else %}
| Application errors | Application log (below). **No error monitor is configured** — see the note at the end of this page | Nobody, until someone looks |
{%- endif %}
| Application log | TODO: `journalctl -u {{ cookiecutter.project_slug }}-gunicorn`{% if cookiecutter.deploy_target == "docker_compose" %} / `docker compose logs web`{% endif %} | — |
{%- if cookiecutter.task_queue != "none" %}
| Background {% if cookiecutter.task_queue == "huey" %}consumer{% else %}worker{% endif %} | TODO: `journalctl -u {{ cookiecutter.project_slug }}-worker`{% if cookiecutter.deploy_target == "docker_compose" %} / `docker compose logs worker`{% endif %}. Its own log, **not** the web process's — a task that fails appears here and nowhere else | TODO: |
{%- if cookiecutter.task_queue == "celery" %}
| Schedule (beat) | TODO: `journalctl -u {{ cookiecutter.project_slug }}-beat`{% if cookiecutter.deploy_target == "docker_compose" %} / `docker compose logs beat`{% endif %} | TODO: |
{%- endif %}
| Queue depth | {% if cookiecutter.task_queue == "huey" %}TODO: `manage.py shell` → `from huey.contrib.djhuey import HUEY; HUEY.pending_count()`{% elif cookiecutter.task_broker == "sqs" %}CloudWatch: `ApproximateNumberOfMessagesVisible` and `ApproximateAgeOfOldestMessage` on the queue{% elif cookiecutter.task_broker == "rabbitmq" %}RabbitMQ management UI, or `rabbitmqctl list_queues`{% else %}`celery -A {{ cookiecutter.project_slug }} inspect stats`, or `redis-cli llen {{ cookiecutter.project_slug }}`{% endif %} | TODO: |
{%- endif %}
| Web server access and error log | TODO: e.g. `/var/log/nginx/{{ cookiecutter.domain_name }}.*.log` | — |
| Database log | TODO: | — |
| Outgoing mail | The e-mail log in the administration interface, plus the relay's own dashboard | — |
| Backup success or failure | TODO: | TODO: |
| Certificate expiry | TODO: | TODO: |
| Disk, memory, CPU | TODO: | TODO: |

TODO: every one of those must name a person or a monitored channel. An unattended mailbox is not a
recipient.

## The health endpoint

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://{{ cookiecutter.domain_name }}/healthz
```

`/healthz` executes a query, so it fails when the site is up but the database is not — which is the
failure the homepage would hide behind a cached page. It returns a status and nothing else: no
version, no hostname, no dependency detail. It is registered outside the localised URL patterns, so
it has no language prefix and never redirects.

Monitor **this URL**, not the homepage:

- From outside the application's own infrastructure.
- Every 60 seconds.
- From at least two locations, one in or near the Gulf region.
- Alert after two consecutive failures from at least two locations — fast enough to alert within
  about three minutes, slow enough to survive one flaky check.

Add a keyword check that a known string is present in the homepage body. A site that returns 200
with an empty page is still down.

## What to alert on

TODO: configure each row, then fire each one deliberately once and confirm it arrives. An alert that
has never fired is an alert you are trusting without evidence.

| Condition | Threshold | Severity | Destination |
|---|---|---|---|
| Site down (health check fails) | 2 consecutive failures, 2 locations | P1 | Alert channel, on-call phone, project lead |
| 5xx rate spike | > 2 % of requests over 5 minutes, or > 20 in 5 minutes | P1 | Alert channel, project lead |
{%- if cookiecutter.sentry == "yes" %}
| Unhandled exception burst | A new issue with > 10 events in 10 minutes | P2 | Alert channel, project lead |
| New issue type in production | First occurrence | P3 | Alert channel |
{%- endif %}
| Response time degradation | p95 > 3 s for 10 minutes | P2 | Alert channel |
| Disk usage | > 80 % warn, > 90 % page | P2 / P1 | Infrastructure, project lead |
| Database connections | > 80 % of `max_connections` for 5 minutes | P2 | Infrastructure, project lead |
| CPU or memory | Sustained > 90 % for 15 minutes | P2 | Infrastructure |
| TLS certificate expiry | 21 days warn, 7 days page | P2 / P1 | Infrastructure, project lead |
| Backup failed or did not run | Any failure, or no success in 26 hours | P1 | Infrastructure, project lead |
| Restore test overdue | No successful test in the agreed period | P3 | Project lead |
| Scheduled job not running | No completion within its interval plus 50 % | P2 | Alert channel |
| Queued e-mail backlog | Unsent queue > 100, or anything unsent for > 30 minutes | P2 | Alert channel |
{%- if cookiecutter.task_queue != "none" %}
| **Background {% if cookiecutter.task_queue == "huey" %}consumer{% else %}worker{% endif %} not running** | Process absent for 2 minutes | P1 | Alert channel, project lead |
{%- if cookiecutter.task_queue == "celery" %}
| **beat not running** | Process absent for 2 minutes | P1 | Alert channel, project lead |
{%- endif %}
| Task queue depth growing | Depth rising for 15 minutes with no completions | P2 | Alert channel |
| Task failing on every attempt | Any task, 3 consecutive failures | P2 | Alert channel |
{%- endif %}
{%- if cookiecutter.rate_limiting == "yes" %}
| Login lockout spike | > 20 lockouts in 10 minutes | P2 | Alert channel, project lead |
{%- endif %}
{%- if cookiecutter.sentry == "yes" %}
| Error-monitoring quota | > 80 % of the monthly quota | P3 | Project lead |
{%- endif %}

An alert that fires three times without anyone acting is either fixed or has its threshold changed,
with the change recorded. Alerts nobody acts on train people to ignore alerts.

## Logging

The application logs to standard output. The process manager owns capture, rotation and retention —
the application never opens its own log file and never writes into the deployment directory.

What ships in `settings/base.py`:

- A single console handler with the format
  `{levelname} {asctime} {name} {process:d} {message}`.
- Root logger at `LOG_LEVEL`, default `INFO`. **`INFO` is the production floor.**
- `django.security` at `WARNING`, so authentication and CSRF failures are visible.
{%- if cookiecutter.rate_limiting == "yes" %}
- `axes` at `WARNING`, so lockouts are visible.
{%- endif %}
- A `{{ cookiecutter.project_slug }}` logger at `LOG_LEVEL` for application messages.

Read them with:

{% if cookiecutter.deploy_target == "gunicorn_nginx" -%}
```bash
journalctl -u {{ cookiecutter.project_slug }}-gunicorn -n 200 --no-pager
journalctl -u {{ cookiecutter.project_slug }}-gunicorn -f            # follow
journalctl -u {{ cookiecutter.project_slug }}-gunicorn --since "2 hours ago" -p err
```
{%- else -%}
```bash
docker compose logs --tail=200 web
docker compose logs -f web
```
{%- endif %}

### Log levels

| Level | Use |
|---|---|
| `DEBUG` | Development only |
| `INFO` | A business event worth reconstructing later: form submitted, mail queued, job finished |
| `WARNING` | A handled anomaly: an upload rejected, an upstream call retried |
| `ERROR` | A failure a human should look at |
| `CRITICAL` | The site is not functioning |

Log messages are static strings with structured arguments, not interpolated sentences — a static
message groups, an f-string produces a new unique message per request.

`django.db.backends` stays at `WARNING`. At `DEBUG` it logs every query **with its parameter
values**, which puts personal data in the log.

### What must never be logged

- Passwords, password-reset tokens, API keys{% if cookiecutter.api != "none" %}, JWTs{% endif %}, session keys, CSRF tokens, or any
  `Authorization` header — in any form, including "just the first few characters".
- Payment card numbers, CVVs, IBANs, or national or civil identity numbers. Where an identifier is
  genuinely needed for support, log the last four characters only.
- Personal data in a URL or query string. It reaches the access log, the proxy, the browser history
  and the `Referer` header of every outbound link.
- Uploaded file contents, e-mail message bodies, or full form submissions. Log the stored record's
  identifier instead.
- Raw upstream exception text rendered back to an end user.

TODO: the shipped configuration does not yet correlate log lines with a request identifier, and
production logs are plain text rather than one JSON object per line. Both are worth adding when this
project gains a log collector: a request ID on every line, returned in an `X-Request-ID` response
header and shown on the 500 page, turns "a user reported an error at about 3pm" into one exact
timeline.

{% if cookiecutter.sentry == "yes" -%}
## Error monitoring

Error monitoring is active only when `SENTRY_DSN` is set. With it empty the SDK is never initialised
and no network call is made, which is why development and CI need no configuration.

| Setting | Value | Why |
|---|---|---|
| `SENTRY_ENVIRONMENT` | `development`, `staging` or `production` — exactly these | Alerting and issue grouping depend on it |
| `SENTRY_RELEASE` | The deployed git tag | Attributes an issue to a release |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.0` by default | Raise to `0.05`–`0.1` for a bounded investigation and **turn it back down**. Left at `1.0`, the quota is gone within days and errors stop being delivered |
| `SENTRY_SEND_DEFAULT_PII` | `False`, and stays false | With it false, events carry no request body, no cookies, no user e-mail and no client IP |

Turning PII on requires written client agreement and a note in the project's data register.

A view handling credentials, payment data or identity documents needs a `before_send` hook that drops
or masks those frames, with a test asserting the field is removed. TODO: record here if any view in
this project needs one.

The deliberate-error endpoint is registered only when `DEBUG` is on **and** a DSN is set, so it can
never be routable in production. A test asserts it returns 404 under production settings.
{%- else -%}
## Error monitoring

**This project was generated without error monitoring.** Unhandled exceptions appear in the
application log and nowhere else, so nobody is alerted and nobody can tell whether an error is new,
frequent, or affecting one user or all of them.

TODO: record this as an accepted risk in [14-decisions.md](14-decisions.md) with the reason, or add
Sentry. It is gated on `SENTRY_DSN`, so adding it costs one dependency and one environment variable.
{%- endif %}

## Troubleshooting: the five most likely failures

**Before anything else, check free disk space.** A full disk causes failures that look like
everything else on this list, and it is the most common cause of a site that "suddenly stopped
working".

```bash
df -h
{%- if cookiecutter.media_storage == "filesystem" %}
du -sh /srv/{{ cookiecutter.project_slug }}/media /srv/{{ cookiecutter.project_slug }}/private-media
{%- else %}
# Media is in the object store, so it never fills this disk. Its size and growth
# are tracked in the provider's console - see 03-infrastructure.md.
{%- endif %}
```

| Symptom | Most likely cause | First response |
|---|---|---|
| **Every page shows an error page** after a release | A migration did not apply, a required configuration value is missing, or the release is faulty | Read the newest error for the exact exception. Confirm the migration state with `showmigrations`. If the cause is not obvious inside the agreed rollback window, roll back ([07-deployment.md](07-deployment.md)) and investigate on staging |
| **The site is unreachable** — timeout or gateway error | The application service is not running, or the server is out of disk or memory | Check disk, then service status, then restart. Read the log from just before the failure: the reason is almost always the last few lines before the process stopped |
| **Forms submit but no e-mail arrives** | Mail credentials changed, the message was rejected as spam, or the relay is refusing the sender | Open the e-mail log in the administration interface — every send is recorded there with its status, which distinguishes "never attempted" from "attempted and rejected". Then verify the credentials and the sending domain's mail authentication records. Check the recipient's spam folder before concluding the site is at fault |
{%- if cookiecutter.media_storage == "filesystem" %}
| **Uploaded images or documents do not appear**, or return a permission error | Ownership or permissions on the upload directory, a full disk, or a changed path after a server move | Confirm the file exists where the application expects it. Check ownership and permissions. Check disk space. Confirm the web server serves that directory — and confirm it does **not** serve `private-media` |
{%- else %}
| **Uploaded images or documents do not appear**, or return a permission error | Object-store credentials expired or were rotated, the identity lost a permission, or the bucket name changed | Run `manage.py check` — `core.W006` reports missing configuration. Then confirm the deployed identity can still read and write the bucket. An editorial image that 403s usually means a signed URL was cached past its expiry, not that the object is gone |
{%- endif %}
| **The browser warns the site is not secure** | Certificate renewal failed silently | Check expiry and issuer, run the renewal manually, reload the web server. Then fix the automation, and confirm the expiry alert fired — if it did not, that is a second fault to fix |

Also specific to this project:

{% if cookiecutter.rate_limiting == "yes" -%}
| Symptom | Most likely cause | First response |
|---|---|---|
| **Legitimate users are locked out of the admin, or a form rejects everyone** | `AXES_IPWARE_PROXY_COUNT` does not match the real number of proxies, so every request appears to come from the load balancer and one attacker locks out everyone | Check the recorded client IP on a recent access attempt. If it is the proxy's address, correct `AXES_IPWARE_PROXY_COUNT` and restart |
{%- if cookiecutter.cache != "redis" %}
| **A rate limit lets through several times its stated budget** | The cache is per-process, so each worker keeps its own counter | Switch the cache to Redis. This is a production defect, not a tuning question |
{%- endif %}
{%- else -%}
| Symptom | Most likely cause | First response |
|---|---|---|
| **Repeated login attempts against the admin** | No lockout is configured on this project | There is no automated defence to check. Escalate; see [14-decisions.md](14-decisions.md) |
{%- endif %}
{%- if cookiecutter.spam_protection == "turnstile_honeypot" %}
| **Every form submission is rejected as spam** | Outbound access to the verification endpoint is blocked, or the secret key is wrong or missing | Check outbound connectivity to the verification host and the configured keys. With no key the protection degrades to honeypot-only rather than rejecting everyone, so total rejection means a key is present but wrong |
{%- endif %}
{%- if cookiecutter.task_queue != "none" %}
| **A scheduled job silently stopped happening** | The background {% if cookiecutter.task_queue == "huey" %}consumer{% else %}worker or beat{% endif %} is not running, or was not restarted by a deploy | Check the process first, then its log. A stopped worker produces silence, not errors, so nothing else will have told you |
| **Tasks run the previous release's behaviour** | The deploy restarted the web process but not the {% if cookiecutter.task_queue == "huey" %}consumer{% else %}worker{% endif %} | Compare the process start time with the deploy time. Restart it; see [07-deployment.md](07-deployment.md) |
| **A task is enqueued but never executes** | It is not registered with the worker — usually because it is not in an app's `tasks.py` | Read the worker's startup log: it lists everything it can run. A task absent from that list will never fire |
{%- if cookiecutter.task_queue == "celery" and cookiecutter.task_broker == "sqs" %}
| **A task appears to run twice** | `AWS_SQS_VISIBILITY_TIMEOUT` is shorter than the task takes, so SQS redelivered it to a second worker | Raise the visibility timeout above `CELERY_TASK_TIME_LIMIT`. `manage.py check` reports this as `tasks.W003` |
| **`celery inspect` and Flower show nothing** | Working as designed: SQS carries no Celery remote control or events | Use CloudWatch for queue depth and message age, and the worker's own log for what it is doing |
{%- endif %}
{%- if cookiecutter.task_queue == "celery" %}
| **Every periodic task fires twice** | Two beat processes are running | There is exactly one beat per environment, not one per application server |
| **Every periodic task fires at once after a restart** | The beat schedule file was deleted, so every task looks "never run" | Restore or accept the one-off burst, then put `CELERY_BEAT_SCHEDULE_FILENAME` somewhere a deploy does not wipe |
{%- endif %}
{%- endif %}

For each incident, also record: whether it affects all visitors or one, who to escalate to, and the
emergency contacts with the hours they are available.

TODO: fill in the escalation contacts and their hours.

## Response times during warranty

| Severity | Meaning | First response | Target resolution |
|---|---|---|---|
| P1 | Site down, forms broken, data loss, active security incident | 1 hour in business hours, 4 hours outside | Same day, with hourly updates |
| P2 | Major feature broken with no workaround; severe performance degradation | 4 business hours | 2 business days |
| P3 | Minor defect; a workaround exists | 1 business day | Next scheduled release |
| P4 | Cosmetic or content issue; enhancement | 2 business days | Scheduled from the backlog |

Business hours are Sunday to Thursday, 09:00 to 18:00 Kuwait time, unless the contract says
otherwise. TODO: confirm against the maintenance agreement.

Every P1 gets a written post-incident note within two working days: what happened, who was affected,
the cause, the fix, and the test or alert that now covers it. Every fixed defect gets a regression
test.

## Log retention

| Log | Retention | Held by |
|---|---|---|
| Application log | 30 days hot, 90 days archived | Process manager / log collector |
| Web server access and error logs | 90 days, rotated daily, compressed | Web server |
{%- if cookiecutter.sentry == "yes" %}
| Error monitoring events | 90 days by default | Sentry |
{%- endif %}
| Uptime check history | 12 months | Uptime provider |
| Admin action log | At least 12 months | The application database |
| E-mail send log | 90 days, then purged by a scheduled job | The application database |
| Backup job history | 12 months | Backup system |
| Post-incident notes | Life of the project | This repository |

Any pruning job carries its retention period in its command arguments, so the policy is visible in
the crontab rather than buried in code.
