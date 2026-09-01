"""Template helpers for the settings-driven menus.

``nav_href`` turns a link block into an href; ``nav_item_active`` and
``nav_branch_active`` decide which entry is highlighted. Active state lives here
rather than in the template because every project that reinvents it in the
template reinvents it slightly wrong - usually as a substring test on the request
path, which lights up "/news/" for "/newsletter/".
"""

from urllib.parse import urlparse

from django import template
{%- if cookiecutter.languages == "en_ar" %}
from django.conf import settings
from django.urls import Resolver404, get_resolver
from django.utils.translation import get_language
{%- endif %}

register = template.Library()

{% if cookiecutter.languages == "en_ar" %}
def _served_without_language_prefix(path):
    """Whether ``path`` is handled by a route registered outside i18n_patterns.

    Resolved against the live URLconf instead of a hardcoded list of prefixes, so
    adding a new unprefixed top-level route (documents, healthz, the sitemap)
    automatically stops it being language-prefixed here.
    """
    clean_path = urlparse(path).path or "/"
    try:
        get_resolver().resolve(clean_path)
    except Resolver404:
        return False
    return True


def _localize_internal_path(path):
    """Add the active language prefix to a root-relative path typed by an editor.

    Mirrors the page-URL patch in ``apps.core.url_patches``. Editors can type a
    raw path such as "/about/" into a link block instead of choosing a page;
    with ``prefix_default_language=True`` that path is outside ``i18n_patterns``,
    so the visitor gets redirected by browser language negotiation rather than
    staying in the language they are reading.
    """
    if not path.startswith("/") or path.startswith("//"):
        return path
    # An empty STATIC_URL/MEDIA_URL would make startswith() true for everything
    # and silently disable localisation, so both are checked for content first.
    for asset_url in (settings.STATIC_URL, settings.MEDIA_URL):
        if asset_url and path.startswith(asset_url):
            return path
    for code, _label in settings.LANGUAGES:
        prefix = f"/{code}"
        if path == prefix or path.startswith(prefix + "/"):
            return path
    if _served_without_language_prefix(path):
        return path
    # The full code, not its language part: with a locale such as "zh-hans",
    # truncating to "zh" emits links that i18n_patterns cannot route.
    return f"/{get_language() or settings.LANGUAGE_CODE}{path}"

{% endif %}
#: What an entry renders as when its destination cannot be resolved. It is a
#: single "#" on purpose: an empty href reloads the current page, and anything
#: built by concatenation leaks a broken value into the markup - a chosen page
#: with no URL and an anchor of "#team" used to render as "##team".
UNRESOLVED_HREF = "#"


@register.filter
def nav_href(value):
    """Resolve a link block value (page, document or url) to an href.

    Accepts any block exposing ``page`` / ``document`` / ``url`` children, so the
    menu blocks and the link and button blocks in ``apps.core.blocks`` all render
    through one resolver. When a page is chosen, ``url`` is treated as an in-page
    anchor and appended to the page's own URL.

    A chosen page has no URL when it sits outside every site's page tree, and a
    chosen document can have lost its file. In both cases the entry resolves to
    ``UNRESOLVED_HREF`` and the anchor is dropped: an anchor into a destination we
    cannot address is meaningless, and pretending otherwise puts "##team" or the
    string "None" into the page.
    """
    getter = getattr(value, "get", None)
    if getter is None:
        return UNRESOLVED_HREF
    page = getter("page")
    document = getter("document")
    url = (getter("url") or "").strip()
    if page:
        base = page.url
        if not base:
            return UNRESOLVED_HREF
        return f"{base}{url}" if url.startswith("#") else base
    if document:
        return document.url or UNRESOLVED_HREF
    if not url:
        return UNRESOLVED_HREF
{%- if cookiecutter.languages == "en_ar" %}
    return _localize_internal_path(url)
{%- else %}
    return url
{%- endif %}


def _normalize_nav_path(path):
    """Reduce a path or URL to a comparable pathname: no query, no hash, no trailing slash."""
    if not path:
        return "/"
    path = str(path).strip()
    if path.startswith(("http://", "https://", "//")):
        path = urlparse(path).path or "/"
    path = path.split("?", 1)[0].split("#", 1)[0]
    return path.rstrip("/") or "/"


def _menu_item_matches_path(item, current_path, allow_descendants=False):
    """Whether one menu entry points at the page currently being served.

    Anchor-only entries never match: the browser does not send the fragment to
    the server, so highlighting them is guesswork that belongs to client-side
    scroll spying.
    """
    href = str(nav_href(item))
    if "#" in href:
        return False
    item_path = _normalize_nav_path(href)
    if item_path == current_path:
        return True
    return bool(allow_descendants and item_path != "/" and current_path.startswith(item_path + "/"))


def _iter_menu_descendants(item):
    getter = getattr(item, "get", None)
    if getter is None:
        return
    for child in getter("children") or []:
        yield child
        yield from _iter_menu_descendants(child)


@register.simple_tag(takes_context=True)
def nav_item_active(context, item):
    """True when this entry points at exactly the page being served."""
    request = context.get("request")
    if request is None or item is None:
        return False
    return _menu_item_matches_path(item, _normalize_nav_path(request.path))


@register.simple_tag(takes_context=True)
def nav_branch_active(context, item):
    """True when this entry, or anything under it, covers the page being served.

    Both sides of the comparison carry the same language prefix (the request path
    and ``nav_href``'s output), so active state is language-correct for free.
    """
    request = context.get("request")
    if request is None or item is None:
        return False
    current_path = _normalize_nav_path(request.path)
    if _menu_item_matches_path(item, current_path, allow_descendants=True):
        return True
    return any(
        _menu_item_matches_path(child, current_path, allow_descendants=True)
        for child in _iter_menu_descendants(item)
    )
