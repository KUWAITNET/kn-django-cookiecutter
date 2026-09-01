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
| CPU | 2 vCPU | 4 vCPU | gunicorn runs 3 workers by default; raise workers only with cores |
| Memory | 2 GB | 4 GB | Django workers plus PostgreSQL{% if cookiecutter.cache == "redis" %} plus Redis{% endif %} on one host |
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
{%- if cookiecutter.cache == "redis" %}
| 6379 | Redis | Localhost only |
{%- endif %}
| 8000 | gunicorn | Localhost only, behind the reverse proxy |

The application listens on `127.0.0.1:8000`. Anything that reaches gunicorn directly from the
internet bypasses TLS, the request size limits and the access log.

## Accounts and process ownership

| Account | Runs | Notes |
|---|---|---|
| `{{ cookiecutter.project_slug }}` | gunicorn, management commands, cron jobs | No login shell required for the service itself; no sudo |
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
- `private-media/` is **never** mapped to a URL by the reverse proxy. It is served only through the
  application's permission-checked private-media view at `/private-media/<path>`. TODO: after the
  first deploy, confirm by requesting a known private file's on-disk path directly through the web
  server and getting a 404.
- `media/` is served by the reverse proxy but must not execute anything. Deny script handlers for
  that location.
{%- else %}
- There is **no media directory on this server**. Uploads go straight to the object store, so
  nothing the reverse proxy can reach holds a visitor's file. That removes a whole class of
  misconfiguration and replaces it with the bucket policy below, which is now the thing that must
  be right.
{%- endif %}
- `staticfiles/` is generated, never edited on the server, and never committed.
{%- if cookiecutter.media_storage != "filesystem" %}

## Object storage

Media lives in an object store instead of on a disk. That trades a capacity problem for a
permissions problem, and the permissions problem is the one that leaks personal data, so it is
spelled out here.

### Layout

| Prefix | Holds | Reachable how |
|---|---|---|
| `media/` (`MEDIA_LOCATION`) | Editorial media: page images, brochures, logos | Signed URLs built by the application, expiring after `{% if cookiecutter.media_storage == "s3" %}AWS_QUERYSTRING_EXPIRE{% elif cookiecutter.media_storage == "gcs" %}GS_EXPIRATION_SECONDS{% else %}AZURE_URL_EXPIRATION_SECS{% endif %}` seconds |
| `private/` (`PRIVATE_MEDIA_LOCATION`) | Personal data: CVs, ID copies, form attachments | Only through `/private-media/<path>`, which checks `core.access_private_media` first and streams the object |
{%- if cookiecutter.static_storage == "cloud" %}
| `static/` (`STATIC_LOCATION`) | Collected CSS, JS, fonts, icons | Public read — the **only** prefix that is allowed to be. Names are content-hashed, so the URLs never expire |
{%- endif %}

The private prefix can be moved to a
{%- if cookiecutter.media_storage == "s3" %} bucket of its own with `AWS_PRIVATE_STORAGE_BUCKET_NAME`
{%- elif cookiecutter.media_storage == "gcs" %} bucket of its own with `GS_PRIVATE_BUCKET_NAME`
{%- else %} container of its own with `AZURE_PRIVATE_CONTAINER`
{%- endif %}. Do it: a policy boundary is harder to get wrong than a prefix in a policy, and it means a
mistake in the public policy cannot reach personal data at all.

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
- Prefer an **instance role / IRSA** over a long-lived access key. If a key is unavoidable, TODO:
  record the rotation schedule and who owns it.
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

### Egress and latency

Every byte a visitor downloads from the private prefix is paid for twice: bucket to application, then
application to visitor. That is the price of the permission check running on every request, and it is
the right default. For a project that serves large private files, `PRIVATE_MEDIA_SIGNED_URLS=True`
switches the view to a redirect so the bytes go straight from the bucket — read the trade-off in
[04-environment-variables.md](04-environment-variables.md) before turning it on.

Public editorial media is served by a signed URL that the application generates but does not proxy,
so it costs one bucket egress and no application time.
{%- endif %}

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
| Package index and git host | 443 | Deploys and dependency installation | Deploys fail |

Nothing else is required at runtime. If an outbound rule has to be opened for a new integration,
add it to this table and to the third-party services register in the same change.

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
- Serve `/static/` from `staticfiles/` and `/media/` from `media/`, and serve **nothing** from
  `private-media/`.
{%- else %}
- Serve `/static/` from `staticfiles/`. There is no `/media/` location: media is in the object
  store, and `/private-media/` must be proxied to the application like any other URL, never served
  from disk.
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
- [ ] A private-media file is unreachable except through the permission-checked view.
{%- else %}
- [ ] A file uploaded through the admin appears under the `media/` prefix in the bucket.
- [ ] A private upload appears under the `private/` prefix, and requesting its object URL directly —
      without a signature — returns 403, not the file.
- [ ] The same file downloads successfully through `/private-media/<path>` for an account holding
      `core.access_private_media`, and returns 403 for one that does not.
- [ ] The application's storage identity cannot change the bucket policy: try it and confirm the
      denial.
{%- endif %}
- [ ] A backup has run and a restore has been performed onto a second machine
      ([08-backup-restore.md](08-backup-restore.md)).
- [ ] Every alert in [09-monitoring.md](09-monitoring.md) has been fired deliberately once and
      arrived.
