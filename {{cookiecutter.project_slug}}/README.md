# {{ cookiecutter.project_name }}

{{ cookiecutter.description }}

Built for {{ cookiecutter.client_name }} by {{ cookiecutter.author }}. Production domain:
`{{ cookiecutter.domain_name }}`.

This README is how you run, test and deploy the project. The full technical documentation is in
[`docs/`](docs/) — start with [`docs/README.md`](docs/README.md).

## Stack

| | |
|---|---|
| Python | {{ cookiecutter.python_version }}, managed by `uv` |
| Framework | Django 5.2 LTS |
{%- if cookiecutter.stack == "wagtail" %}
| Content management | Wagtail 7.4 LTS |
{%- endif %}
| Database | PostgreSQL 17 |
| Cache | {% if cookiecutter.cache == "redis" %}Redis 7{% else %}Local memory (development only — see `docs/14-decisions.md`){% endif %} |
| Admin skin | django-unfold |
{%- if cookiecutter.languages == "en_ar" %}
| Languages | English and Arabic, both URL-prefixed, RTL supported |
{%- else %}
| Languages | English |
{%- endif %}
{%- if cookiecutter.api != "none" %}
| API | Django REST Framework at `/api/v1/`, OpenAPI schema, JWT, RFC 9457 errors{% if cookiecutter.api == "headless" %}, plus the content API at `/api/v2/`{% endif %} |
{%- endif %}
| Mail | django-post-office wrapping the real transport; every send is logged |
| Application server | gunicorn{% if cookiecutter.deploy_target == "gunicorn_nginx" %} behind nginx{% else %}, in a container{% endif %} |
| Lint and format | ruff (including the flake8-bandit security rules) |
| Tests | pytest + pytest-django against PostgreSQL, 60 % coverage floor on `apps/` |

Exact versions of everything: `uv.lock`. Platform support dates: [`docs/02-stack.md`](docs/02-stack.md).

## Quick start

Prerequisites: `git`, `uv`, PostgreSQL 17{% if cookiecutter.cache == "redis" %}, Redis 7{% endif %}, `libmagic`{% if cookiecutter.languages == "en_ar" %}, `gettext`{% endif %}.

```bash
make setup                    # uv sync, generate migrations, install git hooks
cp .env.example .env          # then set SECRET_KEY and DATABASE_URL
createdb {{ cookiecutter.project_slug }}
make migrate
make superuser
make seed                     # development content; idempotent and non-destructive
{%- if cookiecutter.languages == "en_ar" %}
make compile                  # translations; .mo files are not committed
{%- endif %}
make run
```

{% if cookiecutter.docker == "yes" -%}
Supporting services can run in containers while the application runs on the host:

```bash
docker compose up -d db{% if cookiecutter.cache == "redis" %} redis{% endif %} mail
```

The mail catcher's web interface is at `http://localhost:8025`; nothing reaches a real address in
development.
{%- endif %}

| Address | What |
|---|---|
{%- if cookiecutter.frontend != "api_only" %}
{%- if cookiecutter.languages == "en_ar" %}
| `http://localhost:8000/en/` | The site in English |
| `http://localhost:8000/ar/` | The site in Arabic |
{%- else %}
| `http://localhost:8000/` | The site |
{%- endif %}
{%- endif %}
| `http://localhost:8000/{{ cookiecutter.admin_url_prefix }}/` | Administration |
{%- if cookiecutter.stack == "wagtail" %}
| `http://localhost:8000/{{ cookiecutter.admin_url_prefix }}/django/` | The Django admin, for models with no editor interface |
{%- endif %}
{%- if cookiecutter.api != "none" %}
| `http://localhost:8000/api/v1/` | The API |
{%- endif %}
| `http://localhost:8000/healthz` | Health check; touches the database |

Full installation instructions, including the mistakes people actually make:
[`docs/06-installation.md`](docs/06-installation.md).

## Commands

Everything is a `make` target. `make` with no argument lists them.

