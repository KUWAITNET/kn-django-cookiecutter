"""Remove everything the selected options did not ask for, then bootstrap the project.

Two responsibilities:

1. **Prune.** A generated project must contain no dead conditional code and no files for
   features that were not selected. In particular a ``stack=django`` project contains no
   Wagtail dependency, no Wagtail module and no mention of Wagtail anywhere.
2. **Bootstrap.** ``git init``, ``uv sync``, ``makemigrations``, ``pre-commit install`` and
   an initial conventional commit, so the project is runnable immediately.

Bootstrap failures are reported loudly but do not delete the generated project: a missing
network connection should not cost you the generation.
"""

import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path.cwd()

STACK = "{{ cookiecutter.stack }}"
PROJECT_SLUG = "{{ cookiecutter.project_slug }}"
LANGUAGES = "{{ cookiecutter.languages }}"
FRONTEND = "{{ cookiecutter.frontend }}"
MULTISITE = "{{ cookiecutter.multisite }}"
API = "{{ cookiecutter.api }}"
SPAM_PROTECTION = "{{ cookiecutter.spam_protection }}"
RATE_LIMITING = "{{ cookiecutter.rate_limiting }}"
COUNTRIES_APP = "{{ cookiecutter.countries_app }}"
NOTIFICATIONS_APP = "{{ cookiecutter.notifications_app }}"
NEWSLETTER = "{{ cookiecutter.newsletter }}"
NEWSROOM = "{{ cookiecutter.newsroom }}"
FORMS_SUITE = "{{ cookiecutter.forms_suite }}"
ANALYTICS = "{{ cookiecutter.analytics }}"
ASSET_PIPELINE = "{{ cookiecutter.asset_pipeline }}"
TASK_QUEUE = "{{ cookiecutter.task_queue }}"
DOCKER = "{{ cookiecutter.docker }}"
CI = "{{ cookiecutter.ci }}"
BOOTSTRAP = "{{ cookiecutter.bootstrap }}"
USE_2FA = "{{ cookiecutter.use_2fa }}"

IS_WAGTAIL = STACK == "wagtail"
IS_API_ONLY = FRONTEND == "api_only"
HAS_TEMPLATES = not IS_API_ONLY
IS_BILINGUAL = LANGUAGES == "en_ar"

PKG = Path(PROJECT_SLUG)
APPS = Path("apps")

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def remove(*relative_paths: str) -> None:
    """Delete files or directories, ignoring anything already absent."""
    for relative in relative_paths:
        target = PROJECT_ROOT / relative
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        elif target.exists():
            target.unlink()


def prune_empty_dirs(root: Path) -> None:
    """Remove directories left empty by pruning, deepest first."""
    for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir() and path.name != ".git" and not any(path.iterdir()):
            path.rmdir()


# ---------------------------------------------------------------------------
# 1. Prune
# ---------------------------------------------------------------------------

# Stack-specific templates. HTML is never rendered by Jinja (Django and Jinja share
# the same delimiters), so per-stack template differences are handled by shipping
# two directories and merging the right one here.
def merge_template_variant() -> None:
    chosen = PKG / ("templates_wagtail" if IS_WAGTAIL else "templates_django")
    shared = PROJECT_ROOT / PKG / "templates"
    source = PROJECT_ROOT / chosen
    if source.is_dir():
        shared.mkdir(parents=True, exist_ok=True)
        for item in source.iterdir():
            destination = shared / item.name
            if item.is_dir():
                shutil.copytree(item, destination, dirs_exist_ok=True)
            else:
                shutil.copy2(item, destination)
    remove(str(PKG / "templates_wagtail"), str(PKG / "templates_django"))


merge_template_variant()

# Optional applications.
# apps/cities is the reference-data backend only. On the django-countries backend
# the country list comes from the package, and on "none" there is none at all;
# either way this app would be four unused models and a migration to maintain.
# apps/core/countries.py stays in every case - it is the contract the rest of the
# project imports, and it renders a real implementation for all three values.
if COUNTRIES_APP != "cities":
    remove(str(APPS / "cities"))

