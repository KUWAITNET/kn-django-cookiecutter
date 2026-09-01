# 14. Technical decisions and known limitations

A dated log of the decisions that shaped this system. Its purpose is to stop the next developer from
cheerfully undoing a deliberate choice and then rediscovering the reason for it in production.

Every entry below was made when the project was generated from the KUWAITNET project template. They
are recorded here so they can be argued with knowingly rather than reversed by accident.

TODO: record the generation date at the top of the first entry, and add every subsequent decision on
the day it is made — not at handover, when the reasoning has evaporated. Newest last.

Use this shape:

```markdown
### <date> — <the decision, in one line>

**Context.** What problem or constraint prompted it.
**Decision.** What we do.
**Alternatives considered.** What we did not do, and why.
**Consequences.** What this makes easy, what it makes hard, and what would have to change to
reverse it.
```

---

## Decisions made at project generation

### Long-term support releases, with narrow upper bounds

**Context.** A framework upgrade is cheap when planned and expensive when forced by an end-of-life
date that arrived unnoticed.
**Decision.** Django is pinned to the 5.2 LTS line (`django>=5.2,<5.3`){% if cookiecutter.stack == "wagtail" %} and Wagtail to the 7.4 LTS line
(`wagtail>=7.4,<7.5`){% endif %}. Python is pinned by `.python-version` and `requires-python`.
**Alternatives considered.** Tracking the latest feature release: more features sooner, but an
upgrade every eight months and a support window measured in months rather than years.
**Consequences.** Patch releases arrive through `uv lock --upgrade`; a feature-release upgrade is
scheduled work. Do not widen the bound to make an unrelated dependency resolve — that turns a
planned upgrade into an accidental one. The support dates are in [02-stack.md](02-stack.md); put
them in a calendar.

### uv as the package manager, with `uv.lock` committed

**Context.** "It works on my machine" is almost always a different dependency set.
**Decision.** `uv` manages the Python version and the dependencies. `uv.lock` is committed. Deploys
and CI install with `uv sync --frozen`, which installs exactly what is pinned and never re-resolves.
**Alternatives considered.** pip with a requirements file (no lock of transitive dependencies);
Poetry (slower, and a second tool to install on every server).
**Consequences.** The lock file is the authoritative dependency inventory
([02-stack.md](02-stack.md)). A deploy that omits `--frozen` installs something nobody tested.

### Settings split into base, dev, production and test

**Context.** A single settings module with `if DEBUG:` branches means the configuration that runs in
production is one nobody has ever run in full.
**Decision.** `base.py` holds everything shared and never branches on environment. `dev.py`,
`production.py` and `test.py` import from it and override. Every value comes from the environment
through `django-environ`. **Production reads secrets with no default**, so a misconfigured deploy
fails loudly at boot rather than silently running with a development key.
**Alternatives considered.** One module with environment branches; a `local.py` on the server as the
production configuration store.
**Consequences.** Staging and production run the *same* module, differing only in hostname,
credentials and data. `settings/local.py` remains a development escape hatch and is gitignored; no
deploy procedure may instruct anyone to create one on a production host.

### The administration interface is not at `/admin/`

**Context.** `/admin/` is the first path every automated scanner tries.
**Decision.** The administration interface is mounted at `/{{ cookiecutter.admin_url_prefix }}/`.
**Alternatives considered.** Leaving it at the default and relying on lockout alone.
**Consequences.** Scanner noise in the logs drops sharply, which makes real attempts visible. **This
is defence in depth, not a security control**: the controls that do the work are the second factor,
the lockout and TLS. Changing the prefix later changes every bookmark and every piece of
documentation, so it is a decision, not a preference.

### django-unfold as the administration skin

**Context.** Every project was branding the admin differently, by overriding templates, and every
Django upgrade broke a different one.
**Decision.** `django-unfold` is used wherever `django.contrib.admin` is mounted. Branding is done
through the `UNFOLD` settings dictionary.
**Alternatives considered.** Plain admin with template overrides (breaks on upgrade); another skin
(the same problem, one project at a time).
**Consequences.** Every `ModelAdmin` subclasses Unfold's. Template overrides are a last resort; if
any are added, list them and the Unfold version they were written against in the project README.
TODO: the colour palette in `UNFOLD["COLORS"]` is still the template default — replace it with
{{ cookiecutter.client_name }}'s brand palette.

{% if cookiecutter.use_2fa == "yes" -%}
### Two-factor authentication on every administrative account

**Context.** A stolen or reused password is the most common way an administrative account is lost,
and lockout does not help when the attacker has the correct password.
**Decision.** A second factor is enforced by the application for every administrative account, not
by policy. It is disabled in the automated test settings only, where enrolment flows are not what is
under test.
**Alternatives considered.** Enforcing it by policy and trusting people; IP allowlisting instead
(useless for staff who travel).
**Consequences.** Every new administrator must enrol before doing anything. A lost device with no
recovery codes needs an administrator to reset the enrolment. Disabling it in development or staging
defeats the point — staging is where enrolment is proven to work.
{%- else -%}
### Two-factor authentication was NOT enabled — documented exception

