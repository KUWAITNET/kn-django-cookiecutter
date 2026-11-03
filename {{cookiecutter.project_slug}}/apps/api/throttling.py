"""Named throttle scopes (api-standard.md A8).

The rates live in ``settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`` and are
tuned per project against measured traffic before go-live:

===========  ==========================  ==================================
Scope        Keyed on                    Applies to
===========  ==========================  ==================================
``anon``     client IP                   any unauthenticated request
``user``     authenticated user          any authenticated request
``auth``     client IP                   token obtain - a credential oracle
``write``    authenticated user          POST/PUT/PATCH/DELETE
===========  ==========================  ==================================

``anon`` and ``user`` are the global defaults from ``DEFAULT_THROTTLE_CLASSES``
and need no wiring. ``DEFAULT_THROTTLE_CLASSES`` deliberately does *not* include
``ScopedRateThrottle``, so a view that wants a named scope lists the class below
in ``throttle_classes`` - opting in is visible in the view, not implied by a
string attribute somebody may delete.

**The layering rule.** Three mechanisms cover three disjoint surfaces, and mixing
them produces either a gap or a double-counted budget:

- DRF throttling runs inside ``APIView.initial()``, so it covers ``/api/**`` and
  nothing else. It never sees a plain Django view or a form POST.
- ``django-ratelimit`` covers public non-DRF POST endpoints - contact forms,
  newsletter subscribe, site search.
- ``django-axes`` covers authentication: a lockout after N failures is a
  different control from a rate cap, and both apply to login.
- **Never stack ``django-ratelimit`` on a DRF view.** Two mechanisms produce two
  different 429 bodies (one problem+json, one an HTML error page) and the request
  is counted against two budgets, so the effective limit is neither of the
  configured numbers. An API-only project skips ``django-ratelimit`` entirely.

**Counters live in the cache, so the backend matters.** On ``LocMemCache`` every
gunicorn worker keeps its own counter, which turns a configured "10/min" into an
effective 10*N per minute, non-deterministically, depending on which worker the
load balancer picks. Production rate limiting requires Redis: a project that
ships throttling on LocMemCache has not shipped throttling, it has shipped a log
message.
"""

from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle, UserRateThrottle


class AuthRateThrottle(AnonRateThrottle):
    """``auth`` scope, keyed on the client IP.

    Applied to token obtain. Keyed on IP rather than user because the caller is
    by definition not yet authenticated, and because a login endpoint answers
    "does this account exist and is this its password?" - it is a credential
    oracle, and the rate is deliberately the tightest in the API.
    """

    scope = "auth"


class WriteRateThrottle(UserRateThrottle):
    """``write`` scope, keyed on the authenticated user.

    Applied to POST/PUT/PATCH/DELETE on ordinary resources, so a runaway client
    cannot exhaust the write path while ordinary reads stay responsive.
    """

    scope = "write"


class PublicReadRateThrottle(AnonRateThrottle):
    """``anon`` scope, for endpoints that deliberately allow anonymous reads.

    A public endpoint is a free resource, so it always carries a throttle even
    though the global default would also apply: naming it here keeps the intent
    visible on the view.
    """

    scope = "anon"


class ScopedThrottle(ScopedRateThrottle):
    """Reads the scope from the view's ``throttle_scope`` attribute.

    Use it when one view needs a rate that no other view shares::

        class ReportExportView(APIView):
            throttle_classes = [ScopedThrottle]
            throttle_scope = "write"

    The named scope must exist in ``DEFAULT_THROTTLE_RATES`` or DRF raises at
    request time rather than silently not throttling.
    """
