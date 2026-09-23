# cookiecutter-kuwaitnet-web

The KUWAITNET project template. A new Django or Wagtail project starts here, with the
[KUWAITNET web standards](../kuwaitnet-web-standards) already implemented rather than waiting to be
remembered.

That is the point of it. A standard that has to be re-implemented by hand on every project is a
standard that gets skipped under deadline pressure. Wherever a rule can ship as a default, this
template ships it, and the rule becomes "do not remove this" instead of "remember to add this".

## What it generates

A runnable project — dependencies installed, migrations generated, git initialised, first commit
made — containing:

- **Settings split** into `base` / `dev` / `production` / `test`, entirely environment-driven
  through `django-environ`. Production reads secrets with **no defaults**, so a misconfigured deploy
  fails at boot instead of running with a development key.
- **The security pack.** Six controls on every upload field (size cap, extension allowlist, content
  sniffing with `python-magic`, server-side image re-encoding with SVG excluded, generated stored
  filenames, private storage for personal data); a private-media view that checks permission;
  Content-Security-Policy with a per-request nonce and no `unsafe-inline` or `unsafe-eval` in
  `script-src`; Permissions-Policy; Argon2 hashing; an administration interface that is not at
  `/admin/`.
- **Layered abuse resistance**: `django-axes` on authentication, `django-ratelimit` on public
  non-DRF POST endpoints, DRF throttles under `/api/` — never two on one view.
- **Spam protection** that degrades rather than blocks: Turnstile plus a honeypot, falling back to
  honeypot-only when no key is configured, so development, CI and UAT never break.
- **E-mail through `django-post-office`**, wrapping whichever real transport is configured, so every
  send is logged and auditable. Delivery is synchronous: no worker, no queue, nothing to forget on a
  new server.
- **django-unfold** wherever `django.contrib.admin` is mounted, on both stacks.
- **Tooling**: `uv` with a committed lock file, ruff and ruff-format, pytest against PostgreSQL with
  a 60 % coverage floor, bandit, `pip-audit`, pre-commit hooks, a Makefile, a multi-stage Dockerfile
  and a CI pipeline that gates on all of it.
- **The documentation set** — `docs/README.md` plus `01-overview.md` … `15-developer-handover.md`
  and `security-pass.md` — pre-filled with everything the template knows, and marked `TODO:`
  everywhere only the project team can supply an answer. It is the
  [technical documentation skeleton](../kuwaitnet-web-standards/client-templates/technical-documentation-skeleton.md)
  as a real directory, written while the site is built rather than assembled from memory at the end.
- A project `README.md` and a `CLAUDE.md` for AI coding assistants.

## The two stacks

| | `stack=wagtail` | `stack=django` |
|---|---|---|
| For | A content-managed website | A plain Django application or an API backend |
| Content | Wagtail page tree, revisions, editor interface | Models and the Django admin |
| Admin | Wagtail admin, plus django-unfold for models with no editor interface | django-unfold |
| 2FA | `wagtail-2fa` | `django-otp` with an OTP-required admin site |
| Translation | `wagtail-modeltranslation` | `django-modeltranslation` |
| Sitemap | `wagtail.contrib.sitemaps` | `django.contrib.sitemaps` classes |
| Redirects | Editor-managed | `django.contrib.redirects` in the admin |

### The layering rule

Everything that is not specifically about a content management system is **core** and ships on both
stacks: the settings, the security pack, uploads, e-mail, notifications, newsletter, countries,
internationalisation, SEO partials, the DRF pack, the tooling and the documentation. Only the page
tree, blocks, panels, viewsets, site scoping and admin branding are the Wagtail layer.

Where the same requirement has two implementations, both exist and neither stack is left without an
answer.

**A `stack=django` project contains no occurrence of the string "wagtail"** — not in code, not in
comments, not in documentation. That is verified, not assumed:

```bash
grep -ri wagtail path/to/generated/project    # must return nothing
```

## Running it

```bash
uvx --from cookiecutter cookiecutter gh:kuwaitnet/cookiecutter-kuwaitnet-web
```

From a local checkout:

```bash
uvx --from cookiecutter cookiecutter /path/to/cookiecutter-kuwaitnet-web
```

Non-interactively, which is also how the verification runs work:

```bash
uvx --from cookiecutter cookiecutter /path/to/cookiecutter-kuwaitnet-web --no-input \
    project_name="Client Site" stack=django api=rest languages=en
```

