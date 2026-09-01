# 5. Database structure

There is deliberately no table-and-column listing here. A hand-written one is wrong within weeks,
and a reader who finds one error stops trusting the whole document. This page tells you how to
generate a current picture from the live schema, and then documents only what a diagram cannot show.

## Generating a current picture

```bash
# Full schema, no data, no ownership - the reference document
pg_dump --schema-only --no-owner --no-privileges "$DATABASE_URL" > schema.sql

# Table sizes, largest first - shows what is actually growing
psql "$DATABASE_URL" -c "
  SELECT relname AS table,
         pg_size_pretty(pg_total_relation_size(relid)) AS total
  FROM pg_catalog.pg_statio_user_tables
  ORDER BY pg_total_relation_size(relid) DESC
  LIMIT 25;"

# The models Django knows about, and their tables
uv run python manage.py inspectdb --include-views > /dev/null   # sanity check only
uv run python manage.py showmigrations
```

Store the generated `schema.sql` outside the repository with its generation date and the command
that produced it. Do not commit it: a committed schema dump becomes the stale copy this page exists
to avoid.

TODO: if an entity-relationship diagram is required as a deliverable, add `django-extensions` and
Graphviz to the development dependency group and record the exact `graph_models` invocation here.
Generate the diagram at handover, attach it with its date, and do not maintain it by hand.

## The parts a diagram cannot show

TODO: replace each bullet below with the real answer for this project. This is the section with
actual value; an empty one makes the whole set look like a form nobody filled in.

{% if cookiecutter.languages == "en_ar" -%}
- **Translated fields.** Translation is per-field, not per-row: a translatable `title` becomes
  `title_en` and `title_ar` columns on the same table, registered in each app's `translation.py`.
  The plain `title` attribute is a descriptor that resolves to the active language with a fallback,
  so `SELECT title` in raw SQL will not behave the way the ORM does. TODO: list the models that
  carry translated fields.
{%- endif %}
{%- if cookiecutter.stack == "wagtail" %}
- **Content lives in a page tree.** Pages are rows in a shared tree table plus one table per page
  type; a page's data is split across both, so a single page is never a single row. Deleting from
  the page table by hand corrupts the tree. Use the admin or the ORM.
- **Revisions.** Every save creates a revision record holding a serialised copy of the page. This is
  what makes editorial changes reversible, and it is also why the revision table is usually among
  the largest in the database. TODO: record the revision-trimming policy and where it runs.
- **Images and renditions.** Uploaded images are stored once; each display size is generated on
  first use and cached as a rendition row plus a file on disk. Deleting rendition rows is safe —
  they regenerate. Deleting the original is not.
{%- else %}
- **Editorial ownership.** TODO: name the models editors own, and how a change to one is made
  reversible (revision history, soft deletion, or an audit trail), so an accidental edit is not a
  restore-from-backup event.
{%- endif %}
{%- if cookiecutter.countries_app == "yes" %}
- **Country and city reference data** is imported, not authored. Rows carry an active flag so
  editors can control which countries appear in selection lists without deleting reference data
  that existing records point at. Never delete a country row; deactivate it.
{%- endif %}
- **The e-mail log.** `django-post-office` records every message the application sends, with its
  status. This table grows steadily and is a source of personal data (recipient addresses, and
  message bodies). See the retention section below.
{%- if cookiecutter.rate_limiting == "yes" %}
- **Lockout records.** `django-axes` writes an auditable record of failed logins and lockouts. It
  grows with attack traffic, not with usage, so it can grow quickly and unpredictably.
{%- endif %}
{%- if cookiecutter.api != "none" %}
- **Blacklisted refresh tokens.** Refresh tokens rotate, and the superseded token is blacklisted.
  The blacklist table grows with every refresh and must be pruned; nothing prunes it automatically.
  TODO: record the pruning job in [13-scheduled-tasks.md](13-scheduled-tasks.md).
{%- endif %}
- TODO: any relationship deliberately not enforced at database level, and why.
- TODO: any denormalised or cached column, and what refreshes it.
- TODO: any table expected to grow quickly, with its archiving plan.
- TODO: any table that looks unused but is not.

