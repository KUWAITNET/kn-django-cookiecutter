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
{%- if cookiecutter.task_queue != "none" %}
- [ ] Any task whose arguments changed in this release is still callable with the **old** signature.
      During the deploy, old and new code are both in flight against the same queue.
{%- endif %}
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
{%- if cookiecutter.asset_pipeline == "compressor" %}
# Offline compression. NOT optional and NOT reorderable: production has
# COMPRESS_OFFLINE on, so a block that was never compiled raises on every page
# that renders it. It runs after collectstatic because it resolves asset paths
# through the manifest collectstatic has just written.
uv run python manage.py compress --force
{%- endif %}
{%- if cookiecutter.languages == "en_ar" %}
uv run python manage.py compilemessages
{%- endif %}

# 4. Migrations, BEFORE the restart. Never after it, never concurrently, never on worker start.
uv run python manage.py migrate --noinput

# 5. Full restart. A reload (SIGHUP) is not enough after 'uv sync' changed a dependency.
sudo systemctl restart {{ cookiecutter.project_slug }}-gunicorn
sudo systemctl status {{ cookiecutter.project_slug }}-gunicorn --no-pager
{%- if cookiecutter.task_queue != "none" %}

# 6. Restart the background {% if cookiecutter.task_queue == "huey" %}consumer{% else %}worker AND beat{% endif %}. NOT optional, and not a tidy-up step:
#    see "The worker is a second process" below.
{%- if cookiecutter.task_queue == "huey" %}
sudo systemctl restart {{ cookiecutter.project_slug }}-worker
sudo systemctl status {{ cookiecutter.project_slug }}-worker --no-pager
{%- else %}
sudo systemctl restart {{ cookiecutter.project_slug }}-worker {{ cookiecutter.project_slug }}-beat
sudo systemctl status {{ cookiecutter.project_slug }}-worker {{ cookiecutter.project_slug }}-beat --no-pager
{%- endif %}
{%- endif %}
```

Numbered step titles, for the release ticket: 0 snapshot, 1 fetch the approved commit, 2
dependencies from the lockfile, 3 static{% if cookiecutter.asset_pipeline == "compressor" %}, compression{% endif %}{% if cookiecutter.languages == "en_ar" %} and translations{% endif %}, 4 migrations, 5 restart{% if cookiecutter.task_queue != "none" %}, 6 restart the background {% if cookiecutter.task_queue == "huey" %}consumer{% else %}worker and beat{% endif %}{% endif %}, then verify.

Why each of those is written the way it is:

- `--noinput` on `migrate` is mandatory. An interactive prompt on a remote deploy hangs the session
  with the schema half-applied.
- `collectstatic` sets `DJANGO_SETTINGS_MODULE` explicitly. Run under the wrong settings module it
  writes a manifest that does not match the running application, and every hashed asset 404s.
{%- if cookiecutter.asset_pipeline == "compressor" %}
- `compress --force` is the step people leave out of a hand-rolled deploy script, and leaving it out
  is the classic way to ship a site with no styling. `--force` recompiles rather than trusting a
  cached manifest that may describe the previous release.
{%- endif %}
{%- if cookiecutter.static_storage == "cloud" %}
- `collectstatic` writes to the object store, so the deploy account needs the bucket credentials.
  This is also why the container image does not run it at build time: build-time credentials end up
  in a layer.
{%- endif %}
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

{% if cookiecutter.static_storage == "cloud" -%}
# 2. Build the image. Static files are NOT built inside it: they go to the object
#    store, and giving the build bucket credentials would bake them into a layer.
docker compose build web

# 2b. Static files, into the bucket. A deploy step, so the credentials come from
#     the environment and stay out of the image.
docker compose run --rm web python manage.py collectstatic --noinput
{%- if cookiecutter.asset_pipeline == "compressor" %}
# Offline compression. NOT optional and NOT reorderable: production has
# COMPRESS_OFFLINE on, so a block that was never compiled raises on every page
# that renders it. It runs after collectstatic because it resolves asset paths
# through the manifest collectstatic has just written.
docker compose run --rm web python manage.py compress --force
{%- endif %}
{% else -%}
# 2. Build the image. Static files{% if cookiecutter.asset_pipeline == "compressor" %}, the compressed asset bundles{% endif %}{% if cookiecutter.languages == "en_ar" %} and translations{% endif %} are built
#    inside it, under the production settings, so the manifest matches what runs.
docker compose build web
{% endif %}
# 3. Migrations, BEFORE the new container serves traffic. They are deliberately not in
#    the image CMD: two containers starting at once would race, and a failed migration
#    must stop a deploy rather than crash-loop a container.
docker compose run --rm web python manage.py migrate --noinput

# 4. Replace the running container{% if cookiecutter.task_queue != "none" %}S. The {% if cookiecutter.task_queue == "huey" %}worker is{% else %}worker and beat are{% endif %} listed here on purpose:
#    'up -d web' alone leaves {% if cookiecutter.task_queue == "huey" %}it{% else %}them{% endif %} running the previous image. See "The worker is a
#    second process" below{% endif %}.
{%- if cookiecutter.task_queue == "none" %}
docker compose up -d web
docker compose ps
docker compose logs --tail=50 web
{%- elif cookiecutter.task_queue == "huey" %}
docker compose up -d web worker
docker compose ps
docker compose logs --tail=50 web worker
{%- else %}
docker compose up -d web worker beat
docker compose ps
docker compose logs --tail=50 web worker beat
{%- endif %}
```

