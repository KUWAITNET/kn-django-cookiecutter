# Security pass — {{ cookiecutter.project_name }}

The signed record of the pre-go-live security pass. The KUWAITNET go-live checklist references this
file: it is the evidence that the security baseline was applied to this project, not merely
available to it.

**Run it against staging, configured exactly as production will be** — production settings, real
content, TLS on, the same reverse proxy. Re-run it after any Critical or High finding is fixed.

This is not a substitute for an independent penetration test. Testing at that level is scoped and
priced separately.

TODO: this record is unsigned. Complete it before go-live.

## 1. Automated checks

| # | Check | Command or tool | Pass criterion | Result |
|---|---|---|---|---|
| 1 | Django deployment configuration | `make check-deploy` | **Zero** warnings under production settings | TODO: |
| 2 | Known-vulnerable dependencies | `make audit` (`pip-audit` against `uv.lock`) | No Critical or High, or a documented time-boxed exception | TODO: |
| 3 | Static security analysis | `make lint` (ruff `S` rules) and `make security` (bandit) | Clean, or a per-finding `# nosec` with a reviewed justification | TODO: |
| 4 | Dynamic scan | ZAP baseline, authenticated and unauthenticated | No Critical or High alerts; Medium triaged with a written decision | TODO: |
| 5 | Security response headers | A headers scanner against staging | CSP, HSTS, nosniff, frame-ancestors, referrer-policy and permissions-policy all present and restrictive | TODO: |
| 6 | TLS configuration | An SSL grading service against the production hostname | Grade A or better; TLS 1.2 minimum; no weak ciphers | TODO: |
| 7 | Secret leakage | `detect-private-key` (pre-commit) plus a repository **history** scan | No credential in the repository or its history | TODO: |

```bash
make check-deploy
make audit
make lint
make security

docker run --rm -t ghcr.io/zaproxy/zaproxy:stable zap-baseline.py \
  -t https://staging.{{ cookiecutter.domain_name }} -r zap-report.html
```

TODO: attach the ZAP report, the headers scan and the TLS report alongside this record.

## 2. Manual verification

Each line is initialled by the person who performed it. "It should be fine" is not a result.

- [ ] **Object-level access control.** Signed in as user A, request user B's object by its
      identifier — through a URL{% if cookiecutter.api != "none" %} and through the API{% endif %}. Expect 403 or 404, never 200.
- [ ] **Upload bypass attempts.** For every field that accepts a file, all four are rejected: a file
      one byte over the cap; a disallowed extension; a script or executable renamed to an allowed
      extension; an SVG containing a script. Rejection must be a validation error, never a 500.
- [ ] **Private media.** Request the direct URL of a file containing personal data while signed out.
      Expect a denial. Then confirm the on-disk path is not reachable through the web server at all.
{%- if cookiecutter.rate_limiting == "yes" %}
- [ ] **Rate limits and lockout, live.** Trip the login lockout and one public form limit. Confirm
      the lockout, the 429, the `Retry-After` header, and — with more than one worker running — that
      **the counter is shared across workers**.
{%- else %}
- [ ] **Rate limiting exception.** This project has no lockout and no rate limits. Confirm the
      exception is recorded in [14-decisions.md](14-decisions.md) with who accepted it and when.
{%- endif %}
{%- if cookiecutter.spam_protection == "turnstile_honeypot" %}
- [ ] **Spam protection active in the production configuration.** A Turnstile key is present in the
      production environment — the degraded honeypot-only mode is a fallback, not the intended
      production state — and a submission with the honeypot filled is rejected.
{%- elif cookiecutter.spam_protection == "honeypot" %}
- [ ] **Spam protection active.** A submission with the honeypot filled is rejected, and it fails
      identically to a normal validation error.
{%- else %}
- [ ] **Spam protection exception.** This project has no bot protection on public forms. Confirm the
      exception is recorded in [14-decisions.md](14-decisions.md) with who accepted it and when.
{%- endif %}
{%- if cookiecutter.use_2fa == "yes" %}
- [ ] **Second factor enforced.** A staff account with no enrolled device cannot reach any
      administrative view.
{%- else %}
- [ ] **Two-factor exception.** This project does not enforce a second factor. Confirm the exception
      is recorded in [14-decisions.md](14-decisions.md) with who accepted it and when.
{%- endif %}
- [ ] **Administrative surface.** The interface answers at `/{{ cookiecutter.admin_url_prefix }}/`
      and `/admin/` returns 404. No default, demonstration, vendor or temporary account remains. The
      staging basic-authentication credentials are rotated or retired.
