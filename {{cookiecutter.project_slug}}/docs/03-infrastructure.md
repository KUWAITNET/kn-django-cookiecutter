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
| Disk (application + media) | 20 GB | 40 GB | TODO: media is currently ___ GB, growing ~___ GB/year |
| Disk (database) | 10 GB | 20 GB | TODO: database is currently ___ GB |
| Swap | 1 GB | 2 GB | Prevents an out-of-memory kill during `collectstatic` or a large import |

TODO: fill in the current sizes and the growth rate the first time this is deployed, and revisit
them at every release. Uploaded media only grows; a disk that was comfortable at launch is the most
common cause of a site that "suddenly stopped working" two years later.

Re-measure with:

```bash
du -sh /var/www/{{ cookiecutter.project_slug }}/media /var/www/{{ cookiecutter.project_slug }}/private-media
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
├── media/                    MEDIA_ROOT - public uploads, web readable
├── private-media/            PRIVATE_MEDIA_ROOT - personal data, NEVER web readable
└── .env                      environment file, mode 0600, owned by the app account
```
{%- else -%}
```text
/srv/{{ cookiecutter.project_slug }}/
├── app/                      the git checkout (docker compose build context)
│   └── docker-compose.yml
├── media/                    bind-mounted to MEDIA_ROOT in the container
├── private-media/            bind-mounted to PRIVATE_MEDIA_ROOT - personal data
└── .env                      environment file, mode 0600, read by docker compose
```
{%- endif %}

Rules that are not negotiable:

- `.env` is mode `0600`, owned by the application account. It contains the database password, the
  mail password and `SECRET_KEY`. A world-readable `.env` is a credential disclosure.
- `private-media/` is **never** mapped to a URL by the reverse proxy. It is served only through the
  application's permission-checked private-media view at `/private-media/<path>`. TODO: after the
  first deploy, confirm by requesting a known private file's on-disk path directly through the web
  server and getting a 404.
- `media/` is served by the reverse proxy but must not execute anything. Deny script handlers for
  that location.
- `staticfiles/` is generated, never edited on the server, and never committed.

## Outbound network access the application needs

| Destination | Port | Why | Blocked means |
|---|---|---|---|
| SMTP relay (TODO: host) | 587 (TLS) | All outgoing mail | Mail queues, forms appear to succeed but nothing arrives |
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
- Serve `/static/` from `staticfiles/` and `/media/` from `media/`, and serve **nothing** from
  `private-media/`.
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
- [ ] A file uploaded through the admin appears at the expected path with the expected ownership.
- [ ] A private-media file is unreachable except through the permission-checked view.
- [ ] A backup has run and a restore has been performed onto a second machine
      ([08-backup-restore.md](08-backup-restore.md)).
- [ ] Every alert in [09-monitoring.md](09-monitoring.md) has been fired deliberately once and
      arrived.
