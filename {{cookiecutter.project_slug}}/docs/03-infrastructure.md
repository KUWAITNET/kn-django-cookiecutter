# 3. Server and infrastructure requirements

Enough detail that a competent system administrator can build an identical server without asking a
question. Minimums and recommendations are stated separately: a minimum that is really a
recommendation gets ignored, and a recommendation that is really a minimum causes an outage.

## Operating system

TODO: record the exact operating system and version, e.g. Ubuntu 24.04 LTS, and its support end
date.

Requirements the application makes of it:

- A supported Python {{ cookiecutter.python_version }} runtime. Install it with `uv` rather than the
  distribution package, so the version matches `.python-version` exactly.
- `libmagic1`. Upload validation sniffs the real content type of every uploaded file; without
  `libmagic1` that check cannot run.
{%- if cookiecutter.languages == "en_ar" %}
- `gettext`. Translation catalogues are compiled at deploy time; `.mo` files are never committed.
{%- endif %}
- Locale generated for `en_US.UTF-8`. TODO: confirm the locale and that the database was created
  with UTF-8 encoding.
- System timezone UTC. The application's `TIME_ZONE` is `{{ cookiecutter.timezone }}` and
  `USE_TZ = True`, so timestamps are stored in UTC and rendered in local time. Setting the server
  clock to local time gains nothing and makes log correlation harder.
- NTP time synchronisation running. Time-based one-time passwords and certificate validation both
  depend on it.

## Sizing

| Resource | Minimum | Recommended | Notes |
|---|---|---|---|
| CPU | 2 vCPU | 4 vCPU | gunicorn runs 3 workers by default; raise workers only with cores{% if cookiecutter.task_queue != "none" %}. The background {% if cookiecutter.task_queue == "huey" %}consumer{% else %}worker and beat{% endif %} share these cores with the web process{% endif %} |
{%- if cookiecutter.task_queue == "huey" %}
| Memory | 2 GB | 4 GB | Django workers plus PostgreSQL{% if cookiecutter.cache == "redis" %} plus Redis{% endif %} on one host, **plus the task consumer**: it loads the whole Django application, so budget roughly what one gunicorn worker costs (200–300 MB) |
{%- elif cookiecutter.task_queue == "celery" %}
| Memory | 2 GB | 4 GB | Django workers plus PostgreSQL{% if cookiecutter.cache == "redis" %} plus Redis{% endif %} on one host, **plus a Celery worker and beat**. Each loads the whole Django application: budget one gunicorn worker's memory per worker process (200–300 MB), and about half that for beat{% if cookiecutter.task_broker == "rabbitmq" %}. RabbitMQ adds ~300 MB again if it runs here, which it should not{% endif %} |
{%- else %}
| Memory | 2 GB | 4 GB | Django workers plus PostgreSQL{% if cookiecutter.cache == "redis" %} plus Redis{% endif %} on one host |
{%- endif %}
{%- if cookiecutter.media_storage == "filesystem" %}
| Disk (application + media) | 20 GB | 40 GB | TODO: media is currently ___ GB, growing ~___ GB/year |
{%- else %}
| Disk (application) | 10 GB | 20 GB | Code, virtualenv{% if cookiecutter.static_storage != "cloud" %} and `staticfiles/`{% endif %}. Media is in the object store, so it does **not** grow this disk |
{%- endif %}
| Disk (database) | 10 GB | 20 GB | TODO: database is currently ___ GB |
| Swap | 1 GB | 2 GB | Prevents an out-of-memory kill during `collectstatic` or a large import |
{%- if cookiecutter.media_storage != "filesystem" %}
| Object storage | — | — | TODO: bucket is currently ___ GB, growing ~___ GB/year. Priced per GB-month plus egress |
{%- endif %}

TODO: fill in the current sizes and the growth rate the first time this is deployed, and revisit
them at every release. Uploaded media only grows; a
{%- if cookiecutter.media_storage == "filesystem" %} disk that was comfortable at launch is the most
common cause of a site that "suddenly stopped working" two years later.
{%- else %} bucket has no size limit to hit, so the failure
mode moves from an outage to a bill nobody was watching. Egress is the line item that surprises
people: every private download is streamed through the application, so each one is billed twice —
bucket to application, application to visitor.
{%- endif %}