**Context.** The security baseline requires a second factor on every administrative account.
**Decision.** This project was generated without it.
**Alternatives considered.** Enabling it, which is the standard.
**Consequences.** A stolen administrator password is sufficient to take over the site.
TODO: record who accepted this exception, when, on what grounds, and what compensating control is in
place. This is a go-live finding until that is written down.
{%- endif %}

{% if cookiecutter.rate_limiting == "yes" -%}
### Abuse resistance is layered, and the layers never overlap

**Context.** Two limiters on one view produce two different 429 shapes and a double-counted budget,
and nobody can tell which one rejected a request.
**Decision.** Three tools, three jobs:

- **Login lockout** on authentication endpoints. A lockout produces an auditable record; that is a
  different control from a rate cap.
{%- if cookiecutter.frontend != "api_only" %}
- **Rate limits** on public non-API POST endpoints — forms, subscribe, search. Endpoints that send
  mail or write files get the tightest budgets, because each request costs an external resource.
{%- endif %}
{%- if cookiecutter.api != "none" %}
- **Throttles** on everything under `/api/`. Never a rate limiter as well.
{%- endif %}

**Alternatives considered.** One mechanism everywhere; nothing at all (which is what the reference
project this template came from actually had, across seven unauthenticated endpoints, one of which
sent an e-mail per request).
**Consequences.** Adding a public POST endpoint means choosing the right layer for it. Adding the
wrong one, or a second one, is a review finding.
{%- else -%}
### Rate limiting and login lockout were NOT enabled — documented exception

**Context.** The security baseline requires both.
**Decision.** This project was generated without either.
**Alternatives considered.** Enabling them, which is the standard.
**Consequences.** There is no automated defence against credential stuffing or against a script
submitting a public form thousands of times. TODO: record who accepted this, when, and on what
grounds.
{%- endif %}

{% if cookiecutter.spam_protection != "none" -%}
### Spam protection degrades rather than blocks

**Context.** A bot check that is mandatory in every environment breaks development, CI and client
UAT, and someone eventually disables it globally to fix a local problem.
**Decision.** Public forms carry {% if cookiecutter.spam_protection == "turnstile_honeypot" %}a Cloudflare Turnstile challenge **and** a honeypot field. With no
Turnstile key configured, protection degrades to honeypot-only rather than rejecting every
submission{% else %}a honeypot field{% endif %}.
**Alternatives considered.** reCAPTCHA (heavier, worse privacy posture); a mandatory challenge in
every environment (breaks UAT); nothing (an open mail relay).
**Consequences.** Development, CI and UAT never break on a missing key.
{%- if cookiecutter.spam_protection == "turnstile_honeypot" %}
**Production without a key is a go-live finding**, because the degraded mode is a fallback, not the
intended production state. The honeypot fails identically to a normal validation error, so a bot
cannot tell which check rejected it.
{%- else %}
A honeypot alone stops naive bots and not targeted ones. TODO: record the acceptance of that risk.
{%- endif %}
{%- else -%}
### Spam protection was NOT enabled — documented exception

**Context.** The security baseline requires bot protection on every public form.
**Decision.** This project was generated without it.
**Consequences.** Every public form is effectively an open relay for whoever finds it, and every
submission that sends mail costs the client's sending reputation. TODO: record who accepted this,
when, and on what grounds. This is a go-live finding until then.
{%- endif %}

### Uploads are validated on six axes, and personal files are never public

**Context.** The reference project this template came from had **zero validators on public file
uploads**, and stored them under a predictable path in a world-readable media directory — so
applicants' documents were enumerable by anyone who guessed the pattern.
**Decision.** Every upload field enforces all six of: a size limit; an extension allowlist (never a
denylist); content sniffing so the file's real type must match its extension; server-side
re-encoding of images, bounded against decompression bombs, with SVG never accepted on a public
field; a **generated** stored filename, with the original kept in a separate column for display
only; and storage {% if cookiecutter.media_storage == "filesystem" %}under `PRIVATE_MEDIA_ROOT`{% else %}in the separate private storage{% endif %} for anything containing personal data, served
only through a permission-checked view.
**Alternatives considered.** Trusting the browser-supplied content type and filename. Both are
attacker-controlled.
**Consequences.** Adding an upload field is more work than `FileField()`, deliberately. A field that
skips any of the six is a security finding, not a style preference. The private path means a file's
URL is not a credential.

### Content-Security-Policy with a per-request nonce, and no `unsafe-eval`