## Migrations

Migrations are the only way this schema changes. That is a rule, not a preference.

- **Never change the schema by hand on production.** A hand-made column is invisible to
  `makemigrations`, so the next migration is generated against a model of the database that does not
  match the database.
- A migration ships in the same commit as the model change that needs it. CI runs
  `manage.py makemigrations --check --dry-run` and fails on drift — this is the single most
  valuable schema check the project has.
- **A migration merged to `main` is never edited.** Fix forward with a new migration.
- Take a database backup before applying migrations. Every release does this
  ([07-deployment.md](07-deployment.md)); the backup's age is recorded in the release ticket.
- `RunPython` operations use `apps.get_model("<label>", "<Model>")`, never a direct model import,
  and supply either a reverse operation or an explicit `migrations.RunPython.noop` with a comment
  saying why the change cannot be reversed.
- A migration expected to take more than about 30 seconds against production volumes is run
  separately inside the maintenance window, after being timed against a restored production-sized
  copy — not as part of the normal release.

### Migrations are generated, not shipped

This project's first migrations were generated at bootstrap (`make setup` runs `makemigrations`),
because the model set depends on the options the project was created with. They are committed like
any other code from that point on.

```bash
make migrations      # create migrations for model changes
make migrate         # apply them
uv run python manage.py showmigrations          # what is applied where
uv run python manage.py sqlmigrate <app> <n>    # the SQL a migration will run - read it
```

Read `sqlmigrate` output before deploying any migration that touches a large table. A column added
`NOT NULL` with a default rewrites the table and holds a lock for the duration.

### Changing a column without downtime

Adding is safe; removing and renaming are not. Both are done as expand and contract, across at least
two releases:

1. **Expand** — add the new nullable column, deploy.
2. **Backfill** — populate it in batches through a data migration or a management command. Never one
   unbounded `UPDATE` on a large table.
3. **Switch reads** — deploy the code that reads the new column, and leave it running for at least
   one full release cycle.
4. **Contract** — drop the old column in a later release.

The destructive step never ships in the same release as the code that stopped using the column. If
it does, a code rollback leaves the application reading a column that no longer exists.

### Irreversible migrations

TODO: list every migration in this project that cannot be reversed, with the reason. A rollback plan
that assumes a reversible migration and meets an irreversible one becomes a restore from backup.

## Personal data and retention

TODO: complete this table before handover. It is the answer to "what personal data does this system
hold, and for how long?" — a question that will be asked.

| Table / model | Personal data held | Retention | What deletes it |
|---|---|---|---|
| Users | Name, e-mail, hashed password | Life of the account | Manual removal when a person leaves |
| E-mail log (`post_office`) | Recipient addresses, message bodies | 90 days | TODO: scheduled purge — record it in [13](13-scheduled-tasks.md) |
{%- if cookiecutter.rate_limiting == "yes" %}
| Access attempt log (`axes`) | IP addresses, usernames attempted | TODO: | TODO: |
{%- endif %}
{%- if cookiecutter.newsletter == "yes" %}
| Newsletter subscribers | E-mail address, subscription state | Until unsubscribed | Unsubscribe link, then a purge of unsubscribed rows |
{%- endif %}
{%- if cookiecutter.forms_suite == "yes" %}
| Contact submissions | Name, e-mail, phone, message, any attachment | TODO: | TODO: |
{%- endif %}
| Admin action log | Who changed what, and when | At least 12 months | Pruning job, with the retention period visible in its arguments |
| TODO: | | | |

Files that accompany these records — attachments, documents, anything a person uploaded about
themselves — live under `PRIVATE_MEDIA_ROOT`, not `MEDIA_ROOT`. Deleting the database row does not
delete the file; a retention job must delete both.

## Squashing before handover

Before handover, squash migrations on a dedicated branch: `makemigrations --check` must be green and
the full suite must pass against a database built from scratch. Remove the replaced migration files
only after every live environment has applied past the squash point.
