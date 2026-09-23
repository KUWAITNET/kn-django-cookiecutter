# Instructions for AI coding assistants

{{ cookiecutter.project_name }} — a {% if cookiecutter.stack == "wagtail" %}Wagtail{% else %}Django{% endif %} project generated from the KUWAITNET project template.

Read [README.md](README.md) for how to run, test and deploy this project, and
[docs/14-decisions.md](docs/14-decisions.md) before changing anything that looks odd — most of it is
deliberate. This file is the working conventions, not a substitute for either.

## Before you write code

- `make setup && make migrate && make seed` — the test suite runs against seeded content.
- Read the app you are changing. Only the modules an app needs exist, so a missing `services.py`
  means that app has no write-side operations yet, not that the convention was forgotten.
- If a rule here conflicts with what the code actually does, the code is either wrong or has a
  reason. Find the reason before changing either.

## Layout

- All first-party code lives under `apps/`. A Django app never sits at the repository root.
- `{{ cookiecutter.project_slug }}/` is the project package: settings, URLs, WSGI{% if cookiecutter.frontend != "api_only" %}, project templates and the
  theme{% endif %}. **No models and no business logic.**
- Inside an app: `models.py` (models, managers, querysets), `forms.py` (forms only), `services.py`
  (write-side operations), `selectors.py` (cross-app reads), `admin.py`{% if cookiecutter.stack == "wagtail" %}, `wagtail_hooks.py`{% endif %}{% if cookiecutter.languages == "en_ar" %},
  `translation.py`{% endif %}, `tests/`.
- App templates and static files are namespaced by app name: `apps/<app>/templates/<app>/…`.
  Un-namespaced paths resolve to whichever app sorts first in `INSTALLED_APPS`.
- App names describe a domain, not a layer. Never create `utils`, `common`, `helpers` or `misc`.
- Something moves into `apps/core/` the **second** time it is needed, not the first.

## Settings

- `base.py` holds everything shared and never branches on environment. `dev.py`, `production.py` and
  `test.py` import from it and override.
- Every configuration value is read through `django-environ` in the settings package. Never
  `os.environ.get()` elsewhere in the codebase.
- A new setting means: read it in `base.py`, add it to `.env.example` with a placeholder and a
  one-line comment, and add it to `docs/04-environment-variables.md`. All three, same commit.
- `production.py` provides **no defaults for secrets**. Do not add one to make a deploy work.

## Code conventions

- ruff and ruff-format. Line length 100, double quotes. `make format` then `make lint`.
- `models.TextChoices` for every choice field. A raw string literal for a stored choice value must
  not appear in models, forms, views, services, templates, tests or fixtures.
- Every app has an explicit `AppConfig` with `name = "apps.<x>"`, `label = "<x>"` and
  `default_auto_field`.
- User-facing strings use `gettext_lazy as _`.
- Business rules become manager or queryset methods the second time they are written. Views, forms
  and serializers may narrow a queryset by user input; they may not restate policy.
- Every `ModelAdmin` subclasses Unfold's and declares `list_display`, `list_filter`, `search_fields`,
  `ordering` and `fieldsets` explicitly. A `ModelAdmin` with nothing but `pass` is not acceptable.
- Comments explain **why**, never what. A rule that exists because something went wrong says so in
  one clause.
- Type hints where they add clarity; not on Django boilerplate.

## Security invariants — never weaken these

If a task appears to require breaking one of these, stop and say so instead.

- **Uploads.** Every field that accepts a file enforces all six: a per-field size limit; an
  extension **allowlist**, never a denylist; content sniffing so the real type matches the
  extension (the browser-supplied content type and filename are attacker-controlled); server-side
  image re-encoding bounded against decompression bombs, with SVG never accepted on a public field;
  a **generated** stored filename with the original kept in a separate column for display only; and
  `PRIVATE_MEDIA_ROOT` for anything containing personal data. Never add a bare `FileField()`.
- **Private media** is served only through the permission-checked private-media view. Never from
  `MEDIA_URL`, and never by handing out a path.
{%- if cookiecutter.spam_protection != "none" %}
- **Every public form** carries the project's spam protection{% if cookiecutter.spam_protection == "turnstile_honeypot" %} — Turnstile plus a honeypot, degrading
  to honeypot-only when no key is configured{% endif %}. Do not add a public form without it, and do not
  "temporarily" remove it to test something.
{%- endif %}
{%- if cookiecutter.rate_limiting == "yes" %}
- **Rate limiting is layered and the layers never overlap.** Login lockout on authentication
  endpoints{% if cookiecutter.frontend != "api_only" %}; `django-ratelimit` on public non-API POST endpoints{% endif %}{% if cookiecutter.api != "none" %}; DRF throttles on everything
  under `/api/`. Never a rate limiter on a DRF view{% endif %}.
{%- endif %}
- **Content-Security-Policy.** No `'unsafe-inline'` and no `'unsafe-eval'` in `script-src`. An
  inline script carries `{% raw %}nonce="{{ csp_nonce }}"{% endraw %}`. A new third-party script means adding
  its origin to the policy — never relaxing the policy.