**Context.** A CSP containing `'unsafe-inline'` and `'unsafe-eval'` in `script-src` grants exactly
what CSP exists to deny.
**Decision.** `script-src` has no `'unsafe-inline'` and no `'unsafe-eval'`. Inline scripts carry a
per-request nonce: `{% raw %}<script nonce="{{ request.csp_nonce }}">{% endraw %}`.
**Alternatives considered.** Allowing inline scripts "temporarily". Temporary CSP relaxations
outlive everyone who agreed to them.
**Consequences.** A vendored library that requires `eval` cannot simply be dropped in; it is either
replaced or the exception is written down with a date. `style-src` still allows inline styles —
that is a **migration state, not a destination**. TODO: remove `'unsafe-inline'` from `style-src`
once the theme carries no inline style attributes.

### Every outgoing message goes through a logging mail layer, and is sent synchronously

**Context.** "The client says they never got the e-mail" is unanswerable without a record of what
was sent.
**Decision.** `django-post-office` wraps whichever real transport is configured. Every send is
recorded and visible in the administration interface. Delivery is **synchronous**{% if cookiecutter.task_queue == "none" %}, so there is no
queue worker and no `send_queued_mail` cron entry{% else %}, even though this project
has a queue{% endif %}.
{%- if cookiecutter.task_queue == "none" %}
**Alternatives considered.** Celery or a similar queue: a second process to deploy, monitor, restart
and forget on a new server, for a volume that does not need it.
**Consequences.** Nothing to keep alive, and nothing to forget when the site moves to a new server.
The cost is that a slow mail relay slows the request that triggered the send. If this project ever
sends bulk mail, revisit this decision rather than working around it.
{%- else %}
**Alternatives considered.** Enqueuing every send. Rejected as the default: a queued send turns "the
message was sent" into "the message was accepted for sending", and the failure then surfaces in a
worker log rather than in front of the person who triggered it. The queue is used only to **retry**
what an inline send could not deliver.
**Consequences.** A delivery failure is visible immediately. The cost is that a slow mail relay slows
the request that triggered the send. If this project ever sends bulk mail, revisit this decision
rather than working around it — bulk mail is the case the queue is actually for.
{%- endif %}

{% if cookiecutter.api != "none" -%}
### Django REST Framework, RFC 9457 errors, and rotating refresh tokens

