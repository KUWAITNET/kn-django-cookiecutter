# 15. Handing this to another developer

Written for a developer who has never seen this project, including one who does not work for
{{ cookiecutter.author }}.

## Reading order

1. [01-overview.md](01-overview.md) — what this is and how a request travels through it.
2. This page.
3. [06-installation.md](06-installation.md) — get it running.
4. [14-decisions.md](14-decisions.md) — **before you change anything.** It exists to stop you undoing
   a deliberate choice and rediscovering the reason in production.
5. Then, by task: [05-database.md](05-database.md) for schema work,
   [07-deployment.md](07-deployment.md) before your first release,
{%- if cookiecutter.api != "none" %} [12-api.md](12-api.md) for the interface,
{%- endif %} [09-monitoring.md](09-monitoring.md) when something breaks.

## Getting it running

Follow [06-installation.md](06-installation.md). The short version, on a machine that already has
`uv` and PostgreSQL:

```bash
git clone TODO:<repository-url> {{ cookiecutter.project_slug }} && cd {{ cookiecutter.project_slug }}
make setup
cp .env.example .env          # then set SECRET_KEY and DATABASE_URL
createdb {{ cookiecutter.project_slug }}
make migrate
make superuser
make seed                     # a realistic content set, idempotent, never destructive
make run
```

`make seed` matters: the test suite runs against seeded content, so a developer with an empty
database sees failures that are not real.

## How the code is organised

```text
{{ cookiecutter.project_slug }}/
├── apps/                       every first-party app; a Django app never sits at the repo root
│   ├── core/                   shared, project-wide code
{%- if cookiecutter.countries_app == "yes" %}
│   ├── cities/                 country and city reference data
{%- endif %}
{%- if cookiecutter.notifications_app == "yes" %}
│   ├── notifications/          admin-editable e-mail templates and the send log
{%- endif %}
{%- if cookiecutter.stack == "wagtail" %}
│   ├── home/                   the home page type
│   ├── navigation/             menus and navigation settings
{%- if cookiecutter.frontend != "api_only" %}
│   ├── search/                 site search
{%- endif %}
{%- endif %}
{%- if cookiecutter.forms_suite == "yes" %}
│   ├── contact/                the example public form
{%- endif %}
{%- if cookiecutter.newsletter == "yes" %}
│   ├── newsletter/             subscribers and sending
{%- endif %}
{%- if cookiecutter.api != "none" %}
│   ├── api/                    the HTTP interface
{%- endif %}
│   └── <feature>/
├── {{ cookiecutter.project_slug }}/       the Django project package: no models, no business logic
│   ├── settings/               base, dev, production, test
{%- if cookiecutter.languages == "en_ar" %}
│   ├── locale/                 the one message catalogue for the project
{%- endif %}
{%- if cookiecutter.frontend != "api_only" %}
│   ├── static/                 the theme
│   ├── templates/              the shell and anything not owned by one app
{%- endif %}
│   ├── urls.py
│   └── wsgi.py
├── docs/                       this documentation
├── Makefile                    every command you need
├── pyproject.toml
└── uv.lock                     the authoritative dependency list
```

Where to start reading, in order: `{{ cookiecutter.project_slug }}/settings/base.py`, then
`{{ cookiecutter.project_slug }}/urls.py`, then `apps/core/`. Those three tell you what the system
is made of. Then read the app whose behaviour your task touches.

Inside an app: `models.py` (models, managers, querysets), `forms.py` (forms only — no mail sending,
no API calls), `services.py` (write-side operations), `selectors.py` (cross-app reads),
`admin.py`{% if cookiecutter.stack == "wagtail" %}, `wagtail_hooks.py`{% endif %}{% if cookiecutter.languages == "en_ar" %}, `translation.py`{% endif %}, `tests/`. Only the modules the app
actually needs exist; an empty `services.py` is noise.

## Conventions

These are enforced by review and, where possible, by a tool.

- **Style.** ruff and ruff-format. Line length 100, double quotes. No black, no flake8, no isort.
  `make format` fixes it, `make lint` checks it, CI checks it again.
