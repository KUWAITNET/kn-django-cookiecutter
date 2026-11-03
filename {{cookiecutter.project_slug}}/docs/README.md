# {{ cookiecutter.project_name }} — technical documentation

**Client:** {{ cookiecutter.client_name }}
**Production domain:** {{ cookiecutter.domain_name }}
**Maintained by:** {{ cookiecutter.author }} ({{ cookiecutter.author_email }})

This directory is the complete technical documentation for {{ cookiecutter.project_name }}. It is
versioned with the code, so a change to the system and a change to its documentation travel
together in the same review. Documentation assembled in the week before handover is documentation
that is wrong.

Completed, this set gives {{ cookiecutter.client_name }} everything needed to **operate, maintain,
migrate or further develop** the site independently — including with a developer who has never
spoken to {{ cookiecutter.author }}.

## Reading order

| File | Contents | Read it when |
|---|---|---|
| [01-overview.md](01-overview.md) | What the system is, its components, its environments | First, always |
| [02-stack.md](02-stack.md) | Exact versions and their vendor support dates | Planning an upgrade |
| [03-infrastructure.md](03-infrastructure.md) | Server sizing, packages, ports, filesystem layout | Building a server |
| [04-environment-variables.md](04-environment-variables.md) | Every configuration value the app reads | The site will not start |
| [05-database.md](05-database.md) | Data model, migrations, retention | Changing the schema |
| [06-installation.md](06-installation.md) | Empty machine to running site | Onboarding, rebuild |
| [07-deployment.md](07-deployment.md) | The release runbook and rollback | Every release |
| [08-backup-restore.md](08-backup-restore.md) | Backup schedule and a tested restore | Before you need it |
| [09-monitoring.md](09-monitoring.md) | Alerts, logs, the five likely failures | Something is broken |
{%- if cookiecutter.stack == "wagtail" %}
| [10-cms-guide.md](10-cms-guide.md) | Operating the site as a content editor | Training editors |
{%- endif %}
| [11-roles-permissions.md](11-roles-permissions.md) | Who can do what, and who holds each role | Adding a person |
{%- if cookiecutter.api != "none" %}
| [12-api.md](12-api.md) | The HTTP interface other systems use | Integrating |
{%- endif %}
| [13-scheduled-tasks.md](13-scheduled-tasks.md) | Everything that runs without a person | Migrating a server |
| [14-decisions.md](14-decisions.md) | Why the system is the way it is, and its limits | Before you "improve" something |
| [15-developer-handover.md](15-developer-handover.md) | Onboarding the next developer | Day one |
| [security-pass.md](security-pass.md) | The signed pre-go-live security record | Before go-live |

A developer joining the project reads 01, 15, 06, then whichever of 05 / 07 / 12 their first task
touches. An administrator taking over the server reads 03, 04, 07, 08, 09, 13.

## The state of this set

This documentation was generated with the project, so the parts that are determined by the code —
the stack, the settings split, the environment variables, the deploy runbook, the backup commands,
the scheduled tasks, the decision log — are already filled in and correct as of generation.

Everything that only the project team can know is marked **`TODO:`**. Search for it:

```bash
grep -rn "TODO:" docs/
uv run python tools/check_standards.py --verbose   # the same search, as a reported rule (KN007)
```

The standards checker counts these on every run and in CI, so the number is visible from the first
week rather than discovered at handover. It is a warning, not a failure — an unfinished document
during development is normal, and an unfinished document at handover is not.

A `TODO:` left in this set at handover is an incomplete delivery. Sections 03, 04 and 07 are
written the first time the project is deployed, not the week before handover. Section 14 is written
the day a decision is made, while the reasoning is still in someone's head.

## Rules for this directory

- Markdown only, one topic per file, filenames never change (they are referenced from the
  KUWAITNET handover checklist and from client deliverables).
- A pull request that changes behaviour changes the affected document in the same commit.
- Never write a real secret value here. Write the format and name the credential store instead.
- Never paste a table-and-column listing of the database. It is wrong within weeks, and a reader
  who finds one error stops trusting the whole set. See [05-database.md](05-database.md) for the
  commands that generate a current picture instead.
- No "last updated" lines and no version numbers in the text; git owns that.

## Related KUWAITNET standards

This project implements the KUWAITNET web standards. Where this documentation states a rule, the
standard states why it exists and applies to every project:

- Security baseline — the controls in [security-pass.md](security-pass.md).
- Environments and releases — the model behind [07-deployment.md](07-deployment.md).
- Backup and disaster recovery — behind [08-backup-restore.md](08-backup-restore.md).
- Monitoring and logging — behind [09-monitoring.md](09-monitoring.md).
- Testing and QA — the coverage floor enforced in CI.
{%- if cookiecutter.api != "none" %}
- API standard — behind [12-api.md](12-api.md).
{%- endif %}
{%- if cookiecutter.languages == "en_ar" %}
- Internationalisation and RTL standard — the bilingual rules used throughout.
{%- endif %}
- Performance standard, SEO standard, project structure.

TODO: replace this list with links to the standards repository location used by
{{ cookiecutter.client_name }}'s copy of the deliverable, or attach the standards as an appendix.