**Context.** Every project inventing its own error shape means every integrator writes a new error
handler.
**Decision.** DRF, with `application/problem+json` (RFC 9457) as the single error envelope,
produced by `drf-standardized-errors` and a project formatter rather than a bespoke handler
(it is the established KUWAITNET package, covers every DRF exception path, and puts error
responses into the OpenAPI schema; its own default format is not RFC 9457, hence the formatter),
page-number pagination with a hard maximum of 100, deny-by-default permissions, and JWT access plus
rotating refresh tokens with the superseded token blacklisted.
**Alternatives considered.** django-ninja or FastAPI (a second framework in one process, and no
reuse of the project's existing permissions and admin); long-lived API keys (no rotation story).
**Consequences.** One error handler per client. Rotation means a client refreshing from two workers
at once will see one rejected — refresh through a single path. The blacklist table grows with every
refresh and needs the pruning job in [13-scheduled-tasks.md](13-scheduled-tasks.md).
Serializers declare explicit fields: `fields = "__all__"` silently publishes every field added to
the model later.
{%- endif %}

{% if cookiecutter.countries_app == "django_countries" -%}
### Countries come from the KUWAITNET fork of `django-countries`

**Context.** Every project needs a country field, and the country list a KUWAITNET site offers is
subject to a company policy. A policy expressed as a runtime filter is one forgotten `.exclude()`
away from not applying — which is what happened in the project this template came from, where the
same filter was copy-pasted into five forms and one copy had already lost a clause.
**Decision.** `django-countries` is installed from
`git+https://github.com/KUWAITNET/django-countries.git@main` — a public fork of
`SmileyChris/django-countries`, one commit ahead of upstream 9.0.0. The policy is applied to the
shipped **data**, so no queryset can reintroduce what it removes. `uv.lock` records the exact commit
even though the ref is a branch, so builds stay reproducible. There is no table and no import step:
the list works the moment `uv sync` finishes.
**Alternatives considered.** The PyPI package plus a runtime exclusion (the policy becomes a filter
someone can forget); the `cities_light` app (four models and a GeoNames import, for a project that
needs only a country field); a hand-written choices list (drifts, and nobody owns it).
**Consequences.** `COUNTRY_EXCLUDED_CODES` still exists and is normally **empty** — it is for
per-client exclusions on top of the shipped list, not for the company policy. Because this is a
fork, upstream security and data updates do not arrive automatically: rebasing it onto a new
upstream release is a named maintenance task, and the fork is a row in the project's third-party
register. Do not "fix" the `@main` ref by loosening the lock file. Every consumer goes through
`apps/core/countries.py`, so moving to the `cities` backend later is a change to that one module
plus a migration, not a change to every form.
{%- elif cookiecutter.countries_app == "cities" -%}
### Countries come from `cities_light`, with the selection policy in one queryset

**Context.** This project needs more than a country name: editor-toggleable countries, dial codes,
nationalities, translated names, or regions and cities.
**Decision.** `django-cities-light` with the concrete models moved into `apps/cities`
(`CITIES_LIGHT_APP_NAME = "cities"`), so the country table can carry an `is_active` flag and an
editor override for the name. The selection policy lives in exactly one place,
`Country.objects.selectable()`, and `apps/core/countries.py` is the only module the rest of the
project reaches it through.
**Alternatives considered.** The KUWAITNET fork of `django-countries` — no tables, no import step,
and the country-list policy already applied in the data, but no dial codes, no per-project
activation and nowhere to hang a demonym. That is the default for projects needing only a country
field.
**Consequences.** The country list is **empty until `manage.py cities_light` has imported the
GeoNames data**, which is a step on every environment, and four concrete models exist whether or not
the project ever imports a city. Nothing may re-implement the `selectable()` filter: anything that
needs "the countries a visitor may pick" calls the manager. The imported columns belong to the
importer, and a hand-edited value is overwritten by the next run.
{%- else -%}
### No country data — a deliberate omission

**Context.** This project was generated without a countries backend.
**Decision.** No form carries a country field, and the phone field is a single international input
validated with `phonenumbers` rather than a dial-code select plus a national number.
**Alternatives considered.** The KUWAITNET fork of `django-countries` (the default: a country field
and choices, with no tables and no import step); the `cities_light` app (for dial codes,
nationalities, translated names and regions).
**Consequences.** Adding countries later means choosing a backend and implementing
`apps/core/countries.py` for it — that one module is what would change, because nothing else imports
a country library directly. Until then a visitor must type the country calling code themselves, and
a submission records no country.
{%- endif %}

### Migrations are generated at bootstrap, not shipped by the template

**Context.** The model set depends on which options the project was generated with, so a shipped
migration would be wrong for most combinations.
**Decision.** The first migrations were generated by `make setup` when the project was created, and
are committed like any other code from that point on. CI runs
`makemigrations --check --dry-run` and fails on drift.
**Consequences.** The migration history starts at project generation and is this project's own. A
model change without a migration fails in CI rather than on the server.

{% if cookiecutter.languages == "en_ar" -%}
### Per-field translation, with both languages prefixed in the URL

**Context.** A bilingual site where one language is "the default" and the other is "the translation"
produces asymmetric URLs, one-sided search-engine alternates, and a language switcher that 404s.
**Decision.** Translation is per field — one row, translated columns — and both languages carry a
URL prefix (`/en/` and `/ar/`), so neither is privileged.
**Alternatives considered.** A separate content tree per language (double the editorial work, and
the two trees drift); leaving the default language unprefixed (asymmetric alternates).
**Consequences.** Adding a translatable field means registering it for translation and generating a
migration for the extra columns. The language switcher must resolve the *translated* address of the
current page and preserve the query string; a switcher that only swaps the URL prefix 404s the
moment a slug is translated, which is exactly what happened in the reference project.

### The sitemap sits outside the localised URL patterns

**Context.** In the reference project the sitemap was inside them, so it emitted whichever language
the request happened to negotiate — one language, non-deterministically.
**Decision.** One canonical sitemap path, listing every language's URLs, outside the localised
patterns.
**Consequences.** The sitemap is the same for every visitor and every crawler, which is the only
useful behaviour.
{%- endif %}

{% if cookiecutter.cache == "redis" -%}
### Redis as the shared cache

**Context.** Rate-limit{% if cookiecutter.api != "none" %} and throttle{% endif %} counters live in the Django cache. A per-process cache means each
gunicorn worker keeps its own counter, so three workers turn "10 per minute" into 30 per minute.
**Decision.** Redis, in every environment above development.
**Consequences.** One more service to run and monitor. The cache holds no personal data and is not
backed up: it is rebuilt on restart.
{%- else -%}
### The cache is per-process — a known limitation, not a decision to keep

**Context.** This project was generated with the local-memory cache.
**Decision.** Development uses `LocMemCache`.
**Consequences.** **A per-process cache is wrong for production.** Each gunicorn worker keeps its own
copy, so any counter kept in the cache is multiplied by the number of workers.
{%- if cookiecutter.rate_limiting == "yes" or cookiecutter.api != "none" %}
This project keeps rate-limit{% if cookiecutter.api != "none" %} and throttle{% endif %} counters there, so every stated limit is really that limit
times the worker count.
{%- endif %}
TODO: switch to Redis before go-live, or record the acceptance in writing with the multiplied limits
stated explicitly.
{%- endif %}

{% if cookiecutter.task_queue == "none" -%}
### No background task queue

**Context.** A queue is a second long-lived process: it has to be deployed, restarted on every
release, monitored, and remembered when the site moves to a new server. It earns that cost only when
there is work that genuinely cannot happen inside a request.
**Decision.** No queue. Scheduled work is cron entries and systemd timers
([13-scheduled-tasks.md](13-scheduled-tasks.md)); everything else happens in the request that asked
for it.
**Alternatives considered.** Huey on PostgreSQL — the cheapest real queue available here, since it
needs no new service — and Celery. Both were rejected for the same reason: nothing in this project's
scope needs them today.
**Consequences.** Nothing extra to keep alive, and a deploy cannot leave a stale worker running old
code. The cost is that anything slow runs inside the request. When the first genuinely slow or
retryable piece of work appears — a report to generate, an outbound integration that must survive a
timeout, bulk mail — the answer is to add a queue deliberately, not to move the work into a
management command triggered by an HTTP request.

{% elif cookiecutter.task_queue == "huey" -%}
### Huey for background tasks, on {% if cookiecutter.huey_backend == "postgres" %}PostgreSQL{% elif cookiecutter.huey_backend == "redis" %}Redis{% else %}SQLite{% endif %}

**Context.** This project has work that must happen outside a request and on a schedule — the audit
retention job at minimum. The choice was not "queue or no queue" but *how much machinery* that work
justifies.
**Decision.** Huey, with one consumer process that runs both the queue and the periodic schedule.
{%- if cookiecutter.huey_backend == "postgres" %}
Storage is **the application's own PostgreSQL database** (four tables, created by
`manage.py migrate`).
{%- elif cookiecutter.huey_backend == "redis" %}
Storage is **Redis**, on a different database number from the cache so that flushing the cache
cannot empty the queue.
{%- else %}
Storage is **SQLite**, in a file on the application host.
{%- endif %}
**Alternatives considered.** Celery: it brings routing, priorities, multiple queues, chains and
groups, and mature monitoring — none of which this project needs — and costs a broker, a worker and
a separate beat process, three things to run instead of one. Cron alone: no retries, no queue, and
every job becomes a crontab line that exists on one server.
{%- if cookiecutter.huey_backend == "postgres" %}
Redis storage: faster, and it keeps queue churn out of the database, but it is a service to run,
monitor and persist, and the queue then falls outside the database backup. Choose it when queue
writes are measurably a load on PostgreSQL — not before.
{%- endif %}
**Consequences.**
{%- if cookiecutter.huey_backend == "postgres" %}
**No new infrastructure at all.** The queue is backed up with the database, survives a restart
because PostgreSQL does, and there is nothing extra to patch. The cost is queue traffic on the
primary database — real, but small at this project's volume, and measurable before it matters.
{%- elif cookiecutter.huey_backend == "redis" %}
Queue contents are **lost on a Redis restart** unless persistence is tuned (`appendonly yes`), and
the queue is not in the database backup. Both are acceptable only while every task is safe to lose.
{%- else %}
**This is a development configuration.** SQLite storage does not survive multiple worker processes
or a move to a second machine, and it contradicts the PostgreSQL-only rule in the standards.
TODO: switch to the PostgreSQL storage before go-live — it needs no new service — or record the
acceptance in writing.
{%- endif %}
One consumer process must be running and **must be restarted by every deploy**; a deploy that misses
it leaves the previous release's code executing tasks against a migrated database, silently. See
[07-deployment.md](07-deployment.md). If this project later needs task routing, priorities or
several queues scaled independently, that is the point to reconsider Celery — not sooner.

