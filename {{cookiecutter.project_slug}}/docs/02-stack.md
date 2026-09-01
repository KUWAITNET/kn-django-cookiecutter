# 2. Technology stack and versions

**The authoritative list of every package and its exact resolved version is `uv.lock` in the
repository root.** This page is not that list and must never become a stale copy of it. It records
the platform versions a system administrator needs to know, and each one's vendor support end date —
the date that decides when an upgrade is planned rather than improvised.

To see exactly what is installed:

```bash
uv tree                 # dependency graph, resolved versions
uv pip list             # flat inventory
uv run python -c "import django; print(django.get_version())"
```

## Platform versions

| Component | Version in use | Vendor support until | Notes |
|---|---|---|---|
| Python | {{ cookiecutter.python_version }} | {% if cookiecutter.python_version == '3.14' %}October 2030{% else %}October 2029{% endif %} (security support) | Pinned in `.python-version` and `requires-python` |
{%- if cookiecutter.django_version == '6.1' %}
| Django | 6.1 | December 2027 | Current release, not LTS. Chosen so the move to the 6.2 LTS in April 2027 is a single step rather than a jump across two release cycles. `django>=6.1,<6.2` |
{%- else %}
| Django | 5.2 LTS | April 2028 | Long-term support release. `django>=5.2,<5.3` |
{%- endif %}
{%- if cookiecutter.stack == "wagtail" %}
| Wagtail (content management system) | 7.4 LTS | November 2027 | Long-term support release. `wagtail>=7.4,<7.5` |
{%- endif %}
| PostgreSQL | 17 | November 2029 | The only supported database for this project |
{%- if cookiecutter.cache == "redis" %}
| Redis | 7 | TODO: confirm with the hosting provider | Cache, rate-limit and throttle counters |
{%- endif %}
{%- if cookiecutter.deploy_target == "gunicorn_nginx" %}
| Web server | nginx | TODO: | TLS termination, static files, request limits |
{%- else %}
| Container runtime | Docker Engine + Compose v2 | TODO: | See [07-deployment.md](07-deployment.md) |
{%- endif %}
| Application server | gunicorn 23.x | — | WSGI, 3 workers by default |
| Operating system | TODO: e.g. Ubuntu 24.04 LTS | TODO: | See [03-infrastructure.md](03-infrastructure.md) |
| Node.js | Not used | — | There is no JavaScript build step; no Node at runtime or build time |

The two dates that matter most are Django's and{% if cookiecutter.stack == "wagtail" %} the content management system's{% else %} Python's{% endif %}. Put them in a calendar. An upgrade planned six
months out is a sprint; the same upgrade started after support ends is an incident.

## Why LTS releases

{% if cookiecutter.django_version == '6.1' %}Django is pinned to one minor release, and{% if cookiecutter.stack == "wagtail" %} Wagtail to its long-term support line,{% endif %} with a narrow upper bound{% else %}Both Django and{% if cookiecutter.stack == "wagtail" %} Wagtail{% else %} the supporting libraries{% endif %} are pinned to long-term support releases with a narrow upper bound{% endif %}
(`<5.3`{% if cookiecutter.stack == "wagtail" %}, `<7.5`{% endif %}). A minor release is picked up by `uv lock --upgrade`; a feature release is a
deliberate, tested, scheduled piece of work. This is recorded as a decision in
[14-decisions.md](14-decisions.md); do not widen the bound to make an unrelated dependency resolve.

## Application dependencies and what each one is for

Every entry below is a runtime dependency declared in `pyproject.toml`. Nothing here is optional
decoration; each has a job.

