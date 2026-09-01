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

# Static and translations are built with the PRODUCTION settings module, so the
# manifest matches what runs. Placeholder secrets are build-time only: they are
# never baked into the image because settings read them at boot.
RUN SECRET_KEY=build-only-not-a-secret \
    ALLOWED_HOSTS=localhost \
    python manage.py collectstatic --noinput --clear \
{%- if cookiecutter.languages == "en_ar" %}
    && SECRET_KEY=build-only-not-a-secret ALLOWED_HOSTS=localhost \
       python manage.py compilemessages --ignore=.venv \
{%- endif %}
    && chown -R app:app /app/staticfiles

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
