# 1. System overview and architecture

## What this system is

{{ cookiecutter.description }}

It is built for {{ cookiecutter.client_name }}. Production domain: `{{ cookiecutter.domain_name }}`.

{% if cookiecutter.stack == "wagtail" -%}
The site is a content-managed website. Editors sign in to a content management system and build
pages from a fixed set of page types and content blocks; nothing on the public site requires a
developer to change routine content.
{%- else -%}
{%- if cookiecutter.frontend == "api_only" -%}
The system is an application backend. It exposes an HTTP interface to other systems and has no
public HTML site of its own; the administrative interface is the only browser-facing surface.
{%- else -%}
The system is a server-rendered Django application. Pages are rendered from Django templates and
editorial data is maintained through the administration interface.
{%- endif -%}
{%- endif %}

TODO: describe the audiences in one paragraph each — who visits the public site, who administers
it, and which external systems depend on it. Write it so a technical manager can follow it without
the codebase open.

{% if cookiecutter.languages == "en_ar" -%}
The site is bilingual: English and Arabic. Both languages are first-class — English is served under
`/en/` and Arabic under `/ar/`, so neither language is privileged and search engines see symmetric
alternates. Arabic pages render right-to-left.
{%- else -%}
The site is English-only. Adding a second language later is a structural change, not a content
change: see [14-decisions.md](14-decisions.md).
{%- endif %}

## How a request travels

```text
  Internet
     |
     v
  [ TLS / HTTP front ]{% if cookiecutter.deploy_target == "gunicorn_nginx" %}  nginx{% else %}  reverse proxy{% endif %}
     |                 TLS termination, request size limits, access log,
     |                 static and public media, X-Forwarded-Proto
     v
  [ gunicorn ]         WSGI, 3 workers by default
     |
     v
  [ Django application ]   package: {{ cookiecutter.project_slug }}
     |                     middleware chain, in order:
     |                       security headers -> WhiteNoise static -> sessions
{%- if cookiecutter.languages == "en_ar" %}
     |                       -> locale
{%- endif %}
     |                       -> CSRF -> authentication
{%- if cookiecutter.use_2fa == "yes" %}
     |                       -> one-time-password verification
{%- endif %}
     |                       -> CSP + permissions policy
{%- if cookiecutter.rate_limiting == "yes" %}
     |                       -> login lockout
{%- endif %}
     |
     +--> PostgreSQL          content, users, sessions, e-mail log
{%- if cookiecutter.cache == "redis" %}
     +--> Redis               cache, rate-limit{% if cookiecutter.api != "none" %} and throttle{% endif %} counters
{%- else %}
     +--> in-process cache    development only; per worker, not shared
{%- endif %}
{%- if cookiecutter.media_storage == "filesystem" %}
     +--> filesystem          MEDIA_ROOT (public) and PRIVATE_MEDIA_ROOT (personal data)
{%- elif cookiecutter.media_storage == "s3" %}
     +--> S3                  media/ prefix (public) and private/ prefix (personal data)
{%- elif cookiecutter.media_storage == "gcs" %}
     +--> Cloud Storage       media/ prefix (public) and private/ prefix (personal data)
{%- else %}
     +--> Blob Storage        media/ prefix (public) and private/ prefix (personal data)
{%- endif %}
     +--> SMTP relay          all outgoing mail, every send logged
```

External services the application talks to:

| Service | Used for | Fails how | Owner |
|---|---|---|---|
| SMTP relay | All outgoing mail | The failure is recorded in the e-mail log with its reason, so a missing message can be distinguished from a message never attempted | TODO: |
{%- if cookiecutter.spam_protection == "turnstile_honeypot" %}
| Cloudflare Turnstile | Bot protection on public forms | Degrades to honeypot-only when no key is configured | TODO: |
{%- endif %}
{%- if cookiecutter.sentry == "yes" %}
| Sentry | Error monitoring | Fully disabled when `SENTRY_DSN` is unset; no network calls | TODO: |
{%- endif %}
{%- if cookiecutter.analytics == "ga4_gtm" %}
| Google Analytics 4 / Tag Manager | Traffic measurement | Client-side only; no effect on the site if blocked | TODO: |
{%- endif %}
{%- if cookiecutter.countries_app == "cities" %}
| Country/city reference data | Populating the country list (one-off import, not a runtime call) | Import is re-runnable | KUWAITNET |
{%- endif %}