**Use `uvx`.** A system-installed `cookiecutter` is frequently a stale Python 2 shim left behind by
a package manager; it fails with a syntax error inside its own source, which looks like a fault in
the template. `uvx` fetches a current cookiecutter into a throwaway environment and leaves nothing
behind.

Answer the prompts, or accept the defaults — the defaults are the KUWAITNET standard.

## Options

| Option | Default | Values | What it ships |
|---|---|---|---|
| `stack` | `wagtail` | `wagtail`, `django` | Wagtail CMS site, or a plain Django application / API backend |
| `project_name` | `KUWAITNET Web Project` | string | Human-readable name; used in titles, e-mail and admin branding |
| `project_slug` | derived from `project_name` | string | Python package and directory name; validated as an identifier |
| `client_name` | `KUWAITNET` | string | Used in branding and in the generated documentation |
| `domain_name` | `example.com` | hostname | Production domain; used in `CSRF_TRUSTED_ORIGINS` and every runbook |
| `author` / `author_email` | `KUWAITNET` / `info@kuwaitnet.com` | string | Attribution and the default `DEFAULT_FROM_EMAIL` |
| `description` | one line | string | `pyproject.toml` and the API schema description |
| `timezone` | `Asia/Kuwait` | TZ name | `TIME_ZONE`; `USE_TZ` is always on |
| `python_version` | `3.13` | `3.x` | `.python-version`, `requires-python`, the ruff target and the Docker base image |
| `languages` | `en_ar` | `en_ar`, `en` | Bilingual English + Arabic with RTL support and translated fields, or English only |
| `frontend` | `server_rendered` | `server_rendered`, `api_only` | Server-rendered templates, or an API-only backend with no public HTML surface |
| `multisite` | `single` | `single`, `multi` | Wagtail only: several sites from one instance, with site-scoped content and settings |
| `admin_url_prefix` | `manage` | string | The administration path. Wagtail's admin on the Wagtail stack, Django's on the Django stack. **Must not be `admin`** |
| `django_admin_url_prefix` | `backoffice` | string | [wagtail] The Django admin's own path. Independent of `admin_url_prefix`, never nested under it |
| `use_2fa` | `yes` | `yes`, `no` | `wagtail-2fa` or `django-otp`, enforced for every administrative account |
| `spam_protection` | `turnstile_honeypot` | `turnstile_honeypot`, `honeypot`, `none` | Cloudflare Turnstile plus a honeypot, degrading to honeypot-only with no key |
| `rate_limiting` | `yes` | `yes`, `no` | `django-axes` lockout plus `django-ratelimit` on public POST endpoints |
| `countries_app` | `django_countries` | `django_countries`, `cities`, `none` | Which country backend `apps/core/countries.py` implements. `django_countries` = the KUWAITNET fork, installed from git: a country field and choices with no tables and no import, and the country-list policy applied in the data. `cities` = `django-cities-light` in `apps/cities`: editor-toggleable countries, dial codes, nationalities, translated names, regions and cities — empty until the GeoNames import has run |
| `notifications_app` | `yes` | `yes`, `no` | Admin-editable e-mail templates, per-language sending, and an e-mail log |
| `newsletter` | `yes` | `yes`, `no` | Subscribers, unsubscribe tokens, an admin composer |
| `forms_suite` | `yes` | `yes`, `no` | An example contact form: validated, rate-limited, spam-protected, with secure uploads |
| `api` | `none` | `none`, `rest`, `headless` | `rest` = the DRF pack (`/api/v1/`, OpenAPI, JWT, throttles, RFC 9457 errors); `headless` adds the Wagtail API v2 endpoints |
| `sentry` | `yes` | `yes`, `no` | Sentry, initialised only when `SENTRY_DSN` is set |
| `analytics` | `ga4_gtm` | `ga4_gtm`, `none` | GA4 / Tag Manager hooks with IDs read from the environment |
| `database` | `postgres` | fixed | PostgreSQL is the only supported database |
| `cache` | `redis` | `redis`, `locmem` | Redis is required in production wherever a counter lives in the cache |
| `task_queue` | `none` | `none`, `huey`, `celery` | Background work. `none` is the right default: a queue is a second process to deploy, monitor and restart. `huey` = one consumer running the queue **and** the schedule. `celery` = routing, priorities, several queues, chains and groups — at the cost of a broker, a worker and beat |
| `huey_backend` | `postgres` | `postgres`, `redis`, `sqlite` | `task_queue=huey` only. `postgres` needs **no new service**: four tables in the application database, created by `migrate` and backed up with everything else. `redis` keeps queue churn off the database but is a service to run and persist. `sqlite` is development only |
| `task_broker` | `redis` | `redis`, `rabbitmq`, `sqs` | `task_queue=celery` only, and it is a **durability** decision. `redis` is not a durable broker — a restart can drop queued tasks. `rabbitmq` gives durable queues, publisher confirms and dead-lettering, for a server to run and back up. `sqs` gives the same durability fully managed, but `celery inspect` and Flower do not work over it, there are no broker-level priorities, and `celery[sqs]` pulls `pycurl`, which is compiled at install time |
| `docker` | `yes` | `yes`, `no` | A multi-stage uv Dockerfile and a compose file for local services |
| `ci` | `bitbucket` | `bitbucket`, `github`, `none` | A pipeline running ruff, bandit, `pip-audit`, the missing-migration check, the coverage gate and `check --deploy` |
| `deploy_target` | `gunicorn_nginx` | `gunicorn_nginx`, `docker_compose` | Which runbook `docs/07-deployment.md` is written for |
| `bootstrap` | `yes` | `yes`, `no` | `git init`, `uv sync`, `makemigrations`, `pre-commit install` and a first commit |