{% elif cookiecutter.task_queue == "celery" -%}
### Celery for background tasks, over {% if cookiecutter.task_broker == "redis" %}Redis{% elif cookiecutter.task_broker == "rabbitmq" %}RabbitMQ{% else %}Amazon SQS{% endif %}

**Context.** This project has background work that needs more than a cron entry, and enough of it to
justify real queue machinery.
**Decision.** Celery, with a worker and exactly one beat process, over
{% if cookiecutter.task_broker == "redis" %}**Redis** as the broker, on a different database number from the cache{% elif cookiecutter.task_broker == "rabbitmq" %}**RabbitMQ**{% else %}**Amazon SQS**{% endif %}.
**Alternatives considered.** Huey: one process instead of three, and on PostgreSQL it needs no new
service at all — but no routing, no priorities, no multiple queues, no chains or groups, and far
less monitoring. It was rejected because this project needs at least one of those; if that stops
being true, Celery is the more expensive answer.
{%- if cookiecutter.task_broker == "redis" %}
RabbitMQ: durable, acknowledged and dead-letterable, at the cost of another server to run, monitor,
back up and upgrade. SQS: the same durability with nothing to operate, but no Celery remote control
or events, and no broker-level priorities.
{%- elif cookiecutter.task_broker == "rabbitmq" %}
Redis: simpler, and already running for the cache, but **not a durable message broker** — a restart
can drop queued tasks unless persistence is tuned, and there are no publisher confirms or
dead-letter queues. SQS: comparable durability with no server to operate, at the cost of Celery's
remote control and events, which is how `celery inspect` and Flower work.
{%- else %}
RabbitMQ: the same durability guarantees, plus priorities and working remote control — at the cost
of a server to run, patch, monitor, back up and upgrade. Redis: simplest, already running for the
cache, but not durable.
{%- endif %}
**Consequences.**
{%- if cookiecutter.task_broker == "redis" %}
**Redis is not a durable message broker.** An unpersisted restart drops whatever was queued, there
are no publisher confirms and no dead-letter queue. Every task in this project must therefore be
safe to lose and safe to run twice. The moment a task appears that a customer has been told already
happened — a payment reconciled, an invoice issued — this decision has to be revisited rather than
patched around.
{%- elif cookiecutter.task_broker == "rabbitmq" %}
Durable queues, acknowledgements, publisher confirms and dead-lettering, so a task that was accepted
is not lost to a restart. The cost is a broker to run: its own host, monitoring, upgrade path and
backup. A RabbitMQ that hits its disk or memory alarm stops accepting publishes, and the symptom is
a web request that hangs — so its alarms belong in [09-monitoring.md](09-monitoring.md), not in
somebody's memory.
{%- else %}
Durable and redundant, with no broker server to run, patch, back up or monitor, and IAM instead of
broker credentials. Three costs to keep in view: **`celery inspect` and Flower do not work** (SQS
carries no remote control or events), there are **no broker-level priorities**, and the **visibility
timeout is a correctness setting** — SQS redelivers any message not deleted within it, so a task
that outruns `AWS_SQS_VISIBILITY_TIMEOUT` runs twice. A system check enforces the last one.
Development runs against a local Redis instead, because there is no SQS to run locally; that
difference is acceptable for a queue but the SQS-specific behaviour must be exercised on UAT before
go-live.
{%- endif %}
Tasks are acknowledged **after** they complete (`task_acks_late`), so a killed worker returns the
task to the queue rather than losing it — which means every task must be safe to run twice. Two
processes must be running and **must be restarted by every deploy**; a deploy that misses the worker
leaves the previous release's code executing tasks against a migrated database, silently. See
[07-deployment.md](07-deployment.md).

