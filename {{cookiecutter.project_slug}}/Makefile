# {{ cookiecutter.project_name }} - developer and deploy commands.
# Make is used rather than just: it is present on every server and CI image, so
# the deploy runbook's commands work over SSH with nothing to install.

.DEFAULT_GOAL := help
.PHONY: help setup run migrate migrations superuser test test-ci lint format check \
        check-deploy check-migrations security audit messages compile static seed \
        shell clean schema schema-check

help:  ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup:  ## Install dependencies, create migrations, install git hooks
	uv sync
	uv run python manage.py makemigrations
	uv run pre-commit install

run:  ## Run the development server
	uv run python manage.py runserver

migrations:  ## Create migrations for model changes
	uv run python manage.py makemigrations

migrate:  ## Apply migrations
	uv run python manage.py migrate

superuser:  ## Create an administrator account
	uv run python manage.py createsuperuser

seed:  ## Populate the database with development content
	uv run python manage.py seed_content

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
static:  ## Collect static files
	uv run python manage.py collectstatic --noinput
{% if cookiecutter.api != "none" %}
schema:  ## Write the OpenAPI schema to disk
	uv run python manage.py spectacular --file schema.yml --validate

schema-check:  ## Fail when the committed schema no longer matches the code
	uv run python manage.py spectacular --file /tmp/schema.yml --validate
	diff -u schema.yml /tmp/schema.yml
{% endif %}
clean:  ## Remove caches and build artefacts
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage coverage.xml