if NOTIFICATIONS_APP != "yes":
    remove(str(APPS / "notifications"))

if NEWSLETTER != "yes":
    remove(str(APPS / "newsletter"))

if FORMS_SUITE != "yes":
    remove(str(APPS / "contact"))

# The newsroom is Wagtail-only: a routable page serves articles that are models.
if NEWSROOM != "yes" or not IS_WAGTAIL:
    remove(
        str(APPS / "newsroom"),
        str(PKG / "templates" / "blocks" / "latest_articles.html"),
    )

# The background-task app and the Celery application module. With no queue there is
# no worker, so both would be dead code - and docs/13-scheduled-tasks.md already
# documents the cron-only arrangement that replaces them.
if TASK_QUEUE == "none":
    remove(str(APPS / "tasks"))

if TASK_QUEUE != "celery":
    remove(str(PKG / "celery.py"))

if API == "none":
    remove(str(APPS / "api"), "docs/12-api.md")
elif API != "headless":
    # Rendered empty for a non-headless project; delete rather than ship a stub.
    remove(
        str(APPS / "api" / "wagtail_api.py"),
        str(APPS / "api" / "tests" / "test_content_api.py"),
    )

# Stack layer: Wagtail-only modules and templates.
if not IS_WAGTAIL:
    remove(
        str(APPS / "navigation"),
        str(APPS / "home"),
        str(APPS / "search"),
        str(APPS / "core" / "blocks.py"),
        str(APPS / "core" / "panels.py"),
        str(APPS / "core" / "viewsets.py"),
        str(APPS / "core" / "wagtail_hooks.py"),
        str(APPS / "core" / "url_patches.py"),
        str(APPS / "core" / "site_context.py"),
        str(APPS / "core" / "tests" / "test_blocks.py"),
        str(PKG / "static" / "css" / "admin-branding.css"),
        "docs/10-cms-guide.md",
    )
    # Optional apps ship a CMS-admin module that renders empty on this stack. Sweep
    # by name rather than listing each one: the requirement is that the string
    # "wagtail" appears nowhere in a plain-Django project, and a file NAME leaks it
    # just as effectively as file contents - which a contents-only grep will not catch.
    for leftover in PROJECT_ROOT.rglob("*wagtail*"):
        if ".git" not in leftover.parts:
            remove(str(leftover.relative_to(PROJECT_ROOT)))
else:
    # Wagtail projects use the Wagtail page tree and its own translation machinery.
    remove(
        str(APPS / "core" / "sitemaps.py"),
    )

# Multi-site scoping is a Wagtail-only feature.
if MULTISITE != "multi" or not IS_WAGTAIL:
    remove(
        str(APPS / "core" / "site_context.py"),
        str(APPS / "core" / "tests" / "test_site_scoping.py"),
    )

# Bilingual assets. The translation modules and the Arabic search-index patch
# render to empty files on a single-language project.
if not IS_BILINGUAL:
    remove(
        str(PKG / "static" / "css" / "rtl.css"),
        str(PKG / "locale"),
        str(APPS / "core" / "tests" / "test_i18n.py"),
        str(APPS / "core" / "translation.py"),
        str(APPS / "core" / "url_patches.py"),
        str(APPS / "core" / "middleware.py"),
        str(APPS / "navigation" / "translation.py"),
        str(APPS / "home" / "translation.py"),
        str(APPS / "search" / "indexing.py"),
        str(APPS / "cities" / "translation.py"),
        str(APPS / "contact" / "translation.py"),
        str(APPS / "newsroom" / "translation.py"),
    )

# The 2FA screens are only branded when 2FA is actually enabled.
if USE_2FA != "yes":
    remove(str(PKG / "templates" / "wagtail_2fa"))

# The site switcher only exists on a multi-site project.
if MULTISITE != "multi":
    remove(str(APPS / "navigation" / "context_processors.py"))