TODO: add any project-specific integration to this table, and register it in the third-party
services register delivered with the project.

## Where the boundary runs

That boundary determines who can fix what.

- **On {{ cookiecutter.client_name }}'s infrastructure:** the web front end, the application, the
  database, the cache, uploaded files, and the backups. TODO: confirm and name the hosting
  provider, account and region.
- **External services:** every row in the table above. When one of them fails, the fix is with the
  provider or with whoever holds the account, not in this repository.

## Components that hold data

| Component | Holds | Personal data? | Backed up |
|---|---|---|---|
| PostgreSQL | All content, users, sessions, e-mail log{% if cookiecutter.newsletter == "yes" %}, newsletter subscribers{% endif %} | Yes | [08](08-backup-restore.md) |
{%- if cookiecutter.media_storage == "filesystem" %}
| `MEDIA_ROOT` | Public uploads (images, documents) | Normally no | [08](08-backup-restore.md) |
| `PRIVATE_MEDIA_ROOT` | Uploads containing personal data | **Yes** | [08](08-backup-restore.md) |
{%- else %}
| Object store, `media/` prefix | Public uploads (images, documents) | Normally no | [08](08-backup-restore.md) — by bucket versioning, not by copying |
| Object store, `private/` prefix | Uploads containing personal data | **Yes** | [08](08-backup-restore.md) — by bucket versioning, not by copying |
{%- endif %}
{%- if cookiecutter.cache == "redis" %}
| Redis | Cache entries, rate-limit counters | No (must never hold personal data) | Not backed up; rebuilt on restart |
{%- endif %}
| Secrets store | `SECRET_KEY`, database and mail credentials | — | [08](08-backup-restore.md) |

Files containing personal data are never served from a public URL. They live {% if cookiecutter.media_storage == "filesystem" %}under
`PRIVATE_MEDIA_ROOT`{% else %}in a separate
private storage, in a store that is not public-read,{% endif %} and are served only through the permission-checked
private-media view mounted at `/private-media/<path>`.

## Environments

| Environment | Address | Purpose | Real data? | Who has access |
|---|---|---|---|---|
| Production | `https://{{ cookiecutter.domain_name }}` | Live site | Yes | TODO: |
| Staging | TODO: `https://staging.{{ cookiecutter.domain_name }}` | Pre-release verification, UAT, security scan | Anonymised copy | TODO: |
| Local | `http://localhost:8000` | Development | No | Developers |

Production is the only environment containing real personal data. A copy of the production database
taken for debugging is a copy of personal data: anonymise it before it leaves production, and delete
it when the investigation ends.

Each environment uses its own settings module and its own secrets:

| Environment | Settings module | `DEBUG` | Secrets from |
|---|---|---|---|
| Local | `{{ cookiecutter.project_slug }}.settings.dev` | `True` | `.env` file, never committed |
| Test / CI | `{{ cookiecutter.project_slug }}.settings.test` | `False` | Fixed non-secret values in the module |
| Staging | `{{ cookiecutter.project_slug }}.settings.production` | `False` | TODO: name the store |
| Production | `{{ cookiecutter.project_slug }}.settings.production` | `False` | TODO: name the store |

Staging and production share one settings module deliberately. A staging environment configured
differently from production tests a system that does not exist.

## What is deliberately not here

- No background worker or task queue. Mail is delivered synchronously through the outgoing mail
  queue, so there is no worker process to keep alive. See [14-decisions.md](14-decisions.md).
{%- if cookiecutter.cache != "redis" %}
- No shared cache. The cache is in-process, which is correct for development and wrong for
  production behind multiple workers. See [14-decisions.md](14-decisions.md).
{%- endif %}
{%- if cookiecutter.api == "none" %}
- No public HTTP interface for other systems. Section 12 of the KUWAITNET documentation skeleton is
  deliberately absent rather than left empty.
{%- endif %}
