# 7. Deployment procedure

This is the runbook, not a description of one. Where a step is a command, the command is here.

**Deploy target:** {% if cookiecutter.deploy_target == "gunicorn_nginx" %}gunicorn behind nginx, managed by systemd{% else %}docker compose{% endif %}.
**Expected duration:** 3 to 5 minutes for a routine release.
**Downtime:** {% if cookiecutter.deploy_target == "gunicorn_nginx" %}a two- to five-second gap at the restart{% else %}a short gap while the container is recreated{% endif %}, unless a long migration is involved.

## Branches and what deploys where

| Branch | Deploys to | Merged by |
|---|---|---|
| `feature/<ticket>-<slug>` | Nothing; CI only | The author |
| `develop` | Development | The author, after review |
| `staging` | Staging / UAT | The project lead |
| `main` | Production | The project lead, after UAT sign-off |

Promotion is `feature/*` → `develop` → `staging` → `main`, in that order, by merge or fast-forward.
Never by cherry-picking a subset of a branch: what was tested on staging must be exactly what
reaches production.

`main` and `staging` are protected — no direct pushes, no force pushes, green CI and one approving
review required.

A hotfix branches from `main` as `hotfix/<ticket>-<slug>`, is verified on development, is merged to
`main`, and is then **merged back down into `staging` and `develop` in the same working session**.
A hotfix that is not back-merged is a bug that returns with the next release.

## Releases and tags

One annotated tag per production deploy, on `main`, from the reviewed commit:

```bash
git tag -a v1.4.0 -m "Release 1.4.0"
git push origin v1.4.0
```

`vMAJOR.MINOR.PATCH`. MAJOR is a breaking change to a published contract, MINOR is new
functionality, PATCH is a fix.{% if cookiecutter.sentry == "yes" %} The tag name is the value of `SENTRY_RELEASE` on the server, so an error
can be attributed to a release.{% endif %} Content changes made by editors are not releases and are not tagged.

`CHANGELOG.md` carries one section per release, dated, under **Added**, **Changed**, **Fixed** and
**Security**, written at merge time rather than reconstructed from `git log` afterwards. Anything the
deploy needs a human to do — a new environment variable, a new scheduled job, a manual data step —
goes under a **Deploy notes** subheading, because that is where the person doing the deploy will
look.

TODO: create `CHANGELOG.md` at the first release and keep it in the repository root.

## Who authorises a deploy

TODO: name the project lead, the client contact who signs off UAT, and who may deploy to production.

Default maintenance window: 20:00 to 23:00 Kuwait time on a working day. Never after 14:00 on a
Thursday, and never on the last working day before a public holiday. A deploy with visible downtime
is announced at least three working days in advance, with the start time, expected duration and a
named contact. Emergency security fixes are exempt from the notice period; the client is told the
same working day.

At least one engineer stays available for two hours after a production deploy.

## Pre-deploy checklist

- [ ] CI is green on the exact commit being deployed, including the coverage gate.
- [ ] QA sign-off recorded for this build.
- [ ] Client UAT sign-off recorded (releases, not hotfixes).
- [ ] The release is tagged, and `CHANGELOG.md` includes any Deploy notes.
- [ ] Every new environment variable is in `.env.example` **and** set on the server.
- [ ] No destructive migration in this release; expand-and-contract respected
      ([05-database.md](05-database.md)).
- [ ] Any migration expected to exceed about 30 seconds has been identified and scheduled.
- [ ] **A database backup exists, its age is known, and it is less than 24 hours old.** Take a fresh
      one now if not ([08-backup-restore.md](08-backup-restore.md)).
- [ ] The rollback plan is written in the release ticket.
- [ ] The window is agreed and the client is notified.
- [ ] Third-party changes (DNS, mail relay, payment gateway) are done in advance, not during.

## The runbook

{% if cookiecutter.deploy_target == "gunicorn_nginx" -%}
TODO: replace `<host>`, the deploy user and the paths with the real values, and confirm the systemd
unit name.