# apps/core/urls.py only routes the plain-Django home page. A CMS project serves
# "/" from the page tree, and an API-only project serves no HTML at all.
if IS_WAGTAIL or IS_API_ONLY:
    remove(str(APPS / "core" / "urls.py"))

# The contact app is served from the page tree on the CMS stack, so its own
# URLConf is dead there; an API-only project has no HTML form at all.
if IS_WAGTAIL or IS_API_ONLY:
    remove(str(APPS / "contact" / "urls.py"))
if IS_API_ONLY:
    remove(str(APPS / "contact" / "tests" / "test_views.py"))

# contact/translation.py is guarded on the CMS stack AND bilingual, so it renders
# empty for a plain-Django project.
if not IS_WAGTAIL:
    remove(str(APPS / "contact" / "translation.py"))

# API-only projects have no server-rendered surface at all.
if IS_API_ONLY:
    remove(
        str(PKG / "static"),
        str(APPS / "core" / "tests" / "test_templates.py"),
    )
    # Keep the e-mail templates: transactional mail is still HTML.
    templates_dir = PROJECT_ROOT / PKG / "templates"
    if templates_dir.is_dir():
        for child in templates_dir.iterdir():
            if child.name != "emails":
                remove(str(child.relative_to(PROJECT_ROOT)))

# The asset pipeline ships as two variants of the same include rather than an
# {% raw %}{% if %}{% endraw %} inside one: HTML is copied verbatim, never rendered by cookiecutter, so a
# per-option difference in a template has to be a per-option FILE.
INCLUDES = PKG / "templates" / "includes"
for stem in ("styles", "scripts"):
    plain = INCLUDES / f"{stem}.html"
    compressed = INCLUDES / f"{stem}_compressed.html"
    if ASSET_PIPELINE == "compressor" and (PROJECT_ROOT / compressed).exists():
        remove(str(plain))
        (PROJECT_ROOT / compressed).rename(PROJECT_ROOT / plain)
    else:
        remove(str(compressed))

if HAS_TEMPLATES and ANALYTICS != "ga4_gtm":
    remove(
        str(PKG / "templates" / "includes" / "analytics_head.html"),
        str(PKG / "templates" / "includes" / "analytics_body.html"),
    )

if SPAM_PROTECTION == "none":
    remove(
        str(APPS / "core" / "spam.py"),
        str(APPS / "core" / "tests" / "test_spam.py"),
        str(PKG / "templates" / "includes" / "turnstile.html"),
    )
elif SPAM_PROTECTION == "honeypot":
    remove(str(PKG / "templates" / "includes" / "turnstile.html"))

if RATE_LIMITING != "yes":
    remove(str(APPS / "core" / "tests" / "test_rate_limiting.py"))

# Tooling.
if DOCKER != "yes":
    remove("Dockerfile", ".dockerignore", "docker-compose.yml")

if CI == "bitbucket":
    remove(".github")
elif CI == "github":
    remove("bitbucket-pipelines.yml")
else:
    remove(".github", "bitbucket-pipelines.yml")

prune_empty_dirs(PROJECT_ROOT)


# ---------------------------------------------------------------------------
# 2. Local environment file
# ---------------------------------------------------------------------------

env_example = PROJECT_ROOT / ".env.example"
env_file = PROJECT_ROOT / ".env"
if env_example.exists() and not env_file.exists():
    content = env_example.read_text(encoding="utf-8")
    # A real key for local development. Production supplies its own via the environment
    # and the production settings deliberately provide no fallback.
    content = content.replace(
        "SECRET_KEY=change-me-in-production",
        f"SECRET_KEY={secrets.token_urlsafe(50)}",
    )
    env_file.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# 3. Bootstrap
# ---------------------------------------------------------------------------

failures: list[str] = []