Re-measure with:

```bash
{%- if cookiecutter.media_storage == "filesystem" %}
du -sh /var/www/{{ cookiecutter.project_slug }}/media /var/www/{{ cookiecutter.project_slug }}/private-media
{%- elif cookiecutter.media_storage == "s3" %}
aws s3 ls --summarize --human-readable --recursive "s3://$AWS_STORAGE_BUCKET_NAME"
{%- elif cookiecutter.media_storage == "gcs" %}
gcloud storage du --summarize --readable-sizes "gs://$GS_BUCKET_NAME"
{%- else %}
az storage blob list --container-name "$AZURE_CONTAINER" --query "sum(@[].properties.contentLength)"
{%- endif %}
psql "$DATABASE_URL" -c "SELECT pg_size_pretty(pg_database_size(current_database()));"
df -h
```

## Ports

| Port | Service | Exposed to |
|---|---|---|
| 443 | HTTPS | Internet |
| 80 | HTTP, redirects to HTTPS only | Internet |
| 22 | Administrative access (SSH, key authentication only) | TODO: restrict to the office/VPN range |
| 5432 | PostgreSQL | Localhost only |
{%- if cookiecutter.cache == "redis" or (cookiecutter.task_queue == "huey" and cookiecutter.huey_backend == "redis") or (cookiecutter.task_queue == "celery" and cookiecutter.task_broker == "redis") %}
| 6379 | Redis | Localhost only |
{%- endif %}
{%- if cookiecutter.task_queue == "celery" and cookiecutter.task_broker == "rabbitmq" %}
| 5672 | RabbitMQ (AMQP) | The application host only. Never the internet: the broker holds every task's arguments |
| 15672 | RabbitMQ management UI | TODO: restrict to the office/VPN range, or leave the plugin disabled |
{%- endif %}
| 8000 | gunicorn | Localhost only, behind the reverse proxy |

The application listens on `127.0.0.1:8000`. Anything that reaches gunicorn directly from the
internet bypasses TLS, the request size limits and the access log.

## Accounts and process ownership

| Account | Runs | Notes |
|---|---|---|
| `{{ cookiecutter.project_slug }}` | gunicorn, management commands, cron jobs{% if cookiecutter.task_queue == "huey" %}, the task consumer{% elif cookiecutter.task_queue == "celery" %}, the Celery worker and beat{% endif %} | No login shell required for the service itself; no sudo |
{%- if cookiecutter.deploy_target == "gunicorn_nginx" %}
| `www-data` | nginx | Needs read access to `staticfiles/` and `media/` only |
{%- endif %}
| `postgres` | PostgreSQL | — |

The application account owns the code and the media directories. It must **not** own the backup
destination: a compromised application account that can also delete the backups leaves nothing to
restore from.

## Filesystem layout

{% if cookiecutter.deploy_target == "gunicorn_nginx" -%}
```text
/var/www/{{ cookiecutter.project_slug }}/
├── app/                      the git checkout
│   ├── .venv/                created by uv sync --frozen --no-dev
│   ├── manage.py
│   ├── apps/
│   ├── {{ cookiecutter.project_slug }}/
│   └── staticfiles/          written by collectstatic, served by nginx and WhiteNoise
{%- if cookiecutter.media_storage == "filesystem" %}
├── media/                    MEDIA_ROOT - public uploads, web readable
├── private-media/            PRIVATE_MEDIA_ROOT - personal data, NEVER web readable
{%- endif %}
└── .env                      environment file, mode 0600, owned by the app account
```
{%- else -%}
```text
/srv/{{ cookiecutter.project_slug }}/
├── app/                      the git checkout (docker compose build context)
│   └── docker-compose.yml
{%- if cookiecutter.media_storage == "filesystem" %}
├── media/                    bind-mounted to MEDIA_ROOT in the container
├── private-media/            bind-mounted to PRIVATE_MEDIA_ROOT - personal data
{%- endif %}
└── .env                      environment file, mode 0600, read by docker compose
```
{%- endif %}

