{% if cookiecutter.stack == "wagtail" -%}
# 10. Operating the site: guide for content editors

Written for a content editor, not a developer. If a step here does not match what you see on screen,
the site has changed and this guide has not — tell the technical contact in
[15-developer-handover.md](15-developer-handover.md).

TODO: add screenshots for the first sign-in and for anything with more than three steps. Screenshots
age, and they are still worth it.

## Signing in

1. Go to `https://{{ cookiecutter.domain_name }}/{{ cookiecutter.admin_url_prefix }}/`.
2. Enter your username and password.
{%- if cookiecutter.use_2fa == "yes" %}
3. Enter the six-digit code from your authenticator application.

Every account needs a second factor. On your first sign-in you will be asked to scan a code with an
authenticator application on your phone, and you will be shown a set of recovery codes.

**Save the recovery codes somewhere that is not your phone.** If you lose the phone and have no
recovery codes, nobody can restore your access — an administrator has to remove the second factor
from your account and you enrol again from scratch.

If you lose your device: contact an administrator immediately. Do not share your codes with anyone,
and never let two people use one account.
{%- else %}

TODO: this project was generated without two-factor authentication. Record the exception in
[14-decisions.md](14-decisions.md) and tell editors what protects their account instead.
{%- endif %}

{% if cookiecutter.rate_limiting == "yes" -%}
After several failed attempts your account is locked for about thirty minutes. This is deliberate.
Wait, or ask an administrator to clear it — do not keep trying.
{%- endif %}

## Where things are

| Area | What it is for |
|---|---|
| Pages | The page tree. Everything the public sees lives here |
| Images | Uploaded photographs and graphics |
| Documents | PDFs and other downloadable files |
| Snippets | Reusable pieces of content that are not pages |
{%- if cookiecutter.newsletter == "yes" %}
| Newsletter | Subscribers and sending |
{%- endif %}
| Settings | Site-wide configuration. Change nothing here without asking a developer |
| Reports → Site history | Who changed what, and when |
| Redirects | Send an old address to a new one |
{%- if cookiecutter.forms_suite == "yes" or cookiecutter.notifications_app == "yes" %}
| The Django administration at `/{{ cookiecutter.admin_url_prefix }}/django/` | Records with no editor interface: submitted forms, the e-mail log |
{%- endif %}

## The content types

TODO: this is the section editors actually use. List every page type in the site and, for each one:
what it is for, where it appears publicly, which fields are required, and which fields affect search
results or the preview shown when the page is shared on social media.

| Page type | Used for | Appears | Required fields | Affects search or sharing |
|---|---|---|---|---|
| TODO: | | | | |

## Publishing

1. **Draft.** A new or edited page is a draft until you publish it. Drafts are not public.
2. **Preview.** Use the preview panel to see the page as a visitor would. A preview link is not a
   public link and cannot be shared with someone who does not have an account.
3. **Publish.** The page goes live immediately.
4. **Schedule.** Set a go-live date to publish automatically, or an expiry date to remove the page
   automatically. Scheduling depends on a job running on the server
   ([13-scheduled-tasks.md](13-scheduled-tasks.md)) — if scheduled pages stop appearing, that job has
   stopped, and it is a technical fault rather than something you did wrong.

TODO: state who is allowed to publish, and whether an approval step applies to this site.

## Editing safely

- Every save creates a revision. You can compare any two revisions and revert to an earlier one.
- **Unpublishing removes a page from the site; it does not delete it.** Prefer unpublishing.
- Deleting is different: it removes the page and its child pages. If you delete something by
  accident, tell the technical contact the same day — the further back it has to be recovered, the
  more other work is lost with it.
- Changing the address (slug) of a live page breaks every existing link to it and damages its search
  ranking. Use the Redirects tool instead of editing the address of a live page.

## Media guidelines

These numbers are not preferences. This is where sites become slow.

- Photographs: no more than **2000 pixels** on the long edge. The site generates the smaller sizes
  it needs automatically.
- Keep a photograph under **500 KB**, and a full-width banner under **1 MB**.
- JPEG for photographs. PNG only for graphics with flat colour or transparency.
- Never upload an image straight from a camera, or a designer's export, without resizing it. Never
  upload a print file.
- Give every image meaningful alternative text in the language of the page. It is what a
  screen-reader user hears and what search engines read.
- Documents: PDF, under **10 MB**, with a descriptive filename and no personal data in the file's
  properties.
- SVG files are not accepted. They can contain scripts, so they are excluded from uploads by design;
  ask a developer if you need a vector graphic.

Uploads are checked when you submit them: the size, the extension, and the file's actual content.
A file renamed to `.pdf` that is not a PDF is rejected. That is the check working, not a bug.
{% if cookiecutter.languages == "en_ar" %}
## The bilingual rule