def run(command: list[str], description: str, required: bool = True) -> bool:
    sys.stdout.write(f"  {description} ... ")
    sys.stdout.flush()
    try:
        result = subprocess.run(  # noqa: S603
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=900,
        )
    except FileNotFoundError:
        sys.stdout.write(f"{YELLOW}skipped ({command[0]} not installed){RESET}\n")
        if required:
            failures.append(f"{description}: {command[0]} is not installed")
        return False
    except subprocess.TimeoutExpired:
        sys.stdout.write(f"{RED}timed out{RESET}\n")
        failures.append(f"{description}: timed out")
        return False

    if result.returncode != 0:
        sys.stdout.write(f"{RED}failed{RESET}\n")
        tail = (result.stderr or result.stdout or "").strip().splitlines()[-15:]
        for line in tail:
            sys.stdout.write(f"      {line}\n")
        failures.append(description)
        return False

    sys.stdout.write(f"{GREEN}done{RESET}\n")
    return True


if BOOTSTRAP == "yes":
    sys.stdout.write(f"\n{BOLD}Bootstrapping {PROJECT_SLUG}{RESET}\n")

    git_ok = run(["git", "init", "-q", "-b", "main"], "git init")
    sync_ok = run(["uv", "sync", "--quiet"], "uv sync")

    if sync_ok:
        # Migrations are generated rather than shipped: the model set depends on the
        # selected options (languages, multi-site, optional apps), so a shipped migration
        # would be wrong for most combinations.
        run(
            ["uv", "run", "python", "manage.py", "makemigrations", "--no-header"],
            "makemigrations",
        )
        # Normalise import order and formatting. Which optional apps are present
        # changes the import graph, so the canonical order differs per option
        # combination and cannot be baked into the template source.
        run(["uv", "run", "ruff", "check", "--fix", "--quiet", "."], "ruff --fix", required=False)
        run(["uv", "run", "ruff", "format", "--quiet", "."], "ruff format", required=False)
        run(["uv", "run", "pre-commit", "install"], "pre-commit install", required=False)

    if git_ok:
        subprocess.run(["git", "add", "-A"], cwd=PROJECT_ROOT, check=False)  # noqa: S603, S607
        commit = subprocess.run(  # noqa: S603
            [  # noqa: S607
                "git",
                "commit",
                "-q",
                "-m",
                "chore: initial project from cookiecutter-kuwaitnet-web",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        status = "done" if commit.returncode == 0 else "skipped"
        sys.stdout.write(f"  initial commit ... {GREEN}{status}{RESET}\n")


# ---------------------------------------------------------------------------
# 4. Next steps
# ---------------------------------------------------------------------------

sys.stdout.write(f"\n{BOLD}{PROJECT_SLUG} generated.{RESET}\n\n")

if failures:
    sys.stdout.write(f"{YELLOW}Bootstrap did not complete:{RESET}\n")
    for failure in failures:
        sys.stdout.write(f"  - {failure}\n")
    sys.stdout.write("  Run 'make setup' once the problem is resolved.\n\n")

steps = [f"cd {PROJECT_SLUG}"]
if BOOTSTRAP != "yes" or failures:
    steps.append("make setup            # uv sync, migrations, pre-commit hooks")
steps += [
    "createdb " + PROJECT_SLUG + "   # or point DATABASE_URL at an existing database",
    "make migrate",
    "make superuser",
    "make run",
]

sys.stdout.write("Next steps:\n")
for step in steps:
    sys.stdout.write(f"  {step}\n")

sys.stdout.write(
    "\nBefore go-live, work through docs/security-pass.md and the go-live checklist in\n"
    "the KUWAITNET web standards repository.\n\n"
)

if SPAM_PROTECTION == "none" or RATE_LIMITING != "yes" or USE_2FA != "yes":
    sys.stdout.write(
        f"{YELLOW}This project was generated with security defaults disabled. Record the\n"
        f"exception in docs/14-decisions.md.{RESET}\n\n"
    )

# Never leave a failed bootstrap looking like a success in CI.
if failures and os.environ.get("KN_STRICT_BOOTSTRAP"):
    sys.exit(1)