Rules that are not negotiable:

- `.env` is mode `0600`, owned by the application account. It contains the database password, the
  mail password{% if cookiecutter.media_storage != "filesystem" %}, the object-store credentials{% endif %} and `SECRET_KEY`. A world-readable `.env` is a credential disclosure.
{%- if cookiecutter.media_storage == "filesystem" %}
- `private-media/` is **never** mapped to a public URL by the reverse proxy. A private file reaches a
  browser only through the application - the permission gate at `/files/<app.model>/<pk>/<field>/`
  or a signed `/files/signed/<token>/` link - and, once `PRIVATE_FILES_ACCEL_PREFIX` is set, from
  the `internal` nginx location below, which a browser cannot request directly. TODO: after the
  first deploy, run the checks under "Private files on disk" and record the results.
- `media/` is served by the reverse proxy but must not execute anything. Deny script handlers for
  that location.
{%- else %}
- There is **no media directory on this server**. Uploads go straight to the object store, so
  nothing the reverse proxy can reach holds a visitor's file. That removes a whole class of
  misconfiguration and replaces it with the bucket policy below, which is now the thing that must
  be right.
{%- endif %}
- `staticfiles/` is generated, never edited on the server, and never committed.
{%- if cookiecutter.media_storage == "filesystem" %}

## Private files on disk

Django can stream a private file itself, and does until `PRIVATE_FILES_ACCEL_PREFIX` is set. On a
real server, let nginx send the bytes instead: Django checks the signature or the permission, then
answers with an empty response and an `X-Accel-Redirect` header, so no gunicorn worker is held for
the length of a download.

```nginx
# Reachable only through X-Accel-Redirect from Django, never from a browser.
location /protected-private/ {
    internal;
    alias /var/www/{{ cookiecutter.project_slug }}/private-media/;
    add_header Cache-Control "private, no-store" always;
    add_header X-Content-Type-Options "nosniff" always;
}
```

and in `.env`:

```bash
PRIVATE_MEDIA_ROOT=/var/www/{{ cookiecutter.project_slug }}/private-media
PRIVATE_FILES_ACCEL_PREFIX=/protected-private/
```

- `internal` is what makes this safe: a browser asking for `/protected-private/...` gets a 404.
- Django sets `Content-Type` and `Content-Disposition` (attachment for anything that is not an
  image, SVG included) and nginx keeps them, so an uploaded HTML file never renders on this origin.
- **The nginx user must be able to read the folder**: execute on every parent directory, read on
  the files. A folder at `750` owned by the application user gives a 403 that looks like a Django
  bug and is not. Use `755`/`644`, or add the nginx user to the application's group.

Checking it works:

```bash
# 1. the internal location is not reachable from outside -> 404
curl -sI https://{{ cookiecutter.domain_name }}/protected-private/anything | head -1
# 2. a private file is not under /media/ -> 404
curl -sI https://{{ cookiecutter.domain_name }}/media/<a private file's name> | head -1
# 3. a signed link (copy one from a page or the API) -> 200, served by nginx
# 4. the same link after PRIVATE_URL_EXPIRY_SECONDS -> 404
```
{%- else %}

## Object storage

Media lives in an object store instead of on a disk. That trades a capacity problem for a
permissions problem, and the permissions problem is the one that leaks personal data, so it is
spelled out here.

### Layout

| Prefix | Holds | Reachable how |
|---|---|---|
| `media/` (`MEDIA_LOCATION`) | Editorial media: page images, brochures, logos | Signed URLs built by the application, expiring after `{% if cookiecutter.media_storage == "s3" %}AWS_QUERYSTRING_EXPIRE{% elif cookiecutter.media_storage == "gcs" %}GS_EXPIRATION_SECONDS{% else %}AZURE_URL_EXPIRATION_SECS{% endif %}` seconds |
| `private/` (`PRIVATE_MEDIA_LOCATION`), in the private {% if cookiecutter.media_storage == "azure" %}container{% else %}bucket{% endif %} | Personal data: CVs, ID copies, form attachments | A page link goes through the permission gate at `/files/<app.model>/<pk>/<field>/`, which redirects to a fresh signed URL; `<img src>` and API responses carry a signed URL directly. Every one expires after `PRIVATE_URL_EXPIRY_SECONDS` |
{%- if cookiecutter.static_storage == "cloud" %}
| `static/` (`STATIC_LOCATION`) | Collected CSS, JS, fonts, icons | Public read — the **only** prefix that is allowed to be. Names are content-hashed, so the URLs never expire |
{%- endif %}

