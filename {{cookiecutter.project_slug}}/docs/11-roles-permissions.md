# 11. User roles and permissions

Roles are how {{ cookiecutter.client_name }} controls risk after handover. An editor who cannot
delete a page cannot accidentally delete a page.

## The roles

TODO: complete the "Held by" column and add every project-specific role. Review it at handover and
whenever someone joins or leaves.

{% if cookiecutter.stack == "wagtail" -%}
| Role | Can do | Cannot do | Held by |
|---|---|---|---|
| Administrator (superuser) | Everything, including user management, settings and deletion | — | TODO: |
| Moderator | Create, edit, publish and unpublish content in all sections; manage images and documents | Manage users, change settings | TODO: |
| Editor | Create and edit content; submit it for publishing | Publish, delete, manage users | TODO: |
| TODO: project-specific role | | | |

The Editor and Moderator groups exist by default. Editors are never made superusers: a superuser
bypasses every permission check, which makes the whole table above decorative.
{%- else -%}
| Role | Can do | Cannot do | Held by |
|---|---|---|---|
| Administrator (superuser) | Everything, including user management and deletion | — | TODO: |
| Staff (group: TODO:) | Create and edit the records listed in [10-cms-guide.md](10-cms-guide.md) | Manage users, delete records, change configuration | TODO: |
| TODO: project-specific role | | | |

Permissions are Django groups, granted per model and per action (add, change, delete, view). Assign
people to groups, never permissions to individuals — an individual permission is invisible in every
review and is the one nobody remembers to remove.

Staff are never made superusers: a superuser bypasses every permission check, which makes the whole
table above decorative.
{%- endif %}

## Rules that apply to every account

- **One account per person. No shared logins.** A shared account means the audit log cannot answer
  "who did this?", which is the only question that matters after a mistake.
{%- if cookiecutter.use_2fa == "yes" %}
- **Two-factor authentication is required for every administrative account** and is enforced by the
  application, not by policy. It is disabled only in the automated test settings.
{%- else %}
- TODO: two-factor authentication is **not** enforced on this project. Record the exception in
  [14-decisions.md](14-decisions.md) with the compensating control, or enable it.
{%- endif %}
- Minimum password length is 12 characters, and passwords are checked against Django's common
  password list and similarity to the account's own details. Passwords are hashed with Argon2.
{%- if cookiecutter.rate_limiting == "yes" %}
- Repeated failed logins lock the account and IP combination for 30 minutes, and every attempt is
  recorded. Lockout is a different control from a rate cap: it produces an auditable record.
{%- endif %}
- Sessions expire after 12 hours by default. Cookies are `HttpOnly`, `SameSite=Lax`, and `Secure` in
  production.
- **Removal is immediate when someone leaves**, not at the end of the month. Deactivate the account
  the same day.

## Authorisation beyond the role table

Two things editors and administrators cannot see, but which matter to whoever reviews this system:

- Permission is checked **per object**, not only per view. Being allowed to view a type of record
  does not grant access to every record of that type.
- Files containing personal data are served through a view that checks permission on every request.
  A private file's URL is not a credential; guessing it is not enough.

## Adding and removing a person

{% if cookiecutter.stack == "wagtail" -%}
1. Sign in as an administrator and open the users section of the administration interface.
2. Create the account with the person's own e-mail address. Never re-use an existing account.
3. Assign exactly one group from the table above. Do not tick the superuser box.
{%- if cookiecutter.use_2fa == "yes" %}
4. Have the person sign in and enrol their second factor immediately, before they are given anything
   to do.
{%- endif %}
5. Record them in the "Held by" column above.
{%- else -%}
1. Sign in as an administrator and open the users section at
   `https://{{ cookiecutter.domain_name }}/{{ cookiecutter.admin_url_prefix }}/`.
2. Create the account with the person's own e-mail address. Never re-use an existing account.
3. Tick "staff status" and assign exactly one group from the table above. Do not tick "superuser".
{%- if cookiecutter.use_2fa == "yes" %}
4. Have the person sign in and enrol their second factor immediately, before they are given anything
   to do.
{%- endif %}
5. Record them in the "Held by" column above.
{%- endif %}

To remove someone: deactivate the account rather than deleting it, so the audit log keeps its
attribution. Then remove them from this document, and check whether they also held any credential in
the secrets store — if so, rotate it.

## Where administrative actions are recorded

{% if cookiecutter.stack == "wagtail" -%}
Reports → Site history in the administration interface records content and configuration changes,
and every page keeps its revision history. Retained for at least 12 months.
{%- else -%}
The admin action log records who changed what, and when, for every model registered in the
administration interface. Retained for at least 12 months; any pruning job must carry that retention
period in its arguments so the policy is visible.
{%- endif %}
{% if cookiecutter.rate_limiting == "yes" %}
Failed logins and lockouts are recorded separately and are visible in the administration interface.
{% endif %}
The e-mail log records every message the system sent, to whom, and whether it was delivered.

## Before go-live

- [ ] Every default, demonstration, vendor and temporary account is removed.
- [ ] Every remaining account belongs to a named person.
{%- if cookiecutter.use_2fa == "yes" %}
- [ ] Every remaining account has enrolled a second factor.
{%- endif %}
- [ ] No account has superuser rights that does not need them.
- [ ] The staging basic-authentication credentials are rotated or retired.
- [ ] This table is complete and has been reviewed with {{ cookiecutter.client_name }}.