## Combination rules the pre-generation hook enforces

Generation is aborted, before any file is written, when:

| Rule | Why |
|---|---|
| `project_slug` is not a valid Python identifier, is a keyword, or collides with `django`, `wagtail`, `apps`, `test(s)`, `settings`, `static`, `media` | The package would be unimportable, or would shadow something the project itself uses |
| Either admin prefix is `admin`, is empty, is not URL-safe, or collides with `api`, `static`, `media`, `search`, `accounts`, `documents`, `images` | The default admin path is the first thing scanners try; a colliding prefix silently shadows another route |
| [wagtail] `django_admin_url_prefix` equals `admin_url_prefix` | Two admins on one path defeats the reason for having a non-default prefix at all. A prefix merely *derived* from the other warns rather than fails |
| `stack=django` with `multisite=multi` | Site scoping is built on Wagtail's site model |
| `stack=django` with `api=headless` | `headless` means the Wagtail page/image/document endpoints. Use `api=rest` |
| `stack=wagtail` with `frontend=api_only` | A CMS site serves pages. For a headless backend use `stack=wagtail` with `api=headless` |
| `frontend=api_only` with `api=none` | An API-only project with no API |
| `frontend=api_only` with `forms_suite=yes` or `newsletter=yes` | Both need server-rendered templates; in an API project the serializers do that work |
| `deploy_target=docker_compose` with `docker=no` | The runbook would document a deployment whose Dockerfile was never generated |
| `task_broker` is `rabbitmq` or `sqs` without `task_queue=celery` | Only Celery talks to an external broker. Huey is backed by PostgreSQL, Redis or SQLite, and `task_queue=none` has nothing to broker. The default `redis` value is ignored silently, so a project with no queue never has to answer a broker question |
| `domain_name` is not a hostname, or `python_version` is not `3.x` | Caught here rather than at boot |

It also **warns without blocking** — each of these is a documented exception under the security
baseline, and the generated `docs/14-decisions.md` carries a pre-written entry saying so:

- `spam_protection=none` — every public form becomes an open relay.
- `rate_limiting=no` — no login lockout and no limits on public POST endpoints.
- `use_2fa=no` — a stolen administrator password is sufficient to take over the site.
- `rate_limiting=yes` with `cache=locmem` — counters are per-process, so N workers multiply every
  limit by N.
- `api != none` with `cache=locmem` — the same problem for throttles.
- `notifications_app=no` with forms or a newsletter enabled — no admin-editable templates and no
  e-mail log.
- `huey_backend=redis` or `task_broker=redis` with `cache=locmem` — the queue needs a real Redis and
  this project configures none, so the URL falls back to a localhost default that has to exist
  wherever the worker runs.
- `huey_backend=sqlite` — single-process storage; it contradicts the PostgreSQL-only rule and does
  not survive a second worker.