```bash
# 0. Take the pre-deploy snapshot (see 08-backup-restore.md) and note its timestamp
#    in the release ticket.

ssh deploy@<host>
cd /srv/{{ cookiecutter.project_slug }}

# 1. Fetch exactly the approved commit. Deploy a tag, never a branch.
git fetch --all --tags
git checkout v1.4.0

# 2. Dependencies, from the lockfile only. Never a bare 'uv sync'.
uv sync --frozen --no-dev

export DJANGO_SETTINGS_MODULE={{ cookiecutter.project_slug }}.settings.production

# 3. Static files{% if cookiecutter.languages == "en_ar" %} and translations{% endif %}, built under the production settings so the
#    manifest matches what runs.{% if cookiecutter.languages == "en_ar" %} .mo files are built here, never trusted from git.{% endif %}
uv run python manage.py collectstatic --noinput
{%- if cookiecutter.languages == "en_ar" %}
uv run python manage.py compilemessages
{%- endif %}

# 4. Migrations, BEFORE the restart. Never after it, never concurrently, never on worker start.
uv run python manage.py migrate --noinput

# 5. Full restart. A reload (SIGHUP) is not enough after 'uv sync' changed a dependency.
sudo systemctl restart {{ cookiecutter.project_slug }}-gunicorn
sudo systemctl status {{ cookiecutter.project_slug }}-gunicorn --no-pager
```

Numbered step titles, for the release ticket: 0 snapshot, 1 fetch the approved commit, 2
dependencies from the lockfile, 3 static{% if cookiecutter.languages == "en_ar" %} and translations{% endif %}, 4 migrations, 5 restart, then verify.

Why each of those is written the way it is:

- `--noinput` on `migrate` is mandatory. An interactive prompt on a remote deploy hangs the session
  with the schema half-applied.
- `collectstatic` sets `DJANGO_SETTINGS_MODULE` explicitly. Run under the wrong settings module it
  writes a manifest that does not match the running application, and every hashed asset 404s.
- `uv sync --frozen` installs exactly what the lockfile pins. A bare `uv sync` may re-resolve and
  install something nobody tested.
- The deploy account has no git push credentials and no database superuser rights.
{%- else -%}
TODO: replace `<host>` and the paths with the real values.

```bash
# 0. Take the pre-deploy snapshot (see 08-backup-restore.md) and note its timestamp
#    in the release ticket.

ssh deploy@<host>
cd /srv/{{ cookiecutter.project_slug }}

# 1. Fetch exactly the approved commit. Deploy a tag, never a branch.
git fetch --all --tags
git checkout v1.4.0

# 2. Build the image. Static files{% if cookiecutter.languages == "en_ar" %} and translations{% endif %} are built inside it, under the
#    production settings, so the manifest matches what runs.
docker compose build web

# 3. Migrations, BEFORE the new container serves traffic. They are deliberately not in
#    the image CMD: two containers starting at once would race, and a failed migration
#    must stop a deploy rather than crash-loop a container.
docker compose run --rm web python manage.py migrate --noinput

# 4. Replace the running container.
docker compose up -d web
docker compose ps
docker compose logs --tail=50 web
```

Why each of those is written the way it is:

- `--noinput` on `migrate` is mandatory. An interactive prompt on a remote deploy hangs the session
  with the schema half-applied.
- Migrations are a deploy step, not a container start step. Putting them in `CMD` means every
  restart re-runs them and a failure crash-loops instead of stopping the release.
- The image is built from a tag, not from a working copy with local edits.
- The deploy account has no git push credentials and no database superuser rights.
{%- endif %}

## Post-deploy verification

Run all of these. A deploy is not finished until they pass.

```bash
{% if cookiecutter.frontend != "api_only" %}{% if cookiecutter.languages == "en_ar" %}curl -sS -o /dev/null -w '%{http_code} %{time_total}s\n' https://{{ cookiecutter.domain_name }}/en/
curl -sS -o /dev/null -w '%{http_code} %{time_total}s\n' https://{{ cookiecutter.domain_name }}/ar/
{% else %}curl -sS -o /dev/null -w '%{http_code} %{time_total}s\n' https://{{ cookiecutter.domain_name }}/
{% endif %}curl -sS https://{{ cookiecutter.domain_name }}/robots.txt
{% endif %}curl -sS -o /dev/null -w '%{http_code}\n' https://{{ cookiecutter.domain_name }}/healthz
curl -sS -o /dev/null -w '%{http_code}\n' https://{{ cookiecutter.domain_name }}/{{ cookiecutter.admin_url_prefix }}/
# Must be 404: the admin is not at /admin/
curl -sS -o /dev/null -w '%{http_code}\n' https://{{ cookiecutter.domain_name }}/admin/
```