Private files live in a
{%- if cookiecutter.media_storage == "s3" %} bucket of their own, `AWS_PRIVATE_BUCKET_NAME`
{%- elif cookiecutter.media_storage == "gcs" %} bucket of their own, `GS_PRIVATE_BUCKET_NAME`
{%- else %} container of their own, `AZURE_PRIVATE_CONTAINER`
{%- endif %}, never beside public media: a policy boundary is harder to get wrong than a prefix in a
policy, and a mistake in the public policy then cannot reach personal data at all. `manage.py check`
fails with `core.E010` if it is the same as the media one. **No CDN in front of it, ever**: a plain
CDN serves whatever it has cached to anyone until it expires.

### What the {% if cookiecutter.media_storage == "azure" %}container{% else %}bucket{% endif %} must and must not allow

{% if cookiecutter.media_storage == "s3" -%}
- **Block Public Access on at the bucket level**{% if cookiecutter.static_storage == "cloud" %}, except for a bucket policy scoped to `static/*` and
  nothing else{% endif %}. TODO: paste the applied policy here.
- Object ownership set to **bucket owner enforced** (ACLs disabled). The application sends no ACL,
  which is why this works; a bucket that still honours ACLs is one `AWS_DEFAULT_ACL` away from
  publishing everything.
- **Versioning on.** This is the backup — see [08-backup-restore.md](08-backup-restore.md).
- Default encryption (SSE-S3 or SSE-KMS) on. TODO: record which.
- Server access logging or CloudTrail data events on, to a *different* bucket. TODO: record where.
- The application's IAM identity may `GetObject`, `PutObject`, `DeleteObject` and `ListBucket` on
  this bucket and nothing else. It must **not** hold `PutBucketPolicy`, `PutBucketAcl` or
  `DeleteBucket`: a compromised application must not be able to make the bucket public or destroy
  the versions that are the backup.
- **Use the server's role, never keys.** On EC2 attach an instance role (IRSA on EKS) and leave
  `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` unset: role credentials are temporary and never written
  down. Check with `aws sts get-caller-identity`, which must show `assumed-role/<role>/...`. Keys are
  for an S3-compatible store only. TODO: record the role name and its policy, covering both buckets.
- The private bucket additionally: no CloudFront distribution, no bucket policy granting
  `s3:GetObject` to `*`, versioned, encrypted, and a `aws:SecureTransport` deny for plain HTTP.
{%- elif cookiecutter.media_storage == "gcs" -%}
- **Uniform bucket-level access on** (object ACLs disabled). The application sends no ACL, which is
  why this works; a bucket that still honours object ACLs is one `GS_DEFAULT_ACL` away from
  publishing everything.
- **No `allUsers` or `allAuthenticatedUsers` binding**{% if cookiecutter.static_storage == "cloud" %}, except a `roles/storage.objectViewer` binding
  covering the static files — which, because GCS IAM is per-bucket, means putting them in a separate
  bucket rather than a prefix of this one{% endif %}. TODO: paste the applied IAM policy here.
- **Object versioning on.** This is the backup — see [08-backup-restore.md](08-backup-restore.md).
- Encryption at rest is on by default; TODO: record whether a customer-managed key is required.
- Data access audit logs on. TODO: record where they go.
- The application's service account holds `roles/storage.objectAdmin` on this bucket and nothing
  else — never `roles/storage.admin`, which can change the bucket's IAM policy and delete the
  versions that are the backup.