| Target | Does |
|---|---|
| `setup` | `uv sync`, generate migrations, install the pre-commit hooks |
| `run` | Development server |
| `migrations` | Create migrations for model changes |
| `migrate` | Apply migrations |
| `check-migrations` | Fail if a model change has no migration (CI runs this) |
| `superuser` | Create an administrator account |
| `seed` | Populate the database with development content |
| `shell` | Django shell |
| `test` | Test suite, fast, no coverage |
| `test-ci` | Test suite with the coverage gate (60 % on `apps/`) |
| `lint` | ruff, including the security rules |
| `format` | ruff-format, then ruff `--fix` |
| `check` | Django system checks |
| `check-deploy` | Production configuration checks — **must report zero issues before go-live** |
| `security` | bandit static security analysis |
| `audit` | `pip-audit` — fails on a known-vulnerable dependency |
{%- if cookiecutter.languages == "en_ar" %}
| `messages` | Extract translatable strings into the Arabic catalogue |
| `compile` | Compile translations (`.mo` files are build artefacts, not committed) |
{%- endif %}
| `static` | `collectstatic` |
{%- if cookiecutter.api != "none" %}
| `schema` | Write and validate the OpenAPI schema |
| `schema-check` | Fail when the committed schema no longer matches the code |
{%- endif %}
| `clean` | Remove caches and build artefacts |

### Management commands

| Command | Arguments | What it does |
|---|---|---|
| `seed_content` | — | Idempotent, non-destructive development seed. **Never run against production** |
{%- if cookiecutter.stack == "wagtail" %}
| `publish_scheduled` | — | Publishes and expires pages at their set times; runs on cron |
{%- endif %}
{%- if cookiecutter.countries_app == "cities" %}
| `cities_light` | — | One-off import of country and city reference data. **The country list is empty until this has run** |
{%- endif %}

TODO: add every project-specific management command here, with the arguments an operator needs.
Scheduled ones also belong in [`docs/13-scheduled-tasks.md`](docs/13-scheduled-tasks.md).

## Layout

```text
apps/                       every first-party app; a Django app never sits at the repo root
  core/                     shared, project-wide code: validators, storage, context, views
{%- if cookiecutter.countries_app == "cities" %}
  cities/                   country and city reference data (apps/core/countries.py is the contract)
{%- endif %}
{%- if cookiecutter.notifications_app == "yes" %}
  notifications/            admin-editable e-mail templates and the send log
{%- endif %}
{%- if cookiecutter.stack == "wagtail" %}
  home/                     the home page type
  navigation/               menus and navigation settings
{%- if cookiecutter.frontend != "api_only" %}
  search/                   site search
{%- endif %}
{%- endif %}
{%- if cookiecutter.forms_suite == "yes" %}
  contact/                  the example public form
{%- endif %}
{%- if cookiecutter.newsletter == "yes" %}
  newsletter/               subscribers and sending
{%- endif %}
{%- if cookiecutter.api != "none" %}
  api/                      the HTTP interface
{%- endif %}
{{ cookiecutter.project_slug }}/
  settings/                 base.py, dev.py, production.py, test.py
{%- if cookiecutter.languages == "en_ar" %}
  locale/                   the one message catalogue for the project
{%- endif %}
{%- if cookiecutter.frontend != "api_only" %}
  static/                   the theme
  templates/                the shell and anything not owned by one app
{%- endif %}
  urls.py
docs/                       the technical documentation
Makefile
pyproject.toml
uv.lock                     the authoritative dependency list; committed
```

Settings: `dev.py`, `production.py` and `test.py` each import from `base.py` and override.
`manage.py` defaults to `dev`; `wsgi.py` has **no** default, so a production process started without
`DJANGO_SETTINGS_MODULE` fails rather than silently running development settings.

## Documentation