### The Celery schedule lives in the repository, not in the database

**Context.** `django-celery-beat` is the usual choice, and it puts the schedule in database rows that
an administrator can edit without a deploy.
**Decision.** The stock beat scheduler, with the schedule defined in `CELERY_BEAT_SCHEDULE` in
`settings/base.py`.
**Alternatives considered.** `django-celery-beat`. Two reasons against it, either sufficient. Its
current release declares `Django<6.1`, so it cannot be installed alongside {% if cookiecutter.django_version == "6.1" %}the Django this project
runs{% else %}Django 6.1, which this project will move to{% endif %}. And a schedule in database rows exists on exactly one server, appears in no code
review, and is lost with the machine — the same failure this documentation warns about for a crontab
that was never committed.
**Consequences.** Changing when a job runs is a deploy. Beat keeps its "last run" state in the file
named by `CELERY_BEAT_SCHEDULE_FILENAME`, which must be writable and must survive a deploy: delete
it and every periodic task is treated as never run, so they all fire at once on the next start.
Revisit this if the client genuinely needs to retime jobs themselves, and if upstream has by then
supported the Django release in use.

{% endif -%}
{% if cookiecutter.sentry != "yes" -%}
### No error monitoring — a known limitation

**Context.** This project was generated without Sentry.
**Consequences.** An unhandled exception appears in the application log and nowhere else. Nobody is
alerted, and nobody can tell whether an error is new or affects one user or all of them.
TODO: add it, or record the acceptance of the gap.
{%- endif %}

### Makefile as the task runner, and no JavaScript build step

**Context.** A deploy runbook whose commands need a tool installed first is a runbook that fails on a
fresh server at 22:00.
**Decision.** `make` — present on every server and CI image. There is no Node.js build step: CSS and
JavaScript are served as authored{% if cookiecutter.asset_pipeline == "compressor" %}, then concatenated and minified by django-compressor, which is
Python and needs no toolchain{% endif %}, with hashed filenames for cache busting.
**Consequences.** Every command in this documentation works over SSH with nothing to install. Adding
a front-end build step later adds a toolchain to every server and every CI image; that is a decision
to take deliberately, not a convenience to slip in.

### Static files are hashed and served from {% if cookiecutter.static_storage == "cloud" %}the object store{% else %}the application{% endif %}; media is not committed

**Context.** Hand-stamped `?v=` query strings are forgotten, and committed media makes a repository
that takes minutes to clone.
**Decision.** Static files get content-hashed names through a manifest at `collectstatic` time and
are served by {% if cookiecutter.static_storage == "cloud" %}the object store, from a `static/` prefix that is the only publicly readable
part of the bucket{% else %}WhiteNoise{% endif %}. Editorial images and documents go through the administration interface
into the media {% if cookiecutter.media_storage == "filesystem" %}directories{% else %}store{% endif %} and are never committed.
**Consequences.** `collectstatic` must run under the production settings module at deploy time, or
the manifest will not match the running application and every asset 404s.{% if cookiecutter.static_storage == "cloud" %} It also needs the
bucket credentials, which is why it is a deploy step rather than an image build step — build-time
credentials end up in a layer.{% endif %}