- Prefer **workload identity** over a downloaded key file. If a key file is unavoidable, TODO:
  record its path, its mode (`0600`), and the rotation schedule.
{%- else -%}
- The container's public access level must be **Private (no anonymous access)**{% if cookiecutter.static_storage == "cloud" %}, except for a
  separate container set to "Blob" holding the static files{% endif %}. Azure has no per-object ACL, so the
  container setting is the whole control. TODO: record the applied setting per container.
- **Blob versioning on**, with soft delete for blobs and containers. This is the backup — see
  [08-backup-restore.md](08-backup-restore.md).
- Encryption at rest is on by default; TODO: record whether a customer-managed key is required.
- Storage analytics logging on, to a different account. TODO: record where.
- The application's identity holds **Storage Blob Data Contributor** on this container and nothing
  else — never Owner or Contributor at the account scope, which can change the public access level
  and delete the versions that are the backup.
- Prefer a **managed identity** over an account key. If a key is unavoidable, TODO: record the
  rotation schedule and who owns it.
{%- endif %}

`manage.py check` fails with `core.E001`/`core.E002` if the settings would make a media storage
world-readable, and warns with `core.W006` under production settings when the bucket name or the
credentials are missing. Those checks read the application's configuration, not the bucket's — they
cannot see a policy applied in the console, so the list above still has to be verified by hand once,
and recorded here.

### Signed links and their lifetime

The permission gate checks on the click and then redirects to a freshly signed URL, so the bytes go
straight from the bucket and never hold a worker. A signed URL is a bearer token until it expires,
which is why the lifetime is short (`PRIVATE_URL_EXPIRY_SECONDS`, an hour at most without a written
reason), why signed links are never handed to anonymous callers, and why e-mails, SMS and push
notifications link to the page or the gate - never to a signed URL.
{%- if cookiecutter.media_storage == "s3" %}

A presigned URL also dies with the credentials that signed it. Role credentials last about six hours
and are refreshed shortly before they run out, so a link signed just before a refresh can stop working
early. Clients handle a 403 by refetching the resource for a new link.
{%- endif %}

Public editorial media is served by a signed URL that the application generates but does not proxy,
so it costs one bucket egress and no application time.
{%- endif %}

## Moving existing files to private

Changing a field to `storage=private_media_storage` moves nothing: files uploaded before the change
stay in public storage, on a public URL, until they are copied. `manage.py migrate_private_files`
copies every private field's files from `default` to `private` under the same name, so no database
row changes. It is safe to re-run, reports missing files and exits non-zero on any failure, and
refuses to run when both storages point at the same place.

1. Create the private {% if cookiecutter.media_storage == "filesystem" %}folder, outside `MEDIA_ROOT`, readable by the nginx user{% elif cookiecutter.media_storage == "azure" %}container and grant the application's identity access{% else %}bucket and grant the application's role access{% endif %}.
2. Set the environment ({% if cookiecutter.media_storage == "filesystem" %}`PRIVATE_MEDIA_ROOT`{% elif cookiecutter.media_storage == "s3" %}`AWS_PRIVATE_BUCKET_NAME`{% elif cookiecutter.media_storage == "gcs" %}`GS_PRIVATE_BUCKET_NAME`{% else %}`AZURE_PRIVATE_CONTAINER`{% endif %}), deploy, restart, and run `migrate` (an `AlterField`, no SQL).
3. `manage.py migrate_private_files --dry-run`; fix any failure (usually access) and repeat.
4. `manage.py migrate_private_files`.
5. Open private files in the browser and confirm they load through the gate.
6. `manage.py migrate_private_files --delete-source`: copies anything uploaded since step 4, then
   deletes each public copy once it exists in private storage.
7. On any project with a CDN, invalidate the old paths: it keeps serving a cached copy of a deleted
   object until the cache expires.

History tables (django-simple-history and the like) store file names as text: their rows keep the
old names and are not copied.

## Outbound network access the application needs