- [ ] **Error handling.** Force a 404 and a 500 on staging. Both render a branded page with no
      traceback, no framework version and no internal hostname. `DEBUG` is demonstrably off.
- [ ] **Sensitive paths are not served.** `/.env`, `/.git/config`, a directory listing of `/media/`,
      backup files, and source maps of administrative JavaScript all return 404 or 403.
{%- if cookiecutter.media_storage != "filesystem" %}
- [ ] **The media {% if cookiecutter.media_storage == "azure" %}container{% else %}bucket{% endif %} is not public.** Take a private object's key from the database and
      request its object URL directly, with no signature: it must return 403. Then try to list the
      {% if cookiecutter.media_storage == "azure" %}container{% else %}bucket{% endif %} anonymously and confirm that is refused too. `manage.py check` catches a
      public ACL in the settings, but it cannot see a policy applied in the provider's console —
      this is the check that does.
{%- endif %}
- [ ] **Session behaviour.** Cookies carry `Secure`, `HttpOnly` and `SameSite`. The session is
      invalidated on sign-out, and the session key is cycled on sign-in.
- [ ] **CSRF.** A cross-origin POST to a state-changing endpoint is rejected. No view is
      `csrf_exempt` without a written reason.
{%- if cookiecutter.languages == "en_ar" %}
- [ ] **Both languages.** Every check above also passes on the Arabic site. A control that is only
      wired into one language's templates is not wired in.
{%- endif %}
{%- if cookiecutter.api != "none" %}
- [ ] **The API.** The schema UI is not exposed in production. Every endpoint requires
      authentication unless it is a reviewed, deliberate exception. `CORS_ALLOWED_ORIGINS` is an
      explicit list with no wildcard. An error response carries no traceback.
{%- endif %}
{%- if cookiecutter.sentry == "yes" %}
- [ ] **Error monitoring.** `SENTRY_SEND_DEFAULT_PII` is `False`, the environment and release tags
      are correct, and the deliberate-error endpoint returns 404 under production settings.
{%- endif %}

## 3. Findings

| # | Severity | Finding | Status | Re-tested |
|---|---|---|---|---|
| | | | | |

Severity is assigned from this table, not by argument:

| Severity | Definition | Gate |
|---|---|---|
| Critical | Remote code execution, authentication bypass, mass data exposure, administrator takeover | **Blocks go-live. No exceptions.** |
| High | Access to another user's data, stored cross-site scripting, unauthenticated destructive action, secret disclosure | **Blocks go-live. No exceptions.** |
| Medium | Missing hardening with a plausible attack path: a weak CSP, verbose errors, a missing rate limit | Fix before go-live, or obtain formal written client acceptance with a remediation date |
| Low / Informational | Everything else | Recorded; scheduled or accepted |

**No project goes live with an open Critical or High finding.**

## 4. Sign-off record

```text
Security pass — {{ cookiecutter.project_name }}
Client:                  {{ cookiecutter.client_name }}
Environment tested:      staging (____________________), production settings, ____-__-__
Commit / tag tested:     ____________________
Performed by:            ____________________
Reviewed by:             ____________________
Automated checks 1-7:    pass / pass-with-exception   (reports attached)
Manual verification:     all items initialled          (yes / no)
Findings:                ___ Critical, ___ High, ___ Medium, ___ Low
Critical/High resolved:  yes / no    (re-tested ____-__-__)
Accepted exceptions:     ____________________________________________
                         (each with the client acceptance reference and a remediation date)
Result:                  APPROVED FOR GO-LIVE / BLOCKED
```

## 5. After go-live

- A security fix during the warranty period is a defect, not a change request.
- A newly disclosed vulnerability in a pinned dependency is assessed when the dependency audit fails
  the build; Critical and High are patched.
- TODO: state who owns security maintenance after the warranty period ends, and from what date.