- [ ] {% if cookiecutter.deploy_target == "gunicorn_nginx" %}`systemctl status`{% else %}`docker compose ps`{% endif %} shows the new release running.
{%- if cookiecutter.frontend != "api_only" %}
- [ ] Homepage returns 200{% if cookiecutter.languages == "en_ar" %} in both languages{% endif %}, plus one form page and one detail page.
{%- endif %}
- [ ] `/healthz` returns 200.
- [ ] Admin login works{% if cookiecutter.use_2fa == "yes" %}, the second factor is still enforced,{% endif %} and `/admin/` still returns 404.
{%- if cookiecutter.forms_suite == "yes" or cookiecutter.newsletter == "yes" %}
- [ ] A test form submission succeeds and the notification e-mail arrives.
{%- endif %}
{%- if cookiecutter.sentry == "yes" %}
- [ ] Sentry shows the new release tag, and no new unhandled exception in the first 15 minutes.
{%- endif %}
{%- if cookiecutter.api != "none" %}
- [ ] `/api/v1/` responds and the schema UI is **not** exposed in production.
{%- endif %}
- [ ] Static assets load; the CSS hash changed if it should have.
- [ ] Error rate and response time are back at pre-deploy levels after 30 minutes.
- [ ] `CHANGELOG.md` matches what was actually deployed.

## Rollback

**Every release has a written answer to "how do we undo this" before it is deployed, recorded in the
release ticket.** Target for a code-only rollback: under five minutes. That is why releases should
be small.

### Code only, no migration in the release

{% if cookiecutter.deploy_target == "gunicorn_nginx" -%}
```bash
cd /srv/{{ cookiecutter.project_slug }}
git checkout <previous-tag>
uv sync --frozen --no-dev
export DJANGO_SETTINGS_MODULE={{ cookiecutter.project_slug }}.settings.production
uv run python manage.py collectstatic --noinput
{%- if cookiecutter.languages == "en_ar" %}
uv run python manage.py compilemessages
{%- endif %}
sudo systemctl restart {{ cookiecutter.project_slug }}-gunicorn
```
{%- else -%}
```bash
cd /srv/{{ cookiecutter.project_slug }}
git checkout <previous-tag>
docker compose build web
docker compose up -d web
```
{%- endif %}

### A migration has already run

- If expand-and-contract was followed, the migration is additive and the previous code still works
  against the new schema. **Roll back the code and leave the schema alone.**
- If the migration is additive and genuinely reversible, and only then:

```bash
{% if cookiecutter.deploy_target == "docker_compose" %}docker compose run --rm web python manage.py migrate <app> <last_good_migration>{% else %}DJANGO_SETTINGS_MODULE={{ cookiecutter.project_slug }}.settings.production \
  uv run python manage.py migrate <app> <last_good_migration>{% endif %}
```

- If the migration was destructive, or data has already been transformed, **do not reverse-migrate.**
  Escalate, put the site into maintenance, restore from backup
  ([08-backup-restore.md](08-backup-restore.md)) and reconcile post-backup writes by hand.

### What a rollback does not undo

An e-mail that was sent. A file that was written. A webhook that was delivered. A payment that was
taken. A search engine that already crawled the broken page. Say so in the incident note rather than
discovering it later.

Within one working day of any rollback, write a note in the release ticket: what failed, why staging
did not catch it, and which test now covers it.

## First go-live only

In addition to everything above:

- [ ] Basic authentication removed from the production hostname.
- [ ] Production `robots.txt` serves real rules and points at the sitemap; `Disallow: /` is gone
      from production and still present on staging.
- [ ] `X-Robots-Tag: noindex` removed from production responses.
- [ ] HSTS live at the agreed max-age; TLS renewal automated and verified.
{%- if cookiecutter.frontend != "api_only" %}
- [ ] Sitemap submitted; canonical URLs verified{% if cookiecutter.languages == "en_ar" %} in both languages{% endif %}.
{%- endif %}
{%- if cookiecutter.analytics == "ga4_gtm" %}
- [ ] Analytics IDs set on production only, and empty everywhere else.
{%- endif %}
- [ ] Backups configured and the first restore test completed
      ([08-backup-restore.md](08-backup-restore.md)).
- [ ] Uptime monitoring and alerting live, with the correct recipients
      ([09-monitoring.md](09-monitoring.md)).
- [ ] Every secret rotated and handed over ([04-environment-variables.md](04-environment-variables.md)).
- [ ] [security-pass.md](security-pass.md) signed with no open Critical or High finding.

## Release log

TODO: keep one row per production release. When something breaks, the first question is always
"what changed, and when?".

| Date | Tag | Deployed by | Migrations | Notes |
|---|---|---|---|---|
| | | | | |
