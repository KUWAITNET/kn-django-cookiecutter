# 6. Installation from scratch

From an empty machine to a working site. Written so that someone who has never seen this project can
follow it without inference.

**Expected time:** 20 to 30 minutes on a machine that already has PostgreSQL, longer if the database
has to be installed too.

## 1. Prerequisites

| Requirement | Why | Check |
|---|---|---|
| `git` | Obtaining the source | `git --version` |
| `uv` | Python version and dependency management | `uv --version` |
| PostgreSQL 17 server and client | The database | `psql --version` |
| `libmagic` | Upload validation sniffs real file content types | see below |
{%- if cookiecutter.languages == "en_ar" %}
| `gettext` | Compiling translation catalogues | `msgfmt --version` |
{%- endif %}
{%- if cookiecutter.cache == "redis" %}
| Redis 7 | Cache, rate-limit{% if cookiecutter.api != "none" %} and throttle{% endif %} counters | `redis-cli ping` |
{%- endif %}

Python itself does not need to be installed separately: `uv` reads `.python-version` and fetches
Python {{ cookiecutter.python_version }} for you.

```bash
# macOS
brew install uv postgresql@17 libmagic{% if cookiecutter.languages == "en_ar" %} gettext{% endif %}{% if cookiecutter.cache == "redis" %} redis{% endif %}

# Debian / Ubuntu
curl -LsSf https://astral.sh/uv/install.sh | sh
sudo apt-get install -y postgresql-17 postgresql-client-17 libmagic1{% if cookiecutter.languages == "en_ar" %} gettext{% endif %}{% if cookiecutter.cache == "redis" %} redis-server{% endif %}
```

{% if cookiecutter.docker == "yes" -%}
Alternatively, run the supporting services in containers and the application on the host:

```bash
docker compose up -d db{% if cookiecutter.cache == "redis" %} redis{% endif %} mail
```

That gives you PostgreSQL on 5432{% if cookiecutter.cache == "redis" %}, Redis on 6379{% endif %}, and a mail catcher on 1025 with a web interface on
`http://localhost:8025` that catches every outgoing message so nothing reaches a real address.
{%- endif %}

## 2. Get the source

```bash
git clone TODO:<repository-url> {{ cookiecutter.project_slug }}
cd {{ cookiecutter.project_slug }}
```

## 3. Install dependencies

```bash
make setup
```

That runs `uv sync` (creating `.venv` from `uv.lock`), generates migrations for the current model
set, and installs the pre-commit hooks. Every subsequent command is run through `uv run`, so there
is no virtualenv to activate.

## 4. Configure

```bash
cp .env.example .env
```

Then edit `.env`. Every variable is explained in
[04-environment-variables.md](04-environment-variables.md). For a local install the defaults are
usable except:

- `SECRET_KEY` — generate one; never reuse another environment's.
- `DATABASE_URL` — must match the database you are about to create.

```bash
uv run python -c "import secrets; print(secrets.token_urlsafe(50))"
```

## 5. Create the database

```bash
createdb {{ cookiecutter.project_slug }}
```

If your PostgreSQL user is not the default, create the role first and put the matching credentials
in `DATABASE_URL`:

```bash
psql -c "CREATE ROLE {{ cookiecutter.project_slug }} WITH LOGIN PASSWORD 'local-only';"
psql -c "CREATE DATABASE {{ cookiecutter.project_slug }} OWNER {{ cookiecutter.project_slug }};"
```

## 6. Apply migrations

```bash
make migrate
```

## 7. Create an administrator account

```bash
make superuser
```

{% if cookiecutter.use_2fa == "yes" -%}
Administrative accounts require a second factor. On first sign-in you will be asked to enrol an
authenticator application; keep the recovery codes somewhere you can find them, because a lost
device with no recovery codes means the account has to be re-created from the command line.
{%- endif %}

## 8. Load development content

```bash
make seed
```

`seed_content` is idempotent and non-destructive: running it twice produces the same result and it
never deletes anything. It exists so that a fresh checkout has a site to look at, and so the test
suite runs against a realistic content set rather than an empty database.

**Never run it against production.** It is for development and test databases.

{% if cookiecutter.countries_app == "cities" -%}
The country and city reference data is imported separately and takes a few minutes:

```bash
uv run python manage.py cities_light
```
{%- endif %}

{% if cookiecutter.languages == "en_ar" -%}
## 9. Compile translations

```bash
make compile
```

`.mo` files are build artefacts and are not committed. Without this step the site runs, but every
Arabic string falls back to English — which looks like a translation bug and is not one.

## 10. Run it
{%- else -%}
## 9. Run it
{%- endif %}

```bash
make run
```

| Address | What |
|---|---|
{%- if cookiecutter.frontend != "api_only" %}
{%- if cookiecutter.languages == "en_ar" %}
| `http://localhost:8000/en/` | The site in English |
| `http://localhost:8000/ar/` | The site in Arabic, right to left |
{%- else %}
| `http://localhost:8000/` | The site |
{%- endif %}
{%- endif %}
| `http://localhost:8000/{{ cookiecutter.admin_url_prefix }}/` | Administration |
{%- if cookiecutter.stack == "wagtail" %}
| `http://localhost:8000/{{ cookiecutter.admin_url_prefix }}/django/` | The Django admin, for models with no editor interface |
{%- endif %}
{%- if cookiecutter.api != "none" %}
| `http://localhost:8000/api/v1/` | The API root |
| `http://localhost:8000/api/schema/swagger-ui/` | Interactive API documentation (development and staging only) |
{%- endif %}
| `http://localhost:8000/healthz` | Health check; returns 200 and touches the database |

## Verify the installation

```bash
make check            # Django system checks
make test             # the test suite
make lint             # ruff, including the security rules
make check-deploy     # production configuration checks; must report zero issues
```

All four must pass on a correct installation. `make check-deploy` runs against the production
settings module deliberately: it is the same gate CI applies, and it is the fastest way to discover
that a production-only setting is broken.

## The mistakes people actually make

| Symptom | Cause | Fix |
|---|---|---|
| `ImportError: failed to find libmagic` | `libmagic` is not installed | Install it. Upload validation cannot verify file types without it, so this is not optional |
| `FATAL: database "{{ cookiecutter.project_slug }}" does not exist` | Step 5 skipped, or `DATABASE_URL` names a different database | `createdb`, or fix `DATABASE_URL` |
| Site loads but every page is unstyled | `make run` serves static files from the app; a stale `staticfiles/` from a `collectstatic` run confuses it | `rm -rf staticfiles` and re-run |
{%- if cookiecutter.languages == "en_ar" %}
| Arabic pages show English text | Translations not compiled | `make compile` |
{%- endif %}
| Tests fail with a database error | The test database was created before a migration and reused | `uv run pytest --create-db` |
| Everything works, then a form submission fails silently | The mail transport is unconfigured and the console backend swallowed the message | Check the terminal output, or point `DEV_EMAIL_BACKEND` at a local catcher |
| `make setup` fails on `uv sync` | No network, or a private package index needs credentials | Fix the network, then re-run `make setup` |

## Building a server instead of a workstation

The steps above build a development machine. A production server additionally needs the sizing,
packages, ports, accounts and filesystem layout in [03-infrastructure.md](03-infrastructure.md), and
is released to using the runbook in [07-deployment.md](07-deployment.md) — not by running
`make run`.
