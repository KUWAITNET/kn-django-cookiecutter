# syntax=docker/dockerfile:1
#
# Multi-stage uv build. Dependencies are installed in a builder stage and the
# resolved virtualenv is copied into a slim runtime image.
#
# Deliberately NOT done here: running migrations. Migrations are a deploy step,
# not a container start step - two containers starting at once would race, and a
# failed migration must stop a deploy rather than crash-loop a container.

# --- Builder ------------------------------------------------------------------
FROM python:{{ cookiecutter.python_version }}-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
{% if cookiecutter.task_queue == "celery" and cookiecutter.task_broker == "sqs" %}
# celery[sqs] depends on pycurl, a C extension with no wheel for this platform: it
# is compiled here, against libcurl and OpenSSL. Without these three packages the
# build fails inside 'uv sync' with a compiler error about missing curl headers,
# which reads like a broken lockfile and is not. The runtime stage does NOT need
# them - only the shared libraries, which come in with curl below.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libcurl4-openssl-dev \
        libssl-dev \
    && rm -rf /var/lib/apt/lists/*
{% endif %}
WORKDIR /app

# Install dependencies first so the layer is cached until the lockfile changes.
# --frozen: install exactly what the lockfile pins, never re-resolve.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# --- Runtime ------------------------------------------------------------------
FROM python:{{ cookiecutter.python_version }}-slim AS runtime

# libmagic1: content-type sniffing for upload validation (python-magic).
# gettext:   compilemessages at build time, so .mo files are never trusted from git.
{%- if cookiecutter.task_queue == "celery" and cookiecutter.task_broker == "sqs" %}
# curl:      the HEALTHCHECK below, and it brings in the libcurl that the compiled
#            pycurl (celery[sqs]) loads at runtime. Removing curl breaks the worker.
{%- else %}
# curl:      the HEALTHCHECK below.
{%- endif %}
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libmagic1 \
        gettext \
        curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE={{ cookiecutter.project_slug }}.settings.production

WORKDIR /app

COPY --from=builder --chown=app:app /app /app
{% if cookiecutter.static_storage == "cloud" %}
# collectstatic is NOT run here: static files go to the bucket, and the build has
# no cloud credentials (and must not be given any - they would end up in a layer).
# It runs as a deploy step instead; see docs/07-deployment.md.
{%- if cookiecutter.asset_pipeline == "compressor" %}
# "manage.py compress --force" is part of that same deploy step, after collectstatic.
{%- endif %}
{%- if cookiecutter.languages == "en_ar" %}
RUN SECRET_KEY=build-only-not-a-secret \
    ALLOWED_HOSTS=localhost \
    python manage.py compilemessages --ignore=.venv
{%- endif %}
{%- else %}
# Static and translations are built with the PRODUCTION settings module, so the
# manifest matches what runs. Placeholder secrets are build-time only: they are
# never baked into the image because settings read them at boot.
{%- if cookiecutter.asset_pipeline == "compressor" %}
#
# The compress step runs AFTER collectstatic, and it is not optional: production
# has COMPRESS_OFFLINE on, so a page whose block was never compiled raises rather
# than rendering. Skipping it ships a site with no CSS.
{%- endif %}
RUN SECRET_KEY=build-only-not-a-secret \
    ALLOWED_HOSTS=localhost \
    python manage.py collectstatic --noinput --clear \
{%- if cookiecutter.asset_pipeline == "compressor" %}
    && SECRET_KEY=build-only-not-a-secret ALLOWED_HOSTS=localhost \
       python manage.py compress --force \
{%- endif %}
{%- if cookiecutter.languages == "en_ar" %}
    && SECRET_KEY=build-only-not-a-secret ALLOWED_HOSTS=localhost \
       python manage.py compilemessages --ignore=.venv \
{%- endif %}
    && chown -R app:app /app/staticfiles
{%- endif %}

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

CMD ["gunicorn", "{{ cookiecutter.project_slug }}.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