- **Commits.** Conventional commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`).
- **Branches.** `feature/<ticket>-<slug>` off `main`; promotion is
  `feature/*` → `develop` → `staging` → `main` ([07-deployment.md](07-deployment.md)).
- **Choices are `models.TextChoices`**, never bare strings. A raw string literal for a stored choice
  value should not appear anywhere — not in models, views, templates, tests or fixtures.
- **Business rules live in managers and querysets.** The second time a filter is written, it becomes
  a named manager method with a docstring. Views, forms and serializers may narrow a queryset by
  user input; they may not restate policy.
- **Every user-facing string is translatable** (`gettext_lazy as _`).
- **App names describe a domain, not a layer.** `newsroom`, `careers`, `products` — never `utils`,
  `common`, `helpers`, `misc`.
- **Templates and static inside an app are namespaced by the app name**
  (`apps/<app>/templates/<app>/…`), because Django's loaders merge directories and an
  un-namespaced path resolves to whichever app sorts first.
- **Comments explain why, not what.** A rule that exists because something went wrong says so in one
  clause.

## Tests

```bash
make test                                # fast, no coverage
uv run pytest apps/<app> -k <selection>  # one app, one selection
uv run pytest --create-db                # after a schema change
make test-ci                             # the CI gate, including the coverage floor
```

- Tests live in `apps/<app>/tests/test_*.py` and run under `settings/test.py` against PostgreSQL.
- **The floor is 60 % line coverage on `apps/`, enforced as a hard CI failure.** It may rise; it does
  not fall. Deleting or skipping a test to get a green build is a defect, not a shortcut.
- Unit tests use factories (`apps/<app>/tests/factories.py`). Integration tests run against the
  seeded content set, so the templates and settings under test are the ones that ship.
- **Every fixed bug gets a test** that fails against the unfixed code, committed in the same pull
  request as the fix.

The behaviours that must always have tests, because they are the ones that hurt when they break:
upload validation (oversized, disallowed extension, and a file whose content does not match its
extension must all be rejected), server-side form validation rejection paths, permission denial on
another user's object, the admin prefix responding while `/admin/` returns 404,
{%- if cookiecutter.languages == "en_ar" %} URL resolution in both languages,{% endif %} and a smoke test asserting 200 on every key page.

## Worked example: adding a field

{% if cookiecutter.stack == "wagtail" -%}
Adding a subtitle to a page type, end to end.

1. **Model.** Add the field to the page model, with `help_text` an editor will understand, and add it
   to the editing panels so it appears in the interface.
{%- if cookiecutter.languages == "en_ar" %}
2. **Translation.** Register the field in that app's `translation.py`. Text fields only — never
   register an image, a number or a foreign key.
{%- endif %}
{% if cookiecutter.languages == "en_ar" %}3{% else %}2{% endif %}. **Migration.** `make migrations`, then read the generated file before committing it.
{% if cookiecutter.languages == "en_ar" %}4{% else %}3{% endif %}. **Template.** Render it. Every `<img>` needs explicit `width` and `height`,
   `loading="lazy"` and `decoding="async"` — except the largest above-the-fold image, which is eager
   and preloaded. Any inline `<script>` needs `{% raw %}nonce="{{ request.csp_nonce }}"{% endraw %}`.
{% if cookiecutter.languages == "en_ar" %}5{% else %}4{% endif %}. **Test.** A test that the field saves and renders, and one for whatever it changes.
{% if cookiecutter.languages == "en_ar" %}6{% else %}5{% endif %}. **Create the page in the admin once** before opening the pull request. A field that cannot
   be edited in practice passes every automated check.
{% if cookiecutter.languages == "en_ar" %}7{% else %}6{% endif %}. **Deploy.** [07-deployment.md](07-deployment.md).
{%- else -%}
Adding a field to an editorial model, end to end.

1. **Model.** Add the field with `help_text` an editor will understand. Use `TextChoices` if it is a
   choice.
2. **Admin.** Add it to the `ModelAdmin` explicitly — `list_display`, `fieldsets` or both. A
   `ModelAdmin` with nothing but `pass` is not acceptable.
{%- if cookiecutter.languages == "en_ar" %}
3. **Translation.** Register the field in that app's `translation.py` if it holds text an Arabic
   visitor should see. Text fields only.
{%- endif %}
{% if cookiecutter.languages == "en_ar" %}4{% else %}3{% endif %}. **Migration.** `make migrations`, then read the generated file before committing it.
{% if cookiecutter.languages == "en_ar" %}5{% else %}4{% endif %}. {% if cookiecutter.frontend == "api_only" %}**Serializer.** Expose it explicitly, by name. Never `fields = "__all__"` — it publishes
   every field added to the model afterwards.{% else %}**Template.** Render it. Every `<img>` needs explicit `width` and `height`,
   `loading="lazy"` and `decoding="async"` — except the largest above-the-fold image, which is eager
   and preloaded. Any inline `<script>` needs `{% raw %}nonce="{{ request.csp_nonce }}"{% endraw %}`.{% endif %}
{% if cookiecutter.languages == "en_ar" %}6{% else %}5{% endif %}. **Test.** A test that the field saves and appears where it should, and one for whatever it
   changes.
{% if cookiecutter.languages == "en_ar" %}7{% else %}6{% endif %}. **Deploy.** [07-deployment.md](07-deployment.md).
{%- endif %}

## The parts to be careful with

- **Anything that accepts a file.** Six controls apply to every upload field
  ([14-decisions.md](14-decisions.md)). A new `FileField` with no validators is the single defect
  this project was built to prevent.
- **Anything public that accepts a POST.** It needs server-side validation, spam protection and the
  right rate-limiting layer — and only one layer.
- **Migrations on large tables.** Read `sqlmigrate` output. Adding a `NOT NULL` column with a default
  rewrites the table and holds a lock. See the expand-and-contract procedure in
  [05-database.md](05-database.md).
- **The Content-Security-Policy.** Adding a third-party script means adding an origin to the policy
  and to the third-party register. It does not mean adding `'unsafe-inline'`.
{%- if cookiecutter.languages == "en_ar" %}
- **The language switcher.** It must resolve the *translated* address of the current page and
  preserve the query string. A switcher that only swaps the URL prefix 404s the moment a slug is
  translated.
{%- endif %}
- **`AXES_IPWARE_PROXY_COUNT`** must match the real number of proxies. Wrong, and one attacker locks
  out every user.
- **`fields = "__all__"`** on a public form or serializer publishes every field added to the model
  afterwards. It is never used here.
- **`settings/production.py`** provides no defaults for secrets, deliberately. Do not add one to make
  a deploy "just work".

## Getting a first change to production

1. Branch: `feature/<ticket>-<slug>`.
2. Make the change, with a test that fails without it.
3. `make format lint test check-deploy` — all green locally.
4. Open a pull request. CI runs lint, static security analysis, a dependency audit, a missing-
   migration check, the test suite with the coverage gate, and the production configuration check.
5. Review, then merge to `develop`. Verify on development.
6. Merge to `staging`. Verify there, in every language the site serves.
7. After UAT sign-off, merge to `main`, tag, and follow [07-deployment.md](07-deployment.md).

## Definition of done

A change is done when all of these are true — not when it works locally.

- [ ] Conventional-commit history; no commented-out code, no debug prints, no scratch files.
- [ ] `ruff check` and `ruff format --check` pass, with no new per-file ignores.
- [ ] Tests exist for the behaviour added, **including at least one failure path**, and the suite
      passes at or above the coverage floor.
- [ ] `makemigrations --check --dry-run` is clean, and any new migration has been read by the
      reviewer.
- [ ] Every new environment variable is in `.env.example` with a placeholder and a comment, and in
      [04-environment-variables.md](04-environment-variables.md).
- [ ] No secret, key, token, real hostname or real e-mail address is committed.
- [ ] New business-rule querysets are manager methods; new choice fields use `TextChoices` and the
      interface shows labels, not stored codes.
- [ ] `make check-deploy` is clean.
- [ ] Every user-visible string is translatable{% if cookiecutter.languages == "en_ar" %}, and every new template is correct in both
      languages and both text directions{% endif %}.
- [ ] Any new public POST endpoint has server-side validation, spam protection and a rate limit.
- [ ] The README is updated if the way to run, test, seed or deploy the project changed.
- [ ] The affected file in `docs/` is updated in the same commit.

## First week

Do this loop once. A developer who has completed it is genuinely handed over; one who has only read
the documentation is not.

- [ ] Run it locally, with seeded content, in every language the site serves.
- [ ] Read [14-decisions.md](14-decisions.md) end to end.
- [ ] Find where a request for the homepage enters the code and follow it to the template.
- [ ] Make a trivial change, with a test.
- [ ] Get it reviewed and merged.
- [ ] Deploy it to staging yourself, following the runbook rather than someone's memory.
- [ ] Find the log entry proving it happened.
{%- if cookiecutter.sentry == "yes" %}
- [ ] Trigger a deliberate error in development and find it in the error monitor.
{%- endif %}
- [ ] Run a restore test, or watch one ([08-backup-restore.md](08-backup-restore.md)).

## Contacts

TODO: name the outgoing technical lead, the client's technical contact, who holds the hosting
credentials, who holds the secrets store, and how long the warranty period runs.