- **No `fields = "__all__"`** on any public `ModelForm` or serializer. List the fields.
- **Server-side validation on every field**, always, regardless of what the browser does.
- **No secrets in code**: no key, token, password, real hostname or real e-mail address in a commit.
  `.env` is never committed.
- **Never disable a security control to make a test pass.** `settings/test.py` already relaxes the
  few that must be relaxed; anything more is a defect in the test.
- **Never add a diagnostic or debug endpoint** that relies on an unguessable URL. A non-guessable
  URL is not a permission check. Gate it on a staff permission.
- **Never log** a password, token, session key, `Authorization` header, identity number, uploaded
  file's contents, or a full form submission. Log the stored record's identifier.
- **Object-level permission checks** in addition to view-level ones. "Can view this model" is not
  "can view this row".

## Tests

- `apps/<app>/tests/test_*.py`, pytest + pytest-django, against PostgreSQL, under
  `settings/test.py`.
- `make test` locally; `make test-ci` is the gate. The floor is **60 % coverage on `apps/`**, a hard
  CI failure. It may rise; it does not fall.
- Never delete, skip or `xfail` a test to get a green build. That is a defect, not a shortcut.
- New behaviour needs a test, **including at least one failure path**.
- Every fixed bug gets a regression test that fails against the unfixed code, in the same commit as
  the fix.
- Uploads, permission denial, and server-side form rejection always have tests. They are the
  behaviours this project exists to get right.
- Unit tests use factories; integration tests run against the seeded content.

## Migrations

- A migration ships in the same commit as the model change. CI runs
  `makemigrations --check --dry-run` and fails on drift.
- **Never edit a migration that has been merged to `main`.** Fix forward.
- Read `manage.py sqlmigrate <app> <n>` before proposing a migration on a large table.
- Removing or renaming a column is expand-and-contract across at least two releases
  ([docs/05-database.md](docs/05-database.md)). The destructive step never ships with the code that
  stopped using the column.
- `RunPython` uses `apps.get_model(...)`, never a direct model import, and supplies a reverse or an
  explicit `RunPython.noop` with a comment.

## Deployment

Do not invent a deploy procedure. The runbook is [docs/07-deployment.md](docs/07-deployment.md), and
its shape is fixed: take a database backup, deploy a **tag** (never a branch),
`uv sync --frozen --no-dev`, `collectstatic` under the production settings{% if cookiecutter.languages == "en_ar" %}, `compilemessages`{% endif %},
`migrate --noinput` **before** the restart, restart, then verify with the listed checks. Rollback is
planned before the deploy, not improvised after it.

## Do not do this

- Do not add a dependency without a reason in the commit message, and never widen the Django{% if cookiecutter.stack == "wagtail" %} or
  Wagtail{% endif %} version bound to make an unrelated package resolve.
{%- if cookiecutter.stack == "wagtail" %}
- Do not model news, press releases, events or media-room items as Wagtail pages. They are models
  edited through a `SnippetViewSet`, served by one routable index page{% if cookiecutter.newsroom == "yes" %} - copy `apps/newsroom`{% endif %}
  ([docs/14-decisions.md](docs/14-decisions.md)).
{%- endif %}
- Do not add a background worker, task queue or scheduler. Mail is sent synchronously on purpose
  ([docs/14-decisions.md](docs/14-decisions.md)).
- Do not add a JavaScript build step or a Node toolchain.
- Do not move the administration interface back to `/admin/`.
- Do not put business logic in a template tag, a context processor or a template filter, and never
  perform an ORM write in one.
- Do not create `docs/` files outside the numbered set; the filenames are referenced by the
  KUWAITNET handover checklist.
- Do not write a "last updated" line or a version number into a document. Git owns that.
- Do not commit `.mo` files, `staticfiles/`, media, or anything under `.env*` except `.env.example`.
- Do not commit large binaries. Editorial images and documents belong in the media directories, not
  in the repository.
- Do not silence a ruff `S` (security) finding by removing the rule or adding a blanket per-file
  ignore. Silence it inline with a reason on the same line, or fix it.
- Do not create files the task did not ask for — no summary documents, no scratch notes in the
  repository.
- Do not claim something works without running it. `make lint test check-deploy` is three commands.

## When you finish a change

- [ ] `make format lint test check-deploy` all pass.
- [ ] New environment variables are in `.env.example` **and** `docs/04-environment-variables.md`.
- [ ] The affected `docs/` file is updated in the same commit.
- [ ] `README.md` is updated if the way to run, test, seed or deploy changed.
- [ ] The commit message is a conventional commit and says **why**.
