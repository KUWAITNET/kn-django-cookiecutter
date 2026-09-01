# {{ cookiecutter.project_name }} - developer and deploy commands.
# Make is used rather than just: it is present on every server and CI image, so
# the deploy runbook's commands work over SSH with nothing to install.

.DEFAULT_GOAL := help
.PHONY: help setup run migrate migrations superuser test test-ci lint format check \
        check-deploy check-migrations security audit messages compile static seed \
        shell clean schema schema-check worker beat monitor

help:  ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup:  ## Install dependencies, create migrations, install git hooks
	uv sync
	uv run python manage.py makemigrations
	uv run pre-commit install

run:  ## Run the development server
	uv run python manage.py runserver
{%- if cookiecutter.task_queue == "huey" %}

# The consumer runs the schedule as well as the queue, so this one process is the
# whole background story. Tasks run inline while DEBUG is on, so set HUEY_IMMEDIATE=False
# in .env before starting this, or it will sit there with nothing to do.
worker:  ## Run the task consumer (queue + periodic schedule)
	uv run python manage.py run_huey

beat:  ## The schedule is part of the consumer - run 'make worker'
	@echo "No separate scheduler: 'make worker' runs the periodic tasks too."
{%- elif cookiecutter.task_queue == "celery" %}

# Two processes, and both must be running. Set CELERY_TASK_ALWAYS_EAGER=False in
# .env first, or tasks run inline in the web process and the worker sees nothing.
worker:  ## Run a Celery worker
	uv run celery -A {{ cookiecutter.project_slug }} worker --loglevel=INFO --concurrency=2

# Exactly one beat process, ever. Two schedulers means every periodic task fires twice.
beat:  ## Run the Celery scheduler (periodic tasks)
	uv run celery -A {{ cookiecutter.project_slug }} beat --loglevel=INFO
{%- if cookiecutter.task_broker != "sqs" %}

monitor:  ## Flower, the Celery monitoring UI, on http://localhost:5555
	uv run celery -A {{ cookiecutter.project_slug }} flower --port=5555
{%- else %}

monitor:  ## Not available on SQS - see docs/09-monitoring.md
	@echo "SQS carries no Celery events or remote control, so Flower has nothing to read."
	@echo "Monitor the queue in CloudWatch and the worker through its logs instead."
{%- endif %}
{%- endif %}

migrations:  ## Create migrations for model changes
	uv run python manage.py makemigrations

migrate:  ## Apply migrations
	uv run python manage.py migrate

superuser:  ## Create an administrator account
	uv run python manage.py createsuperuser

seed:  ## Populate the database with development content
	uv run python manage.py seed_content
{% if cookiecutter.notifications_app == "yes" %}	uv run python manage.py seed_notifications
{% endif %}
shell:  ## Django shell
	uv run python manage.py shell

test:  ## Run the test suite (fast: no coverage)
	uv run pytest

test-ci:  ## Run the test suite with the coverage gate (60% on apps/)
	uv run pytest --cov=apps --cov-report=term-missing --cov-report=xml --cov-fail-under=60

lint:  ## Lint (includes the flake8-bandit security rules)
	uv run ruff check .

format:  ## Format the codebase
	uv run ruff format .
	uv run ruff check --fix .

check:  ## Django system checks
	uv run python manage.py check

check-deploy:  ## Production deployment checks - must report zero issues before go-live
	DJANGO_SETTINGS_MODULE={{ cookiecutter.project_slug }}.settings.production \
		uv run python manage.py check --deploy

check-migrations:  ## Fail if a model change has no migration
	uv run python manage.py makemigrations --check --dry-run

security:  ## Static security analysis
	uv run bandit -c pyproject.toml -r apps {{ cookiecutter.project_slug }}

audit:  ## Check dependencies for known vulnerabilities
	uv run pip-audit
{% if cookiecutter.languages == "en_ar" %}
messages:  ## Extract translatable strings
	uv run python manage.py makemessages -l ar --ignore=.venv
{%- if cookiecutter.frontend != "api_only" %}
	uv run python manage.py makemessages -l ar -d djangojs --ignore=.venv --ignore=static/vendor
{%- endif %}

compile:  ## Compile translations (.mo files are NOT committed; build them here)
	uv run python manage.py compilemessages --ignore=.venv
{% endif %}
{% if cookiecutter.asset_pipeline == "compressor" -%}
# Production has COMPRESS_OFFLINE on, so a block that was never compiled raises
# rather than rendering. Both steps live in one target, in order, so that no
# deploy path can pick up the first without the second.
static:  ## Collect static files, then compile the compress blocks
	uv run python manage.py collectstatic --noinput
	uv run python manage.py compress --force
{%- else -%}
static:  ## Collect static files
	uv run python manage.py collectstatic --noinput
{%- endif %}
{% if cookiecutter.api != "none" %}
schema:  ## Write the OpenAPI schema to disk
	uv run python manage.py spectacular --file schema.yml --validate --fail-on-warn

schema-check:  ## Fail when the committed schema no longer matches the code
	uv run python manage.py spectacular --file /tmp/schema.yml --validate --fail-on-warn
	diff -u schema.yml /tmp/schema.yml
{% endif %}
clean:  ## Remove caches and build artefacts
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage coverage.xml
