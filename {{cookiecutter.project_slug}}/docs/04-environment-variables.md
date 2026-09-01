# 4. Environment variables reference

Every configuration value the application reads, including the obvious ones. A missing entry here is
a site that will not start on a new server, and the person rebuilding it will not know what is
missing.

Configuration is read through `django-environ` in `{{ cookiecutter.project_slug }}/settings/base.py`.
There is no `os.environ.get()` scattered through the codebase and no `if DEBUG:` branch choosing a
hostname. Values come from the process environment, or from a `.env` file in the repository root
during local development.

**`.env.example` in the repository root is the machine-readable twin of this page.** It lists every
variable in the same order and under the same headings as the settings module. When you add a
variable to settings, add it to `.env.example` and to this table in the same commit. A key that
exists on a server but not in `.env.example` is a defect.

**Never write a real secret value in this file.** Write the format. Secrets are marked below so
nobody pastes one into a ticket, a chat message or a screenshot.

## Core

| Variable | Purpose | Required | Example | Secret |
|---|---|---|---|---|
| `SECRET_KEY` | Signs sessions, password-reset tokens and cookies. Unique per environment; changing it logs everyone out and invalidates outstanding reset links. Production settings provide **no default** — a missing value stops the boot. | Yes | 50 random URL-safe characters | **Yes** |
| `DEBUG` | Detailed error pages and tracebacks. Must be `False` outside development. | Yes | `False` | No |
| `ALLOWED_HOSTS` | Comma-separated domains the site answers for. Never `*` in production. | Yes | `{{ cookiecutter.domain_name }},www.{{ cookiecutter.domain_name }}` | No |
| `SITE_NAME` | Display name used in page titles, e-mail subjects and the admin header. | No | `{{ cookiecutter.project_name }}` | No |
| `BASE_URL` | Absolute base used to build links in e-mail and in machine-readable output, where no request is available. | Yes in production | `https://{{ cookiecutter.domain_name }}` | No |
| `SESSION_COOKIE_AGE` | Session lifetime in seconds. Default 43200 (12 hours). | No | `43200` | No |
| `LOG_LEVEL` | Root log level. `INFO` is the production floor. | No | `INFO` | No |

## Database

| Variable | Purpose | Required | Example | Secret |
|---|---|---|---|---|
| `DATABASE_URL` | PostgreSQL connection. Connections are reused for 60 seconds (`CONN_MAX_AGE`). | Yes | `postgres://user:password@localhost:5432/{{ cookiecutter.project_slug }}` | **Yes** |
| `TEST_DATABASE_URL` | Overrides the database used by the test settings. Falls back to `DATABASE_URL`. | No | | **Yes** |
{% if cookiecutter.cache == "redis" %}
## Cache

| Variable | Purpose | Required | Example | Secret |
|---|---|---|---|---|
| `REDIS_URL` | Shared cache. **Required in production**: rate-limit{% if cookiecutter.api != "none" %} and throttle{% endif %} counters live here, and a per-process cache multiplies every limit by the number of workers. | Yes in production | `redis://127.0.0.1:6379/1` | No |
{% endif %}
## Outgoing mail

Mail always goes through `django-post-office`, which logs every send. These variables configure the
transport it wraps. With none of them set the transport is the console backend, which is correct for
development and would silently swallow production mail.

| Variable | Purpose | Required | Example | Secret |
|---|---|---|---|---|
| `EMAIL_URL` | Single-URL form. Takes precedence over the discrete variables below. | One of the two | `smtp://user:password@smtp.example.com:587` | **Yes** |
| `EMAIL_HOST` | SMTP host. | One of the two | `smtp.example.com` | No |
| `EMAIL_HOST_USER` | SMTP username. | With `EMAIL_HOST` | | No |
| `EMAIL_HOST_PASSWORD` | SMTP password. | With `EMAIL_HOST` | | **Yes** |
| `EMAIL_PORT` | SMTP port. Default 587. | No | `587` | No |
| `EMAIL_USE_TLS` | STARTTLS. Default `True`. | No | `True` | No |
| `EMAIL_USE_SSL` | Implicit TLS. Default `False`. Do not set both. | No | `False` | No |
| `DEFAULT_FROM_EMAIL` | Address system mail is sent from. Must be a domain the relay is authorised to send for, or messages are rejected as spam. | Yes | `no-reply@{{ cookiecutter.domain_name }}` | No |
| `SERVER_EMAIL` | Address used for error mail. Defaults to `DEFAULT_FROM_EMAIL`. | No | | No |
| `DEFAULT_ADMIN_EMAIL` | Fallback recipient for notification mail, comma-separated. | Yes | `TODO: the client's monitored address` | No |
| `DEV_EMAIL_BACKEND` | Development only: the transport post-office wraps locally, e.g. a local SMTP catcher. | No | `django.core.mail.backends.smtp.EmailBackend` | No |
{% if cookiecutter.spam_protection == "turnstile_honeypot" %}
## Spam protection

