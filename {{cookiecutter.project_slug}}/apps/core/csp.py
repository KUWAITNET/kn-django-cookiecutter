"""Content-Security-Policy exceptions for the admin{% if cookiecutter.stack == "wagtail" %}s{% endif %}, and nowhere else.

The public site keeps the strict policy: no ``'unsafe-inline'`` and no
``'unsafe-eval'`` in ``script-src``, inline scripts only with the per-request
nonce. {% if cookiecutter.stack == "wagtail" %}Both admins ship{% else %}The admin ships{% endif %} third-party markup that cannot meet it:

* **Django admin (django-unfold).** Unfold drives its admin with Alpine.js,
  which evaluates every x-data, x-show and @click expression with
  ``new Function()``. Without ``'unsafe-eval'`` none of it runs: modals,
  including the keyboard-shortcuts one, render open with nothing able to close
  them. Unfold ships no CSP-compatible build.
{%- if cookiecutter.stack == "wagtail" %}
* **Wagtail admin.** On snippet and settings edit forms Wagtail initialises
  each chooser with an inline ``<script>new ImageChooser(...)</script>``{% if cookiecutter.languages == "en_ar" %}, and
  wagtail-modeltranslation injects its language toggles the same way{% endif %}.
  None of it carries our nonce, so "Choose an image" does nothing.
  ``'unsafe-inline'`` is the only way to allow it - and browsers *ignore*
  ``'unsafe-inline'`` while a nonce is present in the directive, so the Wagtail
  admin's policy drops the nonce.
{%- endif %}

{% if cookiecutter.stack == "wagtail" %}Both admins are{% else %}The admin is{% endif %} staff-only and behind two-factor authentication, which
bounds what the relaxation exposes. Recorded in docs/14-decisions.md; remove
each branch when its upstream ships CSP-compatible markup.

Placed after ``ContentSecurityPolicyMiddleware`` in ``MIDDLEWARE`` so its
``process_response`` runs first and the CSP middleware reads the override.
"""

from copy import deepcopy

from django.conf import settings
from django.utils.csp import CSP


def _policy(add=(), drop=()):
    policy = deepcopy(settings.SECURE_CSP)
    script_src = [s for s in policy.get("script-src", ["'self'"]) if s not in drop]
    script_src += [s for s in add if s not in script_src]
    policy["script-src"] = script_src
    return policy


def django_admin_csp_policy():
    return _policy(add=[CSP.UNSAFE_EVAL])
{%- if cookiecutter.stack == "wagtail" %}


def wagtail_admin_csp_policy():
    return _policy(add=[CSP.UNSAFE_INLINE], drop=[CSP.NONCE])
{%- endif %}


class AdminCSPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.policies = [
            (f"/{settings.DJANGO_ADMIN_URL_PREFIX.strip('/')}/", django_admin_csp_policy()),
{%- if cookiecutter.stack == "wagtail" %}
            (f"/{settings.WAGTAIL_ADMIN_URL_PREFIX.strip('/')}/", wagtail_admin_csp_policy()),
{%- endif %}
        ]

    def __call__(self, request):
        response = self.get_response(request)
        if hasattr(response, "_csp_config"):
            return response
        for prefix, policy in self.policies:
            if request.path.startswith(prefix):
                response._csp_config = policy
                break
        return response
