{% if cookiecutter.languages == "en_ar" -%}
"""Make CMS page URLs language-prefix aware.

One page tree with per-field translations means Wagtail builds page URLs from
``url_path`` alone, which carries no language prefix - so links, menus,
breadcrumbs and the sitemap would all point at bare paths like ``/about/``.
``prefix_default_language=True`` means every public URL has an explicit prefix,
so a bare path is a redirect at best and a 404 at worst.

Patching ``Page.get_url_parts`` once here means every Wagtail URL helper
(``page.url``, ``{% raw %}{% pageurl %}{% endraw %}``, rich-text links, the sitemap) produces the
correct prefixed URL with no call-site changes.

Installed from ``CoreConfig.ready()``.
"""

from django.conf import settings
from django.utils.translation import get_language
from wagtail.models import Page

_original_get_url_parts = Page.get_url_parts


def _strip_language_prefix(page_path: str) -> str:
    """Remove any language prefix already present on ``page_path``."""
    for code, _label in settings.LANGUAGES:
        prefix = f"/{code}"
        if page_path.startswith(f"{prefix}/"):
            return page_path[len(prefix) :]
        if page_path == prefix:
            return "/"
    return page_path


def _localized_get_url_parts(self, request=None):
    parts = _original_get_url_parts(self, request=request)
    if parts is None:
        return parts

    site_id, root_url, page_path = parts
    if page_path is None:
        return parts

    # The full language code, never truncated at the hyphen: Django's
    # LocalePrefixPattern routes "zh-hans", so emitting "/zh/" would 404 every
    # link on the site.
    language = get_language() or settings.LANGUAGE_CODE
    prefix = f"/{language}"
    if not page_path.startswith(f"{prefix}/") and page_path != prefix:
        page_path = prefix + _strip_language_prefix(page_path)

    return (site_id, root_url, page_path)


# Idempotent: ready() runs twice under the autoreloader.
if getattr(Page.get_url_parts, "__name__", "") != "_localized_get_url_parts":
    Page.get_url_parts = _localized_get_url_parts
{%- endif %}