| Destination | Port | Why | Blocked means |
|---|---|---|---|
| SMTP relay (TODO: host) | 587 (TLS) | All outgoing mail | Mail queues, forms appear to succeed but nothing arrives |
{%- if cookiecutter.media_storage == "s3" %}
| `s3.<region>.amazonaws.com` (or the `AWS_S3_ENDPOINT_URL` host) | 443 | Every media read and write{% if cookiecutter.static_storage == "cloud" %}, and `collectstatic` at deploy time{% endif %} | No uploads, no editorial images, every private download 500s |
{%- elif cookiecutter.media_storage == "gcs" %}
| `storage.googleapis.com` and `oauth2.googleapis.com` | 443 | Every media read and write, plus token minting{% if cookiecutter.static_storage == "cloud" %}, and `collectstatic` at deploy time{% endif %} | No uploads, no editorial images, every private download 500s |
{%- elif cookiecutter.media_storage == "azure" %}
| `<account>.blob.core.windows.net` | 443 | Every media read and write{% if cookiecutter.static_storage == "cloud" %}, and `collectstatic` at deploy time{% endif %} | No uploads, no editorial images, every private download 500s |
{%- endif %}
{%- if cookiecutter.spam_protection == "turnstile_honeypot" %}
| `challenges.cloudflare.com` | 443 | Server-side verification of the spam-protection token | Every protected form submission is rejected |
{%- endif %}
{%- if cookiecutter.sentry == "yes" %}
| Sentry ingest host (TODO: from the DSN) | 443 | Error reports | Errors are logged locally only, no alerts |
{%- endif %}
{%- if cookiecutter.task_queue == "celery" and cookiecutter.task_broker == "sqs" %}
| `sqs.<region>.amazonaws.com` | 443 | Every task enqueue and every worker poll | Nothing is queued and nothing runs. The web request that enqueues will block on the SDK's retries first, so a blocked broker looks like a slow site |
{%- elif cookiecutter.task_queue == "celery" and cookiecutter.task_broker == "rabbitmq" %}
| RabbitMQ host (TODO: hostname) | 5672 | Every task enqueue and every worker poll | Nothing is queued and nothing runs |
{%- endif %}
| Package index and git host | 443 | Deploys and dependency installation | Deploys fail |

Nothing else is required at runtime. If an outbound rule has to be opened for a new integration,
add it to this table and to the third-party services register in the same change.
{%- if cookiecutter.task_queue != "none" %}

## The background {% if cookiecutter.task_queue == "huey" %}consumer{% else %}worker{% endif %}

{% if cookiecutter.task_queue == "huey" -%}
**One extra long-lived process**, started as `python manage.py run_huey`. It runs the queue and the
periodic schedule together, so there is no second scheduler to set up and nothing to forget on a new
machine.

It is the same code as the web application, running under the same account, with the same
environment. Three consequences worth stating before somebody discovers them:

- It **must be restarted by every deploy**. A worker that was not restarted keeps running the code
  it started with, against a database the new code has already migrated. See
  [07-deployment.md](07-deployment.md).
- It holds its own database connections. Add the consumer's worker count (`HUEY_WORKERS`) to the
  gunicorn worker count when sizing PostgreSQL's `max_connections`.
- If it is not running, nothing fails loudly. Tasks accumulate and scheduled work silently does not
  happen — which is why [09-monitoring.md](09-monitoring.md) treats "the worker is alive" as a
  monitored fact rather than an assumption.
{%- if cookiecutter.huey_backend == "postgres" %}

**No new service.** The queue is four tables in the application database, created by
`manage.py migrate`. It is backed up with everything else, it survives a restart because Postgres
does, and there is nothing extra to patch or monitor.
{%- elif cookiecutter.huey_backend == "redis" %}

**Redis holds the queue.** Two things follow. Queued tasks are lost on a Redis restart unless
persistence is configured (`appendonly yes`), and the queue is *not* in the database backup — a
restore brings back the data but not the work that was pending. Both are acceptable only if every
task is safe to lose.
{%- else %}

**SQLite holds the queue**, in a file on this host. It does not survive more than one worker process
and it does not survive a move to a second machine. This is a development configuration; see
[14-decisions.md](14-decisions.md).
{%- endif %}
{%- else -%}
**Two extra long-lived processes:** a Celery worker
(`celery -A {{ cookiecutter.project_slug }} worker`) and exactly one beat
(`celery -A {{ cookiecutter.project_slug }} beat`). Beat is the schedule; the worker executes.
Running two beat processes makes every periodic task fire twice, so it is one per environment, not
one per application server.