| Package | Job |
|---|---|
| `django` | The framework |
{%- if cookiecutter.stack == "wagtail" %}
| `wagtail` | Content management: page tree, revisions, editor interface, search |
{%- endif %}
| `psycopg[binary]` | PostgreSQL driver |
| `django-environ` | Reads configuration from the environment (12-factor) |
| `Pillow` | Image handling and server-side re-encoding of uploads |
| `gunicorn` | WSGI application server |
| `whitenoise` | Serves hashed static files from the application process |
| `django-unfold` | Administration interface skin — the KUWAITNET standard wherever `django.contrib.admin` is mounted |
| `django-csp` | Content-Security-Policy with a per-request nonce |
| `django-permissions-policy` | `Permissions-Policy` response header |
| `argon2-cffi` | Argon2 password hashing |
| `python-magic` | Content sniffing on uploads: the real file type must match the extension |
{%- if cookiecutter.use_2fa == "yes" %}
| `django-otp` | Time-based one-time passwords for administrator accounts |
{%- if cookiecutter.stack == "wagtail" %}
| `wagtail-2fa` | Enforces the second factor on the content management system's admin |
{%- endif %}
{%- endif %}
{%- if cookiecutter.rate_limiting == "yes" %}
| `django-axes` | Login lockout with an auditable record |
{%- if cookiecutter.frontend != "api_only" %}
| `django-ratelimit` | Rate caps on public non-DRF POST endpoints |
{%- endif %}
{%- endif %}
{%- if cookiecutter.spam_protection == "turnstile_honeypot" %}
| `requests` | Server-side verification of the Turnstile token |
{%- endif %}
| `django-post-office` | Wraps the real mail transport so every send is logged and auditable |
{%- if cookiecutter.countries_app == "cities" %}
| `django-cities-light` | Country, region and city reference data, imported from GeoNames into `apps/cities` |
{%- elif cookiecutter.countries_app == "django_countries" %}
| `django-countries` (**KUWAITNET fork**) | The country list and the country field. Installed from `git+https://github.com/KUWAITNET/django-countries.git@main`, **not from PyPI** — see [14-decisions.md](14-decisions.md) |
{%- endif %}
{%- if cookiecutter.countries_app != "none" or cookiecutter.forms_suite == "yes" %}
| `django-phonenumber-field[phonenumbers]` | Validated, normalised telephone numbers{% if cookiecutter.countries_app == "django_countries" %}, and the source of the dial codes offered on public forms{% endif %} |
{%- endif %}
{%- if cookiecutter.languages == "en_ar" %}
{%- if cookiecutter.stack == "wagtail" %}
| `wagtail-modeltranslation` | Per-field translation: one content tree, translated columns |
{%- else %}
| `django-modeltranslation` | Per-field translation: translated columns on the same row |
{%- endif %}
{%- endif %}
{%- if cookiecutter.api != "none" %}
| `djangorestframework` | The HTTP interface |
| `djangorestframework-simplejwt` | Access tokens and rotating refresh tokens for external clients |
| `drf-spectacular` | OpenAPI schema and the documentation UI |
| `django-cors-headers` | Explicit cross-origin allow-list for `/api/` |
| `django-filter` | Query filtering on list endpoints |
{%- endif %}
{%- if cookiecutter.cache == "redis" %}
| `redis` | Client for the shared cache |
{%- endif %}
{%- if cookiecutter.sentry == "yes" %}
| `sentry-sdk[django]` | Error monitoring, active only when `SENTRY_DSN` is set |
{%- endif %}

Development-only tooling (`[dependency-groups] dev`): `ruff` (lint and format, including the
flake8-bandit security rules), `pytest` + `pytest-django` + `pytest-cov`, `factory-boy`,
`django-debug-toolbar`, `bandit`, `pre-commit`, `pip-audit`. None of these are installed in a
production image (`uv sync --no-dev`).

## Reproducing the exact dependency set

```bash
uv sync --frozen          # install exactly what uv.lock pins; never re-resolve
```

`uv.lock` is committed. A deploy that does not use `--frozen` is a deploy that installed something
nobody tested.

To upgrade deliberately:

```bash
uv lock --upgrade-package django   # one package
uv lock --upgrade                  # everything within the declared bounds
uv sync
make test lint
uv run pip-audit
```

Commit the changed `uv.lock` with the reason in the commit message, and run the full gate set
before merging.

## Vulnerability audit

```bash
make audit          # uv run pip-audit — fails on a known-vulnerable dependency
```

This runs on every CI build, so a newly published advisory against a pinned package fails the next
build even when nothing in the repository changed. TODO: record the agreed cadence for running it
against production between releases, and who acts on a finding.

## System packages the application needs at runtime

| Package | Needed by |
|---|---|
| `libmagic1` | `python-magic` upload content sniffing — **without it, upload validation cannot verify file types** |
{%- if cookiecutter.languages == "en_ar" %}
| `gettext` | Compiling translation catalogues at deploy time |
{%- endif %}
| PostgreSQL client libraries | Provided by `psycopg[binary]`; a separate `libpq` is not required |

See [03-infrastructure.md](03-infrastructure.md) for the full server package list.