Why each of those is written the way it is:

- `--noinput` on `migrate` is mandatory. An interactive prompt on a remote deploy hangs the session
  with the schema half-applied.
- Migrations are a deploy step, not a container start step. Putting them in `CMD` means every
  restart re-runs them and a failure crash-loops instead of stopping the release.
{%- if cookiecutter.asset_pipeline == "compressor" %}
- `compress --force` is the step people leave out of a hand-rolled deploy script, and leaving it out
  is the classic way to ship a site with no styling. `--force` recompiles rather than trusting a
  cached manifest that may describe the previous release.{% if cookiecutter.static_storage != "cloud" %} It is wired into the Dockerfile, so the
  image cannot be built without it.{% else %} With static files in a bucket, `collectstatic` needs
  credentials the build must not have, so both steps live in the deploy above rather than in the
  image.{% endif %}
{%- endif %}
- The image is built from a tag, not from a working copy with local edits.
- The deploy account has no git push credentials and no database superuser rights.
{%- endif %}
{%- if cookiecutter.task_queue != "none" %}

## The {% if cookiecutter.task_queue == "huey" %}worker is a second process{% else %}worker and beat are second and third processes{% endif %}

{% if cookiecutter.task_queue == "huey" -%}
The task consumer runs the same code as the web application, in a **separate long-lived process**.
It is started once and then stays up for weeks.
{%- else -%}
The Celery worker and beat run the same code as the web application, in **separate long-lived
processes**. They are started once and then stay up for weeks.
{%- endif %}

**A deploy that restarts the web process and not the {% if cookiecutter.task_queue == "huey" %}consumer{% else %}worker{% endif %} leaves the old code running your
tasks.** This is a real and common outage, not a theoretical one, and it is nasty because everything
looks fine: the site serves the new release, the deploy log is green, CI was green, and nobody gets
an error. Meanwhile the {% if cookiecutter.task_queue == "huey" %}consumer{% else %}worker{% endif %} is executing last release's code against a database the
new release has already migrated. The usual shapes it takes:

- The migration added a non-null column. The old task's `INSERT` omits it and every run fails —
  in a process nobody is watching.
- The migration removed or renamed a field the old task still reads, so the task raises on every
  message and the queue backs up silently.
- The task's logic changed — a corrected VAT rate, a fixed e-mail template, a tightened permission
  check — and the old version keeps producing the wrong output for as long as the process lives.
  Nothing fails. The results are simply wrong, and they are wrong for days, because the process is
  only noticed the next time somebody reboots the machine.

So the restart is a numbered step in the runbook above, not a note at the end. Two rules follow
from it:

1. **Restart {% if cookiecutter.task_queue == "huey" %}it{% else %}both{% endif %} in the same deploy, immediately after the web process** — never "later", never
   "when convenient".
2. **Write tasks so that both versions can be in flight at once.** During any deploy there is a
   window where a message enqueued by the new code is picked up by the old worker, or the reverse.
   The same expand-and-contract discipline that applies to migrations ([05-database.md](05-database.md))
   applies to task signatures: add arguments with defaults, do not remove or reorder them in the
   same release that starts using them.
{%- if cookiecutter.deploy_target == "gunicorn_nginx" %}

TODO: create the systemd unit{% if cookiecutter.task_queue == "celery" %}s{% endif %} and commit {% if cookiecutter.task_queue == "celery" %}them{% else %}it{% endif %} alongside this document. {% if cookiecutter.task_queue == "huey" %}The unit runs
`manage.py run_huey` as the `{{ cookiecutter.project_slug }}` user, with the same environment file as gunicorn,
`Restart=always`, and `WantedBy=multi-user.target` so it comes back after a reboot.{% else %}One unit runs
`celery -A {{ cookiecutter.project_slug }} worker`, the other `celery -A {{ cookiecutter.project_slug }} beat`, both as the
`{{ cookiecutter.project_slug }}` user with the same environment file as gunicorn, `Restart=always`, and
`WantedBy=multi-user.target` so they come back after a reboot.

**Exactly one beat process per environment.** Two schedulers on one schedule make every periodic
task fire twice; if the application ever runs on two servers, beat belongs on one of them only.{% endif %}

A worker that is not under a process manager is a worker that disappears at the next reboot, and
the first sign of it is a scheduled job that stopped months ago.
{%- endif %}
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
{%- if cookiecutter.stack == "wagtail" %}
curl -sS -o /dev/null -w '%{http_code}\n' https://{{ cookiecutter.domain_name }}/{{ cookiecutter.django_admin_url_prefix }}/
{%- endif %}
# Must be 404: the admin is not at /admin/
curl -sS -o /dev/null -w '%{http_code}\n' https://{{ cookiecutter.domain_name }}/admin/
```

- [ ] {% if cookiecutter.deploy_target == "gunicorn_nginx" %}`systemctl status`{% else %}`docker compose ps`{% endif %} shows the new release running.
{%- if cookiecutter.task_queue != "none" %}
- [ ] The background {% if cookiecutter.task_queue == "huey" %}consumer is{% else %}worker and beat are{% endif %} running, and {% if cookiecutter.task_queue == "huey" %}its start time is{% else %}their start times are{% endif %} **after** this deploy — not
      before it. A start time that predates the deploy means old code is still running tasks.
- [ ] The {% if cookiecutter.task_queue == "huey" %}consumer's{% else %}worker's{% endif %} startup log lists every expected task. A task missing from that list will
      never run.
- [ ] One task has actually executed since the restart (enqueue one, or wait for a scheduled run and
      read the log). A process that started is not the same as a process that is working.
{%- endif %}
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
{%- if cookiecutter.asset_pipeline == "compressor" %}
- [ ] The page's stylesheet URL points at `/static/CACHE/css/...`. A page that renders at all proves
      the offline manifest was built; a page whose CSS URL is the uncompressed source means
      `COMPRESS_ENABLED` is off, not that compression succeeded.
{%- endif %}
{%- if cookiecutter.media_storage != "filesystem" %}
- [ ] An image uploaded through the admin renders on the site, so writes to the bucket work under
      the deployed credentials — not only under the ones on a laptop.
- [ ] A private file still downloads through `/private-media/<path>` for a permitted account, and
      403s for everyone else.
{%- endif %}
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
{%- if cookiecutter.asset_pipeline == "compressor" %}
uv run python manage.py compress --force
{%- endif %}
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
{%- if cookiecutter.static_storage == "cloud" %}
docker compose run --rm web python manage.py collectstatic --noinput
{%- if cookiecutter.asset_pipeline == "compressor" %}
docker compose run --rm web python manage.py compress --force
{%- endif %}
{%- endif %}
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
