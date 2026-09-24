"""A Content-Security-Policy exception for the Django admin, and nowhere else.

django-unfold drives its admin with Alpine.js, which evaluates every x-data,
x-show and @click expression with ``new Function()``. Under our policy - no
``'unsafe-eval'`` in ``script-src`` - none of that runs: modals, including the
keyboard-shortcuts one, render open with nothing able to close them, and the
admin is unusable. Unfold ships no CSP-compatible build.

So responses under ``DJANGO_ADMIN_URL_PREFIX`` get the site policy plus
``'unsafe-eval'``. The public site{% if cookiecutter.stack == "wagtail" %} and the Wagtail admin{% endif %} keep the strict policy.
The exception is recorded in docs/14-decisions.md; remove this middleware if
Unfold ever ships a CSP build of Alpine.

Placed after ``ContentSecurityPolicyMiddleware`` in ``MIDDLEWARE`` so its
``process_response`` runs first and the CSP middleware reads the override.
"""

from copy import deepcopy

from django.conf import settings
from django.utils.csp import CSP


def admin_csp_policy():
    policy = deepcopy(settings.SECURE_CSP)
    script_src = list(policy.get("script-src", ["'self'"]))
    if CSP.UNSAFE_EVAL not in script_src:
        script_src.append(CSP.UNSAFE_EVAL)
    policy["script-src"] = script_src
    return policy


class DjangoAdminCSPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.prefix = f"/{settings.DJANGO_ADMIN_URL_PREFIX.strip('/')}/"
        self.policy = admin_csp_policy()

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(self.prefix) and not hasattr(response, "_csp_config"):
            response._csp_config = self.policy
        return response
