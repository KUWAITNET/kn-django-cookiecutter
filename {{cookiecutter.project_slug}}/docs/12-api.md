# 12. Application interface (API)

{{ cookiecutter.project_name }} exposes an HTTP interface for other systems. It is built with Django
REST Framework and follows the KUWAITNET API standard.

## Base addresses

| Environment | Base | Schema UI |
|---|---|---|
| Production | `https://{{ cookiecutter.domain_name }}/api/v1/` | Not exposed |
| Staging | TODO: `https://staging.{{ cookiecutter.domain_name }}/api/v1/` | Available |
| Local | `http://localhost:8000/api/v1/` | Available |

The interactive documentation is controlled by `API_DOCS_ENABLED`, which defaults to `True` in
development and staging and **`False` in production**. Turning it on in production exposes the full
surface of the interface to anyone who guesses the path; do not do it to save a support call.

## Versioning

The version is in the path: `/api/v1/`. `v1` is currently the only accepted version.

Within a version we may add an endpoint, add an optional request field, or add a response field.
We do not remove a field, rename one, change its type, tighten validation, or change the meaning of
an existing value — those require a new version.

TODO: state how breaking changes are announced to integrators, how long the previous version stays
available, and who to tell. Write it before the first integrator exists, not after.

## Authentication

External clients use JSON Web Tokens. Same-origin browser requests may use the session instead.

**Every endpoint requires authentication unless it explicitly opts out.** The default permission is
"authenticated"; a public endpoint is a deliberate, reviewed exception, not an oversight.

```bash
# Obtain a token pair
curl -sS -X POST https://{{ cookiecutter.domain_name }}/api/v1/auth/token/ \
     -H 'Content-Type: application/json' \
     -d '{"username": "integration-client", "password": "..."}'

# Use it
curl -sS https://{{ cookiecutter.domain_name }}/api/v1/ \
     -H 'Authorization: Bearer <access-token>'

# Refresh it
curl -sS -X POST https://{{ cookiecutter.domain_name }}/api/v1/auth/token/refresh/ \
     -H 'Content-Type: application/json' \
     -d '{"refresh": "<refresh-token>"}'
```

TODO: confirm the exact token paths against the schema — `/api/v1/` is mounted from `apps/api/urls.py`
and the schema is the authority.

| Token | Lifetime | Notes |
|---|---|---|
| Access | 15 minutes (`JWT_ACCESS_MINUTES`) | Sent on every request |
| Refresh | 7 days (`JWT_REFRESH_DAYS`) | **Rotates on use**: the old refresh token is blacklisted immediately |

Because refresh tokens rotate and the previous one is blacklisted, a client that refreshes twice in
parallel will find one of the two rejected. Refresh through a single path in the client, not from
every worker independently.

Tokens are signed with `JWT_SIGNING_KEY`, which is deliberately separate from `SECRET_KEY` so that
rotating it invalidates API tokens without logging every browser session out.

TODO: record who owns each client credential, how a credential is issued, and how it is rotated.
Every issued credential belongs to a named person or system, and is listed in the third-party
services register.

## Schema and documentation

```bash
make schema          # writes schema.yml and validates it
make schema-check    # fails when the committed schema no longer matches the code
```

| Path | What |
|---|---|
| `/api/schema/` | The OpenAPI document |
| `/api/schema/swagger-ui/` | Interactive documentation (development and staging only) |

TODO: confirm the exact schema paths against `apps/api/urls.py`.

Commit the generated schema and keep it current: it is the contract, and an integrator reading a
stale one will build against an interface that no longer exists.

## Errors

Every error response is RFC 9457 `application/problem+json`. One shape, for every endpoint, for
every failure — a client writes one error handler.

```json
{
  "type": "https://example.com/api/problems/validation-error",
  "title": "Validation failed",
  "status": 400,
  "detail": "The request body failed validation. See the errors member.",
  "instance": "/api/v1/notes/",
  "request_id": "0f9c1a7e-2b3d-4a5f-8c6e-1d2f3a4b5c6d",
  "errors": [
    { "field": "title", "code": "required", "detail": "This field is required." }
  ]
}
```

A `429` additionally carries `retry_after` in the body and a matching `Retry-After` header.