Both are the same code as the web application, running under the same account, with the same
environment. Consequences worth stating before somebody discovers them:

- They **must be restarted by every deploy**. A worker that was not restarted keeps running the code
  it started with, against a database the new code has already migrated. See
  [07-deployment.md](07-deployment.md).
- Each holds its own database connections. Add the worker's concurrency to the gunicorn worker count
  when sizing PostgreSQL's `max_connections`.
- Beat keeps "when did I last run this" in the file named by `CELERY_BEAT_SCHEDULE_FILENAME`. It
  must be writable and it must survive a deploy: delete it and every periodic task is treated as
  never run, so they all fire at once on the next start.
- If they are not running, nothing fails loudly. See [09-monitoring.md](09-monitoring.md).
{%- if cookiecutter.task_broker == "rabbitmq" %}

**RabbitMQ is another service to run.** It needs its own host or container, its own monitoring, its
own upgrade path, and its own backup story — the broker holds tasks that have been accepted but not
yet run, so losing it loses committed work. TODO: record where it runs, who patches it, what its
memory and disk high-water marks are set to, and whether its definitions (users, vhosts, policies)
are exported anywhere. A RabbitMQ that hits its disk alarm stops accepting publishes, and the
symptom is a web request that hangs.
{%- elif cookiecutter.task_broker == "sqs" %}

**There is no broker server.** SQS is managed: nothing to patch, monitor, back up or upgrade, and
IAM replaces broker credentials. What it costs instead:

- **The queue is not in any backup you control.** Messages live in SQS with its own retention
  (14 days maximum). A database restore does not bring back work that was in flight.
- **`celery inspect` and Flower do not work.** SQS carries no Celery remote control or events, so
  the usual "what is the worker doing right now" tools go dark. Monitor the queue depth and message
  age in CloudWatch, and the worker through its logs; see [09-monitoring.md](09-monitoring.md).
- **No broker-level priorities.** A task that must not wait behind another needs its own queue and a
  worker dedicated to it.
- **Visibility timeout is a correctness setting, not a tuning knob.** SQS makes a message visible
  again once `AWS_SQS_VISIBILITY_TIMEOUT` expires, whether or not the task is still running, and a
  second worker then picks it up. Keep it above `CELERY_TASK_TIME_LIMIT`; a system check enforces
  this.
- **IAM, not passwords.** The instance role needs `sqs:SendMessage`, `sqs:ReceiveMessage`,
  `sqs:DeleteMessage` and `sqs:GetQueueAttributes` on the project's queues. Setting
  `AWS_SQS_QUEUE_URL` lets you drop `sqs:ListQueues` and `sqs:GetQueueUrl` as well, so the worker
  can reach exactly one queue and discover nothing. TODO: record the queue ARNs and the role.

**Development does not use SQS.** `docker-compose.yml` provides a Redis, and `.env` points
`CELERY_BROKER_URL` at it. That is a deliberate difference between environments: for a queue the
application code is identical either way, and running a local SQS emulator costs more than it
proves. What it does **not** prove is the SQS-specific behaviour above — visibility timeout,
redelivery, and the absence of remote control. Exercise those on UAT against a real SQS queue
before go-live; it is an item on the go-live checklist, not an optional nicety.
{%- else %}

**Redis is the broker as well as the cache**, on a separate database number so that flushing the
cache cannot empty the queue. Redis is not a durable message broker: an unpersisted restart drops
whatever was queued, and there are no publisher confirms or dead-letter queues. That is acceptable
only while every task is safe to lose and safe to run twice. If a task appears that a customer has
been told already happened, the broker choice has to be revisited — see
[14-decisions.md](14-decisions.md).
{%- endif %}
{%- endif %}
{%- endif %}

## TLS

TODO: record the certificate issuer, whether renewal is automated, the renewal command, and where
the expiry alert goes.

