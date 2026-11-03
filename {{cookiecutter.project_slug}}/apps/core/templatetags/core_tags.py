"""Template helpers for links, file links, absolute URLs{% if cookiecutter.languages == "en_ar" %}, language switching{% endif %} and bidirectional text.

The module name is fixed (``{% raw %}{% load core_tags %}{% endraw %}``) rather than derived from the
project slug, so the load line is identical in every KUWAITNET project.
"""

import re
{%- if cookiecutter.languages == "en_ar" %}
from urllib.parse import urlsplit
{%- endif %}

from django import template
from django.conf import settings
{%- if cookiecutter.languages == "en_ar" %}
from django.urls import Resolver404, get_resolver
{%- endif %}
from django.utils.html import format_html, format_html_join
from django.utils.translation import get_language

from apps.core import private_files
from apps.core.utils import absolute_url{% if cookiecutter.languages == "en_ar" %}, url_in_language{% endif %}
from apps.core.utils import ltr_isolate as _ltr_isolate

register = template.Library()

#: A clock time, with or without minutes/seconds.
_TIME = re.compile(r"\d{1,2}(?::\d{2}){0,2}")


# --- URLs --------------------------------------------------------------------


@register.filter
def file_link(value):
    """The ``href`` for an uploaded file: the permission gate if it is private.

    Use it for every link to an upload, never ``.url``. A private file gets
    ``/files/<app.model>/<pk>/<field>/``, which checks permission on the click; a
    public one gets its plain URL - so a template never needs to know which it
    has. An inline ``<img src>`` is the one place ``.url`` is right on a private
    file, because the browser loads it without a click.
    """
    return private_files.file_link(value)


@register.filter(name="absolute_url")
def absolute_url_filter(value):
    """Make a path, an image rendition or a file absolute against ``BASE_URL``.

    For ``og:image``, ``rel=canonical`` and anything else a crawler or an e-mail
    client reads, where a root-relative path is useless.
    """
    if value is None or value == "":
        return ""
    url = getattr(value, "url", None) or str(value)
    return absolute_url(url)


@register.simple_tag(takes_context=True)
def canonical_url(context):
    """The absolute URL of the current page, without the query string.

    Query parameters (tracking tags, pagination) create endless duplicate URLs
    for the same content; the canonical link is what tells a crawler which one
    counts.
    """
    request = context.get("request")
    if request is None:
        return settings.BASE_URL
    return request.build_absolute_uri(request.path)
{%- if cookiecutter.stack == "wagtail" %}


@register.filter
def nav_href(value):
    """Resolve a link block value (page [+ #anchor] | document | url) to an href.

    With a page chosen, ``url`` is treated as an in-page anchor and appended, so
    a menu entry can point at a section of the destination page. With neither,
    ``url`` is used as given{% if cookiecutter.languages == "en_ar" %}, except that a bare internal path picks up the
    active language prefix (see ``localize_path``){% endif %}.
    """
    if value is None or not hasattr(value, "get"):
        return "#"
    page = value.get("page")
    document = value.get("document")
    url = (value.get("url") or "").strip()
    if page:
        base = page.url or "#"
        return f"{base}{url}" if url.startswith("#") else base
    if document:
        return document.url or "#"
{%- if cookiecutter.languages == "en_ar" %}
    return localize_path(url) if url else "#"
{%- else %}
    return url or "#"
{%- endif %}


@register.filter
def og_image_url(page, spec="fill-1200x630"):
    """Absolute URL of a page's sharing image at ``spec``, or "" if it has none."""
    image = getattr(page, "social_sharing_image", None)
    if image is None:
        return ""
    return absolute_url(image.get_rendition(spec).url)
{%- endif %}
{%- if cookiecutter.languages == "en_ar" %}


# --- Language ----------------------------------------------------------------


def _served_without_language_prefix(path: str) -> bool:
    """Whether ``path`` is handled by a URLconf entry outside ``i18n_patterns``.

    Resolved dynamically against the real URLconf rather than compared against a
    hardcoded list, so adding a new unprefixed top-level route (a webhook, a
    health check) does not silently start getting a language prefix.
    """
    clean_path = urlsplit(path).path or "/"
    try:
        get_resolver().resolve(clean_path)
    except Resolver404:
        return False
    return True


@register.filter
def localize_path(path: str) -> str:
    """Add the active language prefix to a bare internal path.

    An editor can type ``/about/`` into a link field instead of choosing a page.
    Without a prefix that path falls outside ``i18n_patterns``, so LocaleMiddleware
    redirects it using browser negotiation rather than the language the visitor is
    currently reading.
    """
    if not path or not path.startswith("/") or path.startswith("//"):
        return path
    for url_setting in (settings.STATIC_URL, settings.MEDIA_URL):
        # An empty setting would match every path and silently disable this.
        if url_setting and path.startswith(url_setting):
            return path
    for code, _label in settings.LANGUAGES:
        if path == f"/{code}" or path.startswith(f"/{code}/"):
            return path
    if _served_without_language_prefix(path):
        return path
    return f"/{get_language() or settings.LANGUAGE_CODE}{path}"


@register.simple_tag(takes_context=True)
def switch_language_url(context, language_code):
    """The current page's URL in ``language_code``, for the language switcher.

    Delegates to ``apps.core.utils.url_in_language`` so the switcher, the
    ``hreflang`` alternates and ``og:locale:alternate`` can never disagree about
    what "this page in Arabic" means. Falls back to the current path when the
    page has no version in the target language, so the link is never dead.
    """
    request = context.get("request")
    page = context.get("page")
    url = url_in_language(request, language_code, page=page)
    if url:
        return url
    return request.get_full_path() if request is not None else "/"
{%- endif %}


@register.simple_tag
def active_language():
    """The active language code, falling back to the project default.

    For ``<html lang="...">``, where an empty attribute is an accessibility bug.
    """
    return get_language() or settings.LANGUAGE_CODE


# --- Bidirectional text ------------------------------------------------------


@register.filter(name="ltr_isolate")
def ltr_isolate_filter(value):
    """Isolate a value so it reads left-to-right inside right-to-left text."""
    return _ltr_isolate(value)


@register.filter
def ltr_phone(value):
    """Render one phone number per line, each forced left-to-right.

    A number is a "+" (bidi-neutral) followed by digits (strongly LTR); inside an
    Arabic paragraph the bidirectional algorithm moves the "+" to the wrong end.
    Both the isolate characters and ``dir="ltr"`` are applied, because e-mail and
    feed readers routinely keep one and drop the other.
    """
    if not value:
        return ""
    lines = [line.strip() for line in str(value).splitlines() if line.strip()]
    if not lines:
        return ""
    return format_html_join(
        format_html("<br>"),
        '<span dir="ltr" class="ltr-value">{}</span>',
        ((_ltr_isolate(line),) for line in lines),
    )


@register.filter
def ltr_hours(value):
    """Render opening hours so the times keep their order in right-to-left text.

    Each clock time is isolated individually and the whole run is marked LTR, so
    a range such as ``7:00 - 15:00`` does not reverse. Deliberately does not
    rewrite AM/PM markers: that was locale-specific guesswork in the project this
    came from, and it mangled anything it had not been written for.
    """
    if not value:
        return ""
    isolated = _TIME.sub(lambda match: _ltr_isolate(match.group(0)), str(value))
    return format_html('<span dir="ltr" class="ltr-value">{}</span>', isolated)