The envelope is produced by [`drf-standardized-errors`](https://pypi.org/project/drf-standardized-errors/)
with a project formatter that emits RFC 9457, rather than a hand-written exception handler. That gives
consistent coverage of every DRF exception path and, through its drf-spectacular integration, error
responses that appear in the OpenAPI schema instead of being invisible to it.

One caveat worth knowing when reading the schema: drf-spectacular labels these responses
`application/json` because it derives media types from the renderer classes. The wire response is
`application/problem+json`; only the schema's label is generic.

| Status | Means |
|---|---|
| 400 | The request body failed validation. `errors` names the fields |
| 401 | No credentials, or an expired or invalid access token |
| 403 | Authenticated, but not permitted to do this — including to this specific object |
| 404 | No such object, or an object you are not permitted to know exists |
| 405 | Method not allowed on this endpoint |
| 415 | Unsupported content type; send `application/json` |
| 429 | Rate limited. Honour the `Retry-After` header |
| 500 | An unhandled error. It is reported{% if cookiecutter.sentry == "yes" %} to the error monitor{% endif %}; report it too, with the time |

The error body never contains a traceback, a framework version, a SQL fragment or an internal
hostname. If one appears, that is a security finding.

## Rate limits

| Scope | Default | Environment variable |
|---|---|---|
| Anonymous | 60 per minute | `THROTTLE_ANON` |
| Authenticated | 600 per hour | `THROTTLE_USER` |
| Token endpoints | 10 per minute | `THROTTLE_AUTH` |
| Write operations | 60 per hour | `THROTTLE_WRITE` |

Exceeding a limit returns 429 with `Retry-After`. Clients must honour it; retrying immediately is
how a client turns a throttle into an outage for itself.

{% if cookiecutter.cache == "redis" -%}
Counters live in the shared cache, so a limit is a limit across all workers.
{%- else -%}
**The counters live in a per-process cache on this project.** With three workers, a stated limit of
60 per minute is really up to 180. This is acceptable in development and is a defect in production:
switch the cache to Redis before go-live. See [14-decisions.md](14-decisions.md).
{%- endif %}

Rate limiting is layered deliberately: throttles cover everything under `/api/`, login lockout
covers authentication, and no view carries two of the mechanisms — two limiters on one view produce
two different 429 shapes and a double-counted budget.

## Pagination, filtering and ordering

- Page-number pagination, 20 items per page by default, **hard maximum 100**. A client asking for
  more gets 100, not an error and not the whole table.
- Filtering, ordering and search are enabled per endpoint. Field names accepted by `ordering` and by
  filters are resolved against an explicit allowlist, so a client cannot order by an arbitrary
  column or traverse a relation the endpoint does not expose.
- Serializers declare their fields explicitly. `fields = "__all__"` is never used on a public
  serializer, because it silently publishes every field added to the model afterwards.

## CORS

Browser clients must be listed in `CORS_ALLOWED_ORIGINS`. It is an explicit list; there is no
wildcard, and never a wildcard with credentials. Only `/api/` is subject to CORS.

TODO: list the origins that legitimately call this interface, and remove any that stop doing so.

{% if cookiecutter.api == "headless" and cookiecutter.stack == "wagtail" -%}
## Page, image and document endpoints

In addition to the interface above, the content management system exposes its own read-only
endpoints under `/api/v2/` for pages, images and documents. They are versioned and shaped by Wagtail
rather than by this project, and they serve **published, public content only**.

Use `/api/v1/` for anything this project defines, and `/api/v2/` for delivering managed content to a
front end. TODO: list the page types exposed and the fields each one returns.
{%- endif %}

## A worked example

TODO: replace this with a real endpoint from this project, with a real request and a real response,
so a developer can run it in a terminal immediately.

```bash
TOKEN=$(curl -sS -X POST https://{{ cookiecutter.domain_name }}/api/v1/auth/token/ \
        -H 'Content-Type: application/json' \
        -d '{"username": "...", "password": "..."}' | python -c 'import sys,json; print(json.load(sys.stdin)["access"])')

curl -sS "https://{{ cookiecutter.domain_name }}/api/v1/<resource>/?page=1" \
     -H "Authorization: Bearer $TOKEN" \
     -H 'Accept: application/json'
```

## For developers extending the interface

- Business rules live in the same place they do for the rest of the project. A serializer or view
  that re-implements a rule already expressed in a model manager creates a second answer to the same
  question, and the two drift.
- Every new endpoint needs: an explicit permission class, explicit serializer fields, a throttle
  scope where it is more expensive than a normal read, a schema entry that survives
  `make schema-check`, and tests covering the permission denial path as well as the success path.
- Never add `django-ratelimit` to a DRF view. Throttles are the mechanism there.