| File | Contents |
|---|---|
| [`docs/README.md`](docs/README.md) | Index and reading order |
| [`docs/01-overview.md`](docs/01-overview.md) | Architecture and environments |
| [`docs/04-environment-variables.md`](docs/04-environment-variables.md) | Every configuration value |
| [`docs/06-installation.md`](docs/06-installation.md) | Empty machine to running site |
| [`docs/07-deployment.md`](docs/07-deployment.md) | The release runbook and rollback |
| [`docs/08-backup-restore.md`](docs/08-backup-restore.md) | Backup schedule and a tested restore |
| [`docs/14-decisions.md`](docs/14-decisions.md) | Why the system is the way it is |
| [`docs/15-developer-handover.md`](docs/15-developer-handover.md) | Onboarding the next developer |
| [`docs/security-pass.md`](docs/security-pass.md) | The signed pre-go-live security record |

Anything still marked `TODO:` is unfinished:

```bash
grep -rn "TODO:" docs/
```

## Standards this project follows

Generated from the KUWAITNET project template, which implements the KUWAITNET web standards:
project structure, security baseline, testing and QA, environments and releases, monitoring and
logging, backup and disaster recovery{% if cookiecutter.api != "none" %}, the API standard{% endif %}{% if cookiecutter.languages == "en_ar" %}, the internationalisation and RTL standard{% endif %}, the SEO standard and the
performance standard.

Where a standard could be shipped as a default, it was. That turns each rule from "remember to add
this" into "do not remove this".

## Security defaults that must not be silently removed

Every item below is deliberate. Each is explained in
[`docs/14-decisions.md`](docs/14-decisions.md). Removing one is a decision that belongs in a pull
request with a reason, not a quiet edit.

- **Six controls on every upload field**: size limit, extension allowlist (never a denylist),
  content sniffing so the real type must match the extension, server-side image re-encoding bounded
  against decompression bombs with SVG never accepted, a generated stored filename, and
  `PRIVATE_MEDIA_ROOT` for anything containing personal data.
- **Private media is served only through a permission-checked view**, never from `MEDIA_URL`. A
  file's URL is not a credential.
{%- if cookiecutter.spam_protection != "none" %}
- **Spam protection on every public form**{% if cookiecutter.spam_protection == "turnstile_honeypot" %} — Turnstile plus a honeypot, degrading to honeypot-only
  when no key is configured so development, CI and UAT never break. Production without a key is a
  go-live finding{% endif %}.
{%- endif %}
{%- if cookiecutter.rate_limiting == "yes" %}
- **Layered abuse resistance**: login lockout on authentication{% if cookiecutter.frontend != "api_only" %}, rate limits on public non-API
  POST endpoints{% endif %}{% if cookiecutter.api != "none" %}, throttles under `/api/`{% endif %}. Never two of them on one view.
{%- endif %}
{%- if cookiecutter.use_2fa == "yes" %}
- **A second factor on every administrative account**, enforced by the application. Disabled only in
  the test settings.
{%- endif %}
- **A Content-Security-Policy with a per-request nonce**, and no `'unsafe-inline'` or `'unsafe-eval'`
  in `script-src`. A library that needs `eval` is a finding to fix, not a setting to change.
- **The administration interface is not at `/admin/`.** Defence in depth, not a security control —
  but changing it back removes the depth for nothing.
- **`settings/production.py` provides no defaults for secrets.** A misconfigured deploy must fail at
  boot, not run with a development key.
- **No `fields = "__all__"`** on any public form or serializer.
- **Argon2 password hashing** and a 12-character minimum.
- **`.env` is never committed.** A committed `.env` means those credentials are compromised and must
  be rotated.

`make check-deploy` must report zero issues, and
[`docs/security-pass.md`](docs/security-pass.md) must be signed with no open Critical or High
finding, before this project goes live.

## Contributing

- Branch `feature/<ticket>-<slug>`; promotion is `feature/*` → `develop` → `staging` → `main`.
- Conventional commits.
- ruff and ruff-format, line length 100, double quotes.
- Tests for the behaviour added, including at least one failure path. The coverage floor is 60 % on
  `apps/` and is enforced in CI.
- Every fixed bug gets a regression test in the same pull request.
- The full definition of done is in
  [`docs/15-developer-handover.md`](docs/15-developer-handover.md).

If you are an AI coding assistant, read `CLAUDE.md` first.