- `task_broker=sqs` — `celery[sqs]` pulls `pycurl`, a C extension that needs libcurl and OpenSSL
  headers to build, so `uv sync` fails on a machine without them. SQS also carries no Celery remote
  control or events, so `celery inspect` and Flower do not work.

## What the post-generation hook does

1. **Prunes.** Deletes every file and directory belonging to an unselected feature, so the generated
   project has no dead conditional code and no module for something that was not chosen. This is why
   the template prefers "a separate file that gets deleted" over "an `{% if %}` around half a
   module".
2. **Writes `.env`** from `.env.example`, with a real generated `SECRET_KEY` for local development.
   Production supplies its own; the production settings deliberately provide no fallback.
3. **Bootstraps** (when `bootstrap=yes`): `git init`, `uv sync`, `makemigrations`,
   `pre-commit install`, and an initial conventional commit.

Migrations are generated rather than shipped: the model set depends on the selected options, so a
committed migration would be wrong for most combinations.

A bootstrap failure is reported loudly but never deletes the generated project — a dropped network
connection should not cost you the generation. Set `KN_STRICT_BOOTSTRAP=1` to make a failure exit
non-zero, which is what CI wants.

## Verifying a generated project

Every combination must produce a project that passes all of these. Generate, then:

```bash
cd <generated-project>
createdb <slug>

uv sync
uv run ruff check .
uv run ruff format --check .
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py check

DJANGO_SETTINGS_MODULE=<slug>.settings.production \
SECRET_KEY=verify-only-not-a-secret \
ALLOWED_HOSTS=example.com \
SECURE_SSL_REDIRECT=True \
  uv run python manage.py check --deploy --fail-level WARNING

uv run pytest -q
```

And, for a `stack=django` project:

```bash
grep -ri wagtail .        # must return nothing
```

Combinations worth running before any change is merged, because they exercise different code paths:

| Run | Options |
|---|---|
| Default | everything default (`stack=wagtail`) |
| Plain Django site | `stack=django` |
| API backend | `stack=django frontend=api_only api=rest forms_suite=no newsletter=no` |
| Headless CMS | `stack=wagtail api=headless` |
| Minimal | `languages=en spam_protection=none rate_limiting=no use_2fa=no cache=locmem docker=no ci=none` — must still generate, still pass, and still warn |
| Multi-site | `stack=wagtail multisite=multi` |

## Contributing a change

1. Read [the standards](../kuwaitnet-web-standards) first. Most template changes are a standard
   change wearing a disguise; if the rule is wrong, change the standard in the same pull request
   rather than quietly diverging here.
2. Branch, change the template, and **generate at least the affected combinations** from the
   matrix above. A change that has not been generated has not been tested.
3. Remember the Jinja rules. Cookiecutter renders every generated file with `StrictUndefined`:
   - `.html` files, and anything under a `templates/`, `templates_wagtail/` or `templates_django/`
     directory, are copied without rendering. You cannot use a cookiecutter variable inside one; use
     a context processor or a runtime condition.
   - `.py`, `.toml`, `.yml`, `.md`, `.txt` and `Makefile` **are** rendered. Any literal Django
     template syntax in one must be wrapped in a raw block, or generation fails with an undefined
     error.
   - Use whitespace-control markers so generated Python has no stray blank lines.
4. Keep the two documentation sets in step. The generated `docs/` tree and
   [the technical documentation skeleton](../kuwaitnet-web-standards/client-templates/technical-documentation-skeleton.md)
   are the same artefact. When one changes, change the other in the same pull request — otherwise
   the generated projects and the client deliverable drift, which is exactly how our reference
   project ended up with its only runbook untracked and documenting the wrong admin path.
5. Every rule the template enforces should carry the reason it exists, in one clause. Rules with a
   reason survive; rules without one get argued away.

## Related

- [KUWAITNET web standards](../kuwaitnet-web-standards) — the rules this template implements, and
  the client-facing documents that go with them.
- [Security baseline](../kuwaitnet-web-standards/security-baseline.md) — the controls, and the
  pre-go-live security pass the generated `docs/security-pass.md` records.
- [Project structure](../kuwaitnet-web-standards/project-structure.md) — the layout, settings split,
  naming and migration rules the generated project follows.
- [Technical documentation skeleton](../kuwaitnet-web-standards/client-templates/technical-documentation-skeleton.md)
  — the `docs/` tree this template creates.