The production settings enable HSTS with `SECURE_HSTS_SECONDS=2592000` (30 days), subdomains
included and preload requested. Two consequences to understand before go-live:

- Once a browser has seen the header, it refuses plain HTTP for this host for the full duration.
  Ship it only when TLS is correct on every subdomain the header covers.
- `SECURE_SSL_REDIRECT` and the `X-Forwarded-Proto` handling assume TLS terminates upstream. The
  proxy **must** strip any client-supplied `X-Forwarded-Proto` header, otherwise a client can claim
  its plain-HTTP request was secure.

## Reverse proxy requirements

{% if cookiecutter.deploy_target == "gunicorn_nginx" -%}
TODO: commit the real nginx server block alongside this document, or state where it is kept under
configuration management.

Whatever the final configuration, it must:

- Terminate TLS, redirect `80` to `443`, and serve nothing over plain HTTP but the redirect.
- Set `X-Forwarded-Proto` itself and strip any value the client sent.
- Set `client_max_body_size` to at least the application's request cap (10 MB) — a smaller value
  makes uploads fail at the proxy with an error the application never sees and cannot explain.
{%- if cookiecutter.static_storage == "cloud" %}
- Serve **nothing** from disk: both static files and media come from the object store.
{%- elif cookiecutter.media_storage == "filesystem" %}
- Serve `/static/` from `staticfiles/` and `/media/` from `media/`, and serve `private-media/` only
  from the `internal` location in "Private files on disk" above.
{%- else %}
- Serve `/static/` from `staticfiles/`. There is no `/media/` location: media is in the object
  store, and `/files/` must be proxied to the application like any other URL.
{%- endif %}
- Write an access log and an error log to the paths recorded in [09-monitoring.md](09-monitoring.md).
- Proxy everything else to `127.0.0.1:8000` with a read timeout at least as long as gunicorn's
  (60 s).
{%- else -%}
TODO: record which component terminates TLS in front of the compose stack, and confirm it sets
`X-Forwarded-Proto` itself and strips any client-supplied value.

Whatever the final configuration, it must terminate TLS, redirect port 80 to 443, allow request
bodies of at least 10 MB, and expose the container's port 8000 to nothing but itself.
{%- endif %}

## Database server

- PostgreSQL 17, UTF-8 encoding.
- One database and one role per environment. The application role owns its own schema and has no
  superuser rights.
- `CONN_MAX_AGE` is 60 seconds, so each gunicorn worker holds a connection open. Size
  `max_connections` for `workers x (1 + headroom)` plus room for management commands, cron jobs and
  a psql session. TODO: record the configured `max_connections`.
- Listening on localhost only. If the database is on a separate host, TODO: record the host, the
  network path, and that the connection is TLS-encrypted.

## What must be true before this server is considered ready

- [ ] `make check-deploy` reports zero issues under production settings.
- [ ] `https://{{ cookiecutter.domain_name }}/healthz` returns 200 and touches the database.
- [ ] `https://{{ cookiecutter.domain_name }}/{{ cookiecutter.admin_url_prefix }}/` loads over HTTPS
      and `/admin/` returns 404.
{%- if cookiecutter.media_storage == "filesystem" %}
- [ ] A file uploaded through the admin appears at the expected path with the expected ownership.
- [ ] The four checks under "Private files on disk" pass.
{%- else %}
- [ ] A file uploaded through the admin appears under the `media/` prefix in the bucket.
- [ ] A private upload appears under the `private/` prefix, and requesting its object URL directly —
      without a signature — returns 403, not the file.
- [ ] The same file opens through its `/files/<app.model>/<pk>/<field>/` link for an account holding
      the model's `PRIVATE_FILE_PERMISSIONS` entry, and returns 403 for one that does not.
- [ ] The application's storage identity cannot change the bucket policy: try it and confirm the
      denial.
{%- endif %}
- [ ] A backup has run and a restore has been performed onto a second machine
      ([08-backup-restore.md](08-backup-restore.md)).
- [ ] Every alert in [09-monitoring.md](09-monitoring.md) has been fired deliberately once and
      arrived.