### Media is stored {% if cookiecutter.media_storage == "filesystem" %}on the application server's disk{% else %}in an object store, in two separate storages{% endif %}

{% if cookiecutter.media_storage == "filesystem" -%}
**Context.** Uploaded files have to live somewhere with a backup story, and personal data must never
be reachable from a public URL.
**Decision.** `MEDIA_ROOT` on local disk for editorial media, and a separate `PRIVATE_MEDIA_ROOT`
that the web server never maps to a URL, served only through a permission-checked view.
**Alternatives considered.** An object store (S3, GCS, Azure Blob), which the template also
supports: it removes the media disk from the sizing conversation, survives losing the server, and
scales without thought. It was not chosen here because it adds a cloud SDK, a set of credentials, a
bucket policy that must be right, and per-GB egress on every private download — cost that only pays
for itself once media volume or availability requirements justify it.
**Consequences.** The media disk grows and must be watched ([03-infrastructure.md](03-infrastructure.md)),
and the nightly media `rsync` in [08-backup-restore.md](08-backup-restore.md) is a real, separate
backup job that has to be monitored. Moving to a bucket later is a settings change plus a one-off
copy: `STORAGES` is the only place that names the backend, and no model or view knows the difference.
{%- else -%}
**Context.** Uploaded files have to live somewhere with a backup story, and personal data must never
be reachable from a public URL. A media disk on the application server is one more thing to size,
monitor and lose with the server.
**Decision.** Media goes to {% if cookiecutter.media_storage == "s3" %}Amazon S3{% elif cookiecutter.media_storage == "gcs" %}Google Cloud Storage{% else %}Azure Blob Storage{% endif %} through `django-storages`, as **two storages,
not one**: a public storage for editorial media, and a private storage for anything a visitor
uploads about themselves. The bucket is not public-read; no public ACL is ever sent, and every URL
the application builds is signed and expires. Private files are streamed through the
permission-checked view by default, never redirected to.
**Alternatives considered.**
*One bucket, world-readable, "the URLs are unguessable".* This is the reference project's failure
verbatim: applicant CVs sat under a public media root with the filenames their owners gave them.
Unguessable is not a permission.
*Signed URLs for private media by default.* Cheaper — the bytes never touch a worker — but a signed
URL, once issued, is valid for its whole lifetime to anyone holding it: after logout, after the
permission is revoked, after it is forwarded or logged by a proxy. It is available behind
`PRIVATE_MEDIA_SIGNED_URLS` for projects serving large private files, as a per-project decision with
the expiry set as low as the download tolerates.
*Local disk.* Simpler, and the right answer for a small site; see the alternative branch of this
decision in the template.
**Consequences.** The server needs no media disk, and losing the server loses no files. In exchange:
a cloud SDK and a credential to rotate; a bucket policy that is now the thing standing between
private uploads and the internet, verified by hand and recorded in
[03-infrastructure.md](03-infrastructure.md); and egress billed twice on every private download,
because the permission check runs on every byte. **"Backup" also changes meaning** — from a nightly
`rsync` to bucket versioning plus lifecycle rules, which live in the same account as the data and
therefore protect against a mistake but not against losing the account. Read
[08-backup-restore.md](08-backup-restore.md) before agreeing an RPO.
{%- endif %}

### {% if cookiecutter.asset_pipeline == "compressor" %}django-compressor, with offline compression{% else %}No asset pipeline: WhiteNoise is the whole story{% endif %}

