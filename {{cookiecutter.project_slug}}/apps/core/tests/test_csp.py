"""The Content-Security-Policy, and the nonce that makes it worth having.

This exists because the failure mode is silent. The nonce reaches a template
only through ``django.template.context_processors.csp``, as ``csp_nonce``. If
that processor is missing from settings, or a template still uses the
``request.csp_nonce`` expression that ``django-csp`` provided before CSP moved
into Django core, the attribute renders **empty**: no exception, no warning, a
200 response, and a browser that silently refuses to run the script. Nothing in
a normal test suite notices, because the page still returns 200 and still
contains the tag.

So these tests assert the round trip: the nonce in the body is non-empty, and
the same value appears in the header. Either half alone would pass while the
policy did nothing.
"""

from __future__ import annotations

import re

import pytest
from django.http import HttpResponse
from django.middleware.csp import ContentSecurityPolicyMiddleware
from django.template import engines
from django.template.context_processors import csp as csp_context_processor
from django.test import RequestFactory

NONCE_ATTR = re.compile(r'nonce="([^"]*)"')


# Built by concatenation so no Jinja-significant sequence appears in this file.
# The generator renders this module, and a literal double-brace here - or even a
# raw-tag in a comment explaining one - is consumed at generation time. That is
# not hypothetical: the first version of this file broke exactly that way.
OPEN = "{" + "{"
CLOSE = "}" + "}"
INLINE_SCRIPT = f'<script nonce="{OPEN} csp_nonce {CLOSE}">1;</script>'


def render_with_nonce(request):
    template = engines["django"].from_string(INLINE_SCRIPT)
    return HttpResponse(template.render(csp_context_processor(request), request))


@pytest.fixture
def response_with_inline_script():
    request = RequestFactory().get("/")
    return ContentSecurityPolicyMiddleware(render_with_nonce)(request)


class TestNonce:
    def test_nonce_attribute_is_not_empty(self, response_with_inline_script):
        """An empty nonce is the silent failure this whole module is here for."""
        match = NONCE_ATTR.search(response_with_inline_script.content.decode())
        assert match, "no nonce attribute was rendered at all"
        assert match.group(1), (
            "the nonce rendered empty. Either "
            "django.template.context_processors.csp is missing from "
            "TEMPLATES['OPTIONS']['context_processors'], or the template still "
            "uses request.csp_nonce, which Django does not provide."
        )

    def test_header_carries_the_same_nonce(self, response_with_inline_script):
        body_nonce = NONCE_ATTR.search(response_with_inline_script.content.decode()).group(1)
        header = response_with_inline_script.headers["Content-Security-Policy"]
        assert f"'nonce-{body_nonce}'" in header, (
            "the script's nonce is not in the policy, so the browser will "
            "refuse to run it"
        )

    def test_sentinel_never_reaches_the_browser(self, response_with_inline_script):
        header = response_with_inline_script.headers["Content-Security-Policy"]
        assert "<CSP_NONCE_SENTINEL>" not in header


class TestPolicy:
    @pytest.mark.django_db
    def test_policy_is_served_on_a_normal_page(self, client):
        """`/healthz` needs no page tree, but still traverses every middleware -
        which is all this assertion is about. It does check the database, so the
        mark is required even though no row is created."""
        response = client.get("/healthz")
        assert "Content-Security-Policy" in response.headers

    def test_script_src_allows_no_inline_or_eval(self, settings):
        """A nonce-based policy that also allows inline script protects nothing.

        `core.E005` checks the same thing as a Django system check; this is the
        test that fails in CI if somebody loosens it to make a vendor snippet
        work.
        """
        sources = settings.SECURE_CSP.get("script-src", [])
        assert "'unsafe-inline'" not in sources
        assert "'unsafe-eval'" not in sources

    def test_object_src_is_none(self, settings):
        assert settings.SECURE_CSP.get("object-src") == ["'none'"]

    def test_frame_ancestors_is_restricted(self, settings):
        """Clickjacking protection, alongside X-Frame-Options."""
        assert settings.SECURE_CSP.get("frame-ancestors") == ["'self'"]
