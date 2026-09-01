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
only; and storage under `PRIVATE_MEDIA_ROOT` for anything containing personal data, served only
through a permission-checked view.
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
recorded and visible in the administration interface. Delivery is **synchronous**, so there is no
queue worker and no `send_queued_mail` cron entry.
**Alternatives considered.** Celery or a similar queue: a second process to deploy, monitor, restart
and forget on a new server, for a volume that does not need it.
**Consequences.** Nothing to keep alive, and nothing to forget when the site moves to a new server.
The cost is that a slow mail relay slows the request that triggered the send. If this project ever
sends bulk mail, revisit this decision rather than working around it.

{% if cookiecutter.api != "none" -%}
### Django REST Framework, RFC 9457 errors, and rotating refresh tokens

**Context.** Every project inventing its own error shape means every integrator writes a new error
handler.
**Decision.** DRF, with `application/problem+json` (RFC 9457) as the single error envelope,
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
JavaScript are served as authored, with hashed filenames for cache busting.
**Consequences.** Every command in this documentation works over SSH with nothing to install. Adding
a front-end build step later adds a toolchain to every server and every CI image; that is a decision
to take deliberately, not a convenience to slip in.

### Static files are hashed and served from the application; media is not committed

**Context.** Hand-stamped `?v=` query strings are forgotten, and committed media makes a repository
that takes minutes to clone.
**Decision.** Static files get content-hashed names through a manifest at `collectstatic` time and
are served by WhiteNoise. Editorial images and documents go through the administration interface
into the media directories and are never committed.
**Consequences.** `collectstatic` must run under the production settings module at deploy time, or
the manifest will not match the running application and every asset 404s.

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
- **Log correlation.** Log lines carry no request identifier, so relating a user's report to a
  specific request is manual. See [09-monitoring.md](09-monitoring.md).
- TODO: anything deferred to a later phase, with the phase named.
- TODO: any accepted risk, with who accepted it and when.
- TODO: any component known to need attention by a given date.