| Variable | Purpose | Required | Example | Secret |
|---|---|---|---|---|
| `TURNSTILE_SITE_KEY` | Public key rendered into the form. Unset means protection degrades to honeypot-only, so development, CI and UAT are never blocked. **Production without a key is a go-live finding.** | Yes in production | | No |
| `TURNSTILE_SECRET_KEY` | Used for server-side verification of the submitted token. | Yes in production | | **Yes** |
{% endif %}
{%- if cookiecutter.rate_limiting == "yes" %}
## Rate limiting and lockout

| Variable | Purpose | Required | Example | Secret |
|---|---|---|---|---|
| `AXES_FAILURE_LIMIT` | Failed logins before lockout. Default 5. | No | `5` | No |
| `AXES_COOLOFF_HOURS` | Lockout duration in hours. Default 0.5 (30 minutes). | No | `0.5` | No |
| `AXES_IPWARE_PROXY_COUNT` | Number of trusted proxies in front of the application. **Get this wrong and every request appears to come from the load balancer, so one attacker locks out every user.** Set it to the real number of proxies; leave at 0 when the application is reached directly. | Yes in production | `1` | No |
{%- if cookiecutter.frontend != "api_only" %}
| `RATELIMIT_FORM_SUBMIT` | Budget for form submissions. Default `5/h`. | No | `5/h` | No |
{%- if cookiecutter.newsletter == "yes" %}
| `RATELIMIT_NEWSLETTER` | Budget for newsletter subscription. Default `3/h`. Tight because each request sends mail. | No | `3/h` | No |
{%- endif %}
| `RATELIMIT_SEARCH` | Budget for search. Default `30/m`. | No | `30/m` | No |
{%- endif %}
{% endif %}
## Uploads

| Variable | Purpose | Required | Example | Secret |
|---|---|---|---|---|
| `MEDIA_ROOT` | Where public uploads are written. | Yes in production | `/var/www/{{ cookiecutter.project_slug }}/media` | No |
| `PRIVATE_MEDIA_ROOT` | Where uploads containing personal data are written. **Must not be reachable from the web server.** | Yes in production | `/var/www/{{ cookiecutter.project_slug }}/private-media` | No |
| `UPLOAD_MAX_SIZE_MB` | Default per-field size cap in megabytes. Default 10. Individual fields may set a tighter cap. | No | `10` | No |
| `UPLOAD_IMAGE_MAX_PIXELS` | Pixel-count ceiling that bounds decompression bombs. Default 50000000. | No | `50000000` | No |
{% if cookiecutter.api != "none" %}
## API

| Variable | Purpose | Required | Example | Secret |
|---|---|---|---|---|
| `CORS_ALLOWED_ORIGINS` | Comma-separated origins allowed to call `/api/`. Explicit list only; never a wildcard with credentials. | Yes where a browser client calls the API | `https://app.{{ cookiecutter.domain_name }}` | No |
| `CORS_ALLOW_CREDENTIALS` | Whether cross-origin requests may carry cookies. Default `False`. | No | `False` | No |
| `JWT_ACCESS_MINUTES` | Access token lifetime. Default 15. | No | `15` | No |
| `JWT_REFRESH_DAYS` | Refresh token lifetime. Default 7. Refresh tokens rotate and the old one is blacklisted. | No | `7` | No |
| `JWT_SIGNING_KEY` | Separate signing key, so rotating it does not invalidate browser sessions. Defaults to `SECRET_KEY`. | No | | **Yes** |
| `THROTTLE_ANON` | Anonymous throttle. Default `60/min`. | No | `60/min` | No |
| `THROTTLE_USER` | Authenticated throttle. Default `600/hour`. | No | `600/hour` | No |
| `THROTTLE_AUTH` | Token endpoint throttle. Default `10/min`. | No | `10/min` | No |
| `THROTTLE_WRITE` | Write-operation throttle. Default `60/hour`. | No | `60/hour` | No |
| `API_DOCS_ENABLED` | Serves the interactive schema UI. Defaults to `True` in development and staging and **`False` in production**. | No | `False` | No |
{% endif %}
{%- if cookiecutter.analytics == "ga4_gtm" %}
## Analytics

| Variable | Purpose | Required | Example | Secret |
|---|---|---|---|---|
| `GA4_MEASUREMENT_ID` | Analytics property. **Leave empty everywhere but production**, so staging traffic never reaches the client's property. | No | `G-XXXXXXXXXX` | No |
| `GTM_CONTAINER_ID` | Tag Manager container. Same rule. | No | `GTM-XXXXXXX` | No |
{% endif %}
{%- if cookiecutter.sentry == "yes" %}
## Error monitoring