Every page exists in Arabic and English.

- A page published in one language only leaves visitors on the other language facing a gap, and it
  damages search results for that language.
- Translate through the translation fields on the same page, not by creating a separate unlinked
  page. This is what keeps the language switcher working — a separate page is not connected to its
  counterpart and the switcher cannot find it.
- **Do not paste English text into an Arabic field as a placeholder.** Publish nothing rather than
  publish the wrong language.
- TODO: record the agreed conventions for numbers, dates and names on Arabic pages.
{% endif %}
## What editors must not change without a developer

- The address (slug) of a live page. Use Redirects.
- Anything under Settings.
- Anything in the Django administration area that is not covered by this guide.
- Any field whose purpose you are not sure of. Ask; it takes a minute and saves an incident.

## Getting help

TODO: name the contact, the channel, and the hours.

When reporting a problem, include: the address of the page, what you did, what you expected, what
happened instead, the time it happened, and a screenshot. "The site is broken" costs a day of
guessing.
{%- else -%}
# 10. Operating the site: guide for content editors

Written for a content editor, not a developer. If a step here does not match what you see on screen,
the site has changed and this guide has not — tell the technical contact in
[15-developer-handover.md](15-developer-handover.md).

TODO: add screenshots for the first sign-in and for anything with more than three steps.

## Signing in

1. Go to `https://{{ cookiecutter.domain_name }}/{{ cookiecutter.admin_url_prefix }}/`.
2. Enter your username and password.
{%- if cookiecutter.use_2fa == "yes" %}
3. Enter the six-digit code from your authenticator application.

Every account needs a second factor. On your first sign-in you will be asked to scan a code with an
authenticator application on your phone, and you will be shown a set of recovery codes.

**Save the recovery codes somewhere that is not your phone.** If you lose the phone and have no
recovery codes, an administrator has to remove the second factor from your account and you enrol
again from scratch.
{%- endif %}

{% if cookiecutter.rate_limiting == "yes" -%}
After several failed attempts your account is locked for about thirty minutes. This is deliberate.
Wait, or ask an administrator to clear it.
{%- endif %}

## What editors maintain

TODO: list every record type an editor is expected to create or change, and for each one: what it is
for, where it appears publicly, which fields are required, and which fields affect search results or
the preview shown when a page is shared.

| Record type | Used for | Appears | Required fields | Affects search or sharing |
|---|---|---|---|---|
| TODO: | | | | |

TODO: state how a record is taken off the public site — a status field, an active flag, or an
unpublish action — and make clear that this is not the same as deleting it.

## Editing safely

- Prefer deactivating or unpublishing over deleting. Deleting is not reversible from the interface.
- Every change is recorded in the admin action log, so "who changed this?" has an answer.
- Changing the address of a live page breaks every existing link to it and damages its search
  ranking. Ask a developer to add a redirect rather than editing the address.
- TODO: record how an accidental edit is recovered on this project, and how far back that is
  possible.

## Media guidelines

These numbers are not preferences. This is where sites become slow.

- Photographs: no more than **2000 pixels** on the long edge.
- Keep a photograph under **500 KB**, and a full-width banner under **1 MB**.
- JPEG for photographs. PNG only for graphics with flat colour or transparency.
- Never upload an image straight from a camera, or a designer's export, without resizing it.
- Give every image meaningful alternative text in the language of the page.
- Documents: PDF, under **10 MB**, with a descriptive filename and no personal data in the file's
  properties.
- SVG files are not accepted. They can contain scripts, so they are excluded from uploads by design.

Uploads are checked when you submit them: the size, the extension, and the file's actual content.
A file renamed to `.pdf` that is not a PDF is rejected. That is the check working, not a bug.
{% if cookiecutter.languages == "en_ar" %}
## The bilingual rule

Every piece of public content exists in Arabic and English.

- Content published in one language only leaves visitors on the other language facing a gap, and it
  damages search results for that language.
- Fill in both language fields on the same record. Do not create a second, unlinked record for the
  other language — the language switcher cannot find it.
- **Do not paste English text into an Arabic field as a placeholder.** Publish nothing rather than
  publish the wrong language.
- TODO: record the agreed conventions for numbers, dates and names in Arabic.
{% endif %}
## What editors must not change without a developer

- The address of a live page.
- Any configuration record.
- Anything in the administration area not covered by this guide.
- Any field whose purpose you are not sure of. Ask; it takes a minute and saves an incident.

## Getting help

TODO: name the contact, the channel, and the hours.

When reporting a problem, include: the address of the page, what you did, what you expected, what
happened instead, the time it happened, and a screenshot.
{%- endif %}