**Context.** `django-compressor` appears in 25 of 56 modern KUWAITNET projects, so the team knows it
and reaches for it by habit. Habit is not a reason. What it actually buys has narrowed: WhiteNoise
already gzips and brotlis every static file and gives it a content-hashed name, this template ships
no SASS or LESS and no Node build step, and under HTTP/2 concatenating files to save round trips is
worth far less than it was when the habit formed.
{% if cookiecutter.asset_pipeline == "compressor" -%}
**Decision.** `django-compressor` is enabled, with `COMPRESS_OFFLINE = True` in production. The
compress blocks live in `templates/includes/styles.html` and `templates/includes/scripts.html`.
**Alternatives considered.** No pipeline at all — the template's default, and the right answer for a
site with a handful of hand-written stylesheets. A Node toolchain — more capable, and it puts npm on
every server and every CI image for the rest of the project's life.
**Consequences.** **`manage.py compress --force` must run on every deploy, after `collectstatic`.**
With `COMPRESS_OFFLINE` on, a block that was never compiled raises rather than rendering, so a deploy
path that skips the step ships a broken site — the classic and entirely avoidable footgun. It is
wired into the Dockerfile and into the runbook in [07-deployment.md](07-deployment.md); any new
deploy path must carry it too. Nothing inside a compress block may vary per request: the offline
manifest is keyed on the rendered block, so an inline nonce or a per-user value would never match.
Turn it **off** again if the SASS/LESS theme it was enabled for is dropped; keeping a compile step
for two static files is pure deploy risk.
{%- else -%}
**Decision.** No asset pipeline. WhiteNoise's `CompressedManifestStaticFilesStorage` does the
compression and the cache busting, and the CSS and JavaScript are served as authored.
**Alternatives considered.** `django-compressor`, available in this template as
`asset_pipeline=compressor`. Turn it on when the project grows a **SASS or LESS theme and no Node
toolchain** — `COMPRESS_PRECOMPILERS` compiles it at deploy time in Python, which is exactly the gap
WhiteNoise does not fill. Do **not** turn it on to minify two hand-written stylesheets, or to
concatenate files that HTTP/2 already multiplexes: `COMPRESS_OFFLINE` then adds a mandatory
`manage.py compress --force` to every deploy, and a deploy path that forgets it ships a site with no
CSS.
**Consequences.** One fewer build step, one fewer dependency and one fewer way for a deploy to
half-work. If a theme with a preprocessor arrives later, enabling compressor is a settings change
plus a template include plus a runbook line — record it here on the day it happens.
{%- endif %}

### Tests run against PostgreSQL, with a coverage floor of 60 % on `apps/`

**Context.** A suite that runs on SQLite passes tests the production database would fail.
**Decision.** pytest with pytest-django, against PostgreSQL, with `--cov-fail-under=60` as a hard CI
failure.
**Consequences.** The floor may rise; it does not fall. Deleting or skipping a test to get a green
build is a defect. Coverage flags are deliberately not in `addopts`, so a single-test debug run
stays fast.

---

## Known limitations

Written down deliberately. This is the difference between a client who plans and a client who is
surprised.

- **Designed volume.** TODO: state the traffic, content volume and concurrent editor count this
  system was designed and tested for, and what would need work beyond that. A number nobody has
  measured is not a limitation, it is a guess.
- **No background job processing.** Anything slow happens inside the request that triggered it. A
  long-running import or a bulk mail send would need a queue, which this project does not have.
- **Search.** TODO: state what search covers and what it does not{% if cookiecutter.stack == "wagtail" %}. Site search uses the database
  backend, which is adequate for a site of this size and does not offer relevance tuning, typo
  tolerance or faceting{% endif %}.
- **`style-src` still allows inline styles.** A migration state, not a destination; see the CSP
  decision above.
{%- if cookiecutter.cache != "redis" %}
- **The cache is per-process.** See the decision above; this is the most consequential item on this
  list.
{%- endif %}
{%- if cookiecutter.sentry != "yes" %}
- **No error monitoring.**
{%- endif %}
{%- if cookiecutter.use_2fa != "yes" %}
- **No second factor on administrative accounts.**
{%- endif %}
{%- if cookiecutter.spam_protection == "none" %}
- **No bot protection on public forms.**
{%- endif %}
{%- if cookiecutter.rate_limiting != "yes" %}
- **No login lockout and no rate limits.**
{%- endif %}
{%- if cookiecutter.countries_app == "cities" %}
- **The country list is empty until the GeoNames import has run** on that environment. A fresh
  database renders an empty country dropdown, which reads as a bug and is not one.
{%- elif cookiecutter.countries_app == "django_countries" %}
- **The country list comes from a fork**, so upstream data and security updates arrive only when
  somebody rebases it. See the decision above.
{%- else %}
- **No country data.** Forms carry no country field, and a phone number must be typed with its
  country calling code.
{%- endif %}
{%- if cookiecutter.media_storage != "filesystem" %}
- **Private downloads are proxied, so their bandwidth is billed twice** — bucket to application, then
  application to visitor — and a large download holds a gunicorn worker for its duration. That is the
  price of checking the permission on every byte. `PRIVATE_MEDIA_SIGNED_URLS` trades it away; read
  the decision above before doing so.
- **Media backup lives in the same cloud account as the media.** Bucket versioning protects against
  a deletion or an overwrite, not against losing the account. See
  [08-backup-restore.md](08-backup-restore.md).
{%- endif %}
{%- if cookiecutter.asset_pipeline == "compressor" %}
- **Every deploy path must run `manage.py compress --force`.** Offline compression means a page whose
  block was never compiled raises instead of rendering. The Dockerfile and the runbook do it; a
  hand-rolled deploy script is where this gets forgotten.
{%- endif %}
- **Log correlation.** Log lines carry no request identifier, so relating a user's report to a
  specific request is manual. See [09-monitoring.md](09-monitoring.md).
- TODO: anything deferred to a later phase, with the phase named.
- TODO: any accepted risk, with who accepted it and when.
- TODO: any component known to need attention by a given date.