| Variable | Purpose | Required | Example | Secret |
|---|---|---|---|---|
| `SENTRY_DSN` | Reporting destination. **Unset means Sentry is fully disabled**: the SDK is never initialised and no network call is made. | Yes in production | | **Yes** |
| `SENTRY_ENVIRONMENT` | Exactly `development`, `staging` or `production`. Alerts and issue grouping depend on it. | Yes with a DSN | `production` | No |
| `SENTRY_RELEASE` | The deployed git tag. Lets an issue be attributed to a release. | Yes in production | `v1.4.0` | No |
| `SENTRY_TRACES_SAMPLE_RATE` | Performance tracing. Default `0.0`. Raise to `0.05`–`0.1` for a bounded investigation and **turn it back down** — a rate left at `1.0` exhausts the quota within days, after which errors stop being delivered. | No | `0.0` | No |
| `SENTRY_SEND_DEFAULT_PII` | Attaches request bodies, cookies, user e-mail and client IP to events. Default `False` and stays false unless the client agrees in writing. | No | `False` | No |
{% endif %}
{%- if cookiecutter.countries_app != "none" %}
## Countries

| Variable | Purpose | Required | Example | Secret |
|---|---|---|---|---|
{%- if cookiecutter.countries_app == "cities" %}
| `COUNTRY_EXCLUDED_CODES` | ISO 3166-1 alpha-2 codes withheld from every public country list. Read only by `Country.objects.selectable()`, which every country and dial-code list on the site goes through. | No | `AA,BB` | No |
{%- else %}
| `COUNTRY_EXCLUDED_CODES` | ISO 3166-1 alpha-2 codes withheld from every public country list. **Normally empty**: the KUWAITNET `django-countries` fork applies the country-list policy to the data it ships, so this is only for a per-client exclusion on top of that. | No | `AA,BB` | No |
{%- endif %}

{% endif %}
## Production transport security

These have safe defaults in `settings/production.py`. Override only with a reason recorded in
[14-decisions.md](14-decisions.md).

| Variable | Purpose | Required | Example | Secret |
|---|---|---|---|---|
| `SECURE_SSL_REDIRECT` | Redirects HTTP to HTTPS. Default `True`. | No | `True` | No |
| `SECURE_HSTS_SECONDS` | HSTS max-age. Default 2592000 (30 days). Raise to a year only after 30 days without incident. | No | `2592000` | No |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | Default `True`. Applies HSTS to every subdomain — verify TLS on all of them first. | No | `True` | No |
| `SECURE_HSTS_PRELOAD` | Default `True`. | No | `True` | No |
| `CSRF_TRUSTED_ORIGINS` | Origins allowed to submit forms. Defaults to `https://{{ cookiecutter.domain_name }}`. | No | `https://{{ cookiecutter.domain_name }},https://www.{{ cookiecutter.domain_name }}` | No |
{%- if cookiecutter.use_2fa == "yes" %}
{%- if cookiecutter.stack == "wagtail" %}
| `WAGTAIL_2FA_REQUIRED` | Enforces the second factor on administrative accounts. Default `True`. Setting it to `False` in any environment but test is a security finding. | No | `True` | No |
{%- else %}
| `OTP_ADMIN_REQUIRED` | Enforces the second factor on administrative accounts. Default `True`. Setting it to `False` in any environment but test is a security finding. | No | `True` | No |
{%- endif %}
{%- endif %}

## Where the values live

| Environment | Source | Who can read them |
|---|---|---|
| Local | `.env` in the repository root, gitignored, mode 0600 | The developer |
| CI | Fixed non-secret values in the workflow and in `settings/test.py` | Anyone with repository access |
| Staging | TODO: name the store | TODO: |
| Production | TODO: name the store | TODO: project lead and named engineers only |

Rules that apply to all of them:

- `.env` is never committed. A `.env` that reaches the repository means the credentials in it are
  compromised and must be rotated, not deleted from the history and forgotten.
- Production secrets are not sent through chat, e-mail, ticket comments or spreadsheets.
- `SECRET_KEY`, the database password, the SMTP credentials and every third-party key are **rotated
  at handover** and whenever someone with access leaves. Do it inside a maintenance window.
- `settings/local.py` is a development escape hatch. It is gitignored and it is **not** a production
  secret store; no deploy procedure may instruct anyone to create one on a production host.

## After changing a value

{% if cookiecutter.deploy_target == "gunicorn_nginx" -%}
```bash
sudo systemctl restart {{ cookiecutter.project_slug }}-gunicorn
sudo systemctl status {{ cookiecutter.project_slug }}-gunicorn --no-pager
curl -sS -o /dev/null -w '%{http_code}\n' https://{{ cookiecutter.domain_name }}/healthz
```
{%- else -%}
```bash
docker compose up -d --force-recreate web
docker compose ps
curl -sS -o /dev/null -w '%{http_code}\n' https://{{ cookiecutter.domain_name }}/healthz
```
{%- endif %}

Settings are read once at boot. A changed variable has no effect until the application restarts, and
a restart that silently fails leaves the old value in place — always check the status and the health
endpoint afterwards.
