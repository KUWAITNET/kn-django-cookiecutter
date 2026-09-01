"""Bilingual URLs, the language switcher and bidirectional text helpers."""

import pytest
from django.test import RequestFactory
from django.urls import reverse
from django.utils import translation

from apps.core.templatetags.core_tags import localize_path, switch_language_url
from apps.core.utils import (
    LTR_ISOLATE,
    POP_DIRECTIONAL_ISOLATE,
    language_alternatives,
    ltr_isolate,
    url_in_language,
)


def _request(path="/en/"):
    return RequestFactory().get(path)


# --- The switcher ------------------------------------------------------------


def test_switching_language_swaps_the_prefix():
    context = {"request": _request("/en/")}
    assert switch_language_url(context, "ar").startswith("/ar/")


def test_switching_language_preserves_the_query_string():
    """Losing ?page=3 on a language switch loses the visitor's place."""
    context = {"request": _request("/en/?page=3&category=news")}
    switched = switch_language_url(context, "ar")
    assert "page=3" in switched
    assert "category=news" in switched


def test_an_unknown_language_code_does_not_produce_a_dead_link():
    context = {"request": _request("/en/")}
    # A typo must not emit "/xx/", which would 404 for every visitor who clicks.
    assert switch_language_url(context, "xx") == "/en/"


def test_url_in_language_returns_a_path_for_every_configured_language(settings):
    request = _request("/en/")
    for code, _label in settings.LANGUAGES:
        assert url_in_language(request, code).startswith(f"/{code}/")


# --- hreflang / switcher data ------------------------------------------------


def test_language_alternatives_describe_every_language(settings):
    alternatives = language_alternatives(_request("/en/"))
    assert len(alternatives) == len(settings.LANGUAGES)
    codes = {entry["code"] for entry in alternatives}
    assert codes == {code for code, _ in settings.LANGUAGES}
    for entry in alternatives:
        # Everything hreflang, og:locale and the switcher need, in one shape.
        assert set(entry) == {"code", "name", "name_local", "bidi", "url", "is_current"}
        assert entry["url"].startswith("http")


def test_language_alternatives_mark_the_active_language():
    with translation.override("ar"):
        alternatives = language_alternatives(_request("/ar/"))
    current = [entry for entry in alternatives if entry["is_current"]]
    assert len(current) == 1
    assert current[0]["code"] == "ar"
    assert current[0]["bidi"] is True


# --- Editor-typed paths ------------------------------------------------------


@pytest.mark.parametrize("path", ["/about/", "/about/team/", "/about/team/?page=2"])
def test_a_bare_internal_path_gets_the_active_language_prefix(path):
    with translation.override("ar"):
        assert localize_path(path) == f"/ar{path}"


def test_an_already_prefixed_path_is_left_alone():
    with translation.override("en"):
        assert localize_path("/ar/about/") == "/ar/about/"


def test_a_route_outside_i18n_patterns_is_never_prefixed():
    # Resolved against the real URLconf, so adding an unprefixed route does not
    # silently start getting a language prefix.
    with translation.override("ar"):
        assert localize_path(reverse("healthz")) == reverse("healthz")


# --- URL resolution in both languages ----------------------------------------
{%- if cookiecutter.stack == "wagtail" %}


@pytest.mark.django_db
def test_page_urls_carry_the_active_language_prefix():
    from wagtail.models import Page

    page = Page.objects.live().filter(depth__gt=1).first()
    if page is None:
        pytest.skip("no live page in the seeded tree")
    with translation.override("en"):
        assert page.url.startswith("/en/")
    with translation.override("ar"):
        assert page.url.startswith("/ar/")
{%- else %}
{%- if cookiecutter.frontend != "api_only" %}


def test_named_urls_resolve_under_both_languages(settings):
    for code, _label in settings.LANGUAGES:
        with translation.override(code):
            assert reverse("home").startswith(f"/{code}/")
{%- endif %}
{%- endif %}


# --- Bidirectional text ------------------------------------------------------


def test_ltr_isolate_wraps_the_value_in_isolate_characters():
    isolated = ltr_isolate("+965 2234 5678")
    # The control characters work in plain text too, which CSS does not: e-mail
    # clients routinely strip the style attribute.
    assert isolated.startswith(LTR_ISOLATE)
    assert isolated.endswith(POP_DIRECTIONAL_ISOLATE)
    assert "+965 2234 5678" in isolated


def test_ltr_isolate_leaves_empty_values_alone():
    assert ltr_isolate("") == ""
    assert ltr_isolate(None) is None
