"""Small cross-app helpers, tied to no app's domain models.

Deliberately free of module-level imports from ``apps.core.emails``: in the
reference project ``utils`` imported the e-mail/branding stack at module scope,
so importing one three-line string helper dragged in templates, settings models
and the mail backend, and the module could not be reused anywhere else.
"""

from urllib.parse import urljoin{% if cookiecutter.languages == "en_ar" %}, urlsplit, urlunsplit{% endif %}

from django.conf import settings
{%- if cookiecutter.stack == "wagtail" and cookiecutter.languages == "en_ar" %}
from django.utils import translation
{%- endif %}
from django.utils.html import strip_tags
from django.utils.translation import get_language, get_language_info

#: Unicode bidirectional isolates. U+2066 opens a left-to-right isolate and
#: U+2069 closes it; everything between is laid out LTR and cannot reorder the
#: text around it.
LTR_ISOLATE = "\u2066"
POP_DIRECTIONAL_ISOLATE = "\u2069"


def ltr_isolate(value):
    """Wrap ``value`` so it always reads left-to-right, e.g. ``+965 2234 5678``.

    A phone number mixes "+" (bidi-neutral) with digits (strongly LTR). Dropped
    into an Arabic paragraph, Unicode's bidirectional algorithm moves the "+" to
    the wrong end and a leading zero can jump across a separator. The isolate
    characters fix it in plain text as well as HTML, which matters because e-mail
    clients routinely strip the CSS (``unicode-bidi: isolate``) that would
    otherwise do the same job. Visually a no-op in an LTR context, so it is safe
    to apply unconditionally.
    """
    if not value:
        return value
    return f"{LTR_ISOLATE}{value}{POP_DIRECTIONAL_ISOLATE}"


def active_language_prefix() -> str:
    """The active language code, as it appears in a URL prefix.

    Never truncated at the hyphen. Django's ``LocalePrefixPattern`` routes the
    full code, so shortening ``zh-hans`` to ``zh`` produces links that 404 - a
    bug the reference project had in four separate copies of this snippet.
    """
    return get_language() or settings.LANGUAGE_CODE


def absolute_url(path: str) -> str:
    """Make ``path`` absolute against ``BASE_URL``.

    Used for canonical links, e-mail bodies and anything else that leaves the
    request cycle, where a root-relative path is useless.
    """
    if not path:
        return settings.BASE_URL
    if path.startswith(("http://", "https://")):
        return path
    return urljoin(f"{settings.BASE_URL.rstrip('/')}/", path.lstrip("/"))


def static_absolute_url(static_path: str) -> str:
    """Absolute URL of a static file, or "" when it has not been collected.

    ``static()`` is resolved here, in Python, and never in a template: under a
    hashed manifest storage a missing entry raises, and a raise inside a rendered
    page is a 500 on every page that includes it.
    """
    from django.templatetags.static import static

    try:
        return absolute_url(static(static_path))
    except ValueError:
        return ""


def swap_language_prefix(path: str, language_code: str) -> str:
    """Replace whatever language prefix ``path`` carries with ``language_code``."""
    for code, _label in settings.LANGUAGES:
        prefix = f"/{code}"
        if path.startswith(f"{prefix}/"):
            path = path[len(prefix) :]
            break
        if path in (prefix, f"{prefix}/"):
            path = "/"
            break
    if not path.startswith("/"):
        path = f"/{path}"
    return f"/{language_code}{path}"


def url_in_language(request, language_code: str, page=None) -> str:
    """The current page's path under ``language_code``, or "" if it has none.

    The single primitive behind the language switcher, the ``hreflang``
    alternates and ``og:locale:alternate`` - written once so those three can
    never disagree.

    Three things it has to get right, all of which the reference implementation
    got wrong:

    * **translated slugs.** Slugs are per-language, so swapping only the prefix
      turns ``/en/about/`` into ``/ar/about/`` and 404s whenever the Arabic slug
      differs. Re-rendering the page's own URL under the target language is the
      only correct answer.
    * **the query string.** Switching language on ``?page=3&category=x`` must not
      throw away the pagination and filters the visitor chose.
    * **an unknown code.** A typo must not emit a prefix that 404s.
    """
{%- if cookiecutter.languages == "en_ar" %}
    from django.urls import translate_url

    if language_code not in dict(settings.LANGUAGES):
        return ""
    full_path = request.get_full_path() if request is not None else "/"
    _scheme, _netloc, path, query, fragment = urlsplit(full_path)
{%- if cookiecutter.stack == "wagtail" %}

    # Stashed by the before_serve_page hook in apps.core.wagtail_hooks, because
    # nothing else makes the page being served visible outside the view.
    page = page if page is not None else getattr(request, "wagtail_page", None)
    if page is not None:
        with translation.override(language_code):
            page_url = page.get_url(request=request)
        if not page_url:
            return ""
        return urlunsplit(("", "", page_url, query, fragment))
{%- endif %}

    # A named URL pattern can itself be translated; translate_url reverses the
    # current match under the target language and returns the input unchanged
    # when it cannot.
    translated = translate_url(path, language_code)
    if translated != path:
        return urlunsplit(("", "", translated, query, fragment))
    return urlunsplit(("", "", swap_language_prefix(path, language_code), query, fragment))
{%- else %}
    # Single-language project: there is no other language to point at, and no
    # language prefix in the URLs.
    if language_code != settings.LANGUAGE_CODE:
        return ""
    return request.get_full_path() if request is not None else "/"
{%- endif %}


def language_alternatives(request, page=None) -> list[dict]:
    """Every configured language, with this page's URL in it.

    Feeds ``hreflang``/``x-default``, ``og:locale``, and the language switcher.
    ``url`` is empty when the page has no version in that language, so a template
    can skip the alternate rather than emit one that 404s.
    """
    current = get_language() or settings.LANGUAGE_CODE
    alternatives = []
    for code, label in settings.LANGUAGES:
        try:
            info = get_language_info(code)
            name, name_local, bidi = info["name"], info["name_local"], info["bidi"]
        except KeyError:
            # A locale Django does not ship metadata for: fall back to the label.
            name = name_local = str(label)
            bidi = False
        path = url_in_language(request, code, page=page)
        # Built from BASE_URL, never from the request host. rel=canonical and
        # og:url are absolute against BASE_URL, and an hreflang set that pointed at
        # a different origin would contradict them - two conflicting signals about
        # which URL is authoritative, which is worse than emitting neither.
        url = absolute_url(path) if path else ""
        alternatives.append(
            {
                "code": code,
                "name": name,
                "name_local": name_local,
                "bidi": bidi,
                "url": url,
                "is_current": code == current,
            }
        )
    return alternatives


def get_client_ip(request) -> str:
    """The client's IP, honouring one proxy hop.

    Only ``REMOTE_ADDR`` is trustworthy; ``X-Forwarded-For`` is client-supplied
    unless the proxy overwrites it. Use this for logging and Turnstile, never as
    an authorisation input.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def has_rich_text_content(html) -> bool:
    """Whether a rich-text value holds real text rather than just markup.

    An "empty" rich-text field still serialises to a non-empty string such as
    ``<p></p>``, so a plain truthiness test cannot tell it apart from content.
    """
    return bool(strip_tags(html or "").strip())


def flatten_formset_errors(formset) -> dict:
    """Flatten a formset's per-row errors into one ``{field_name: [...]}`` dict.

    Keys use each row's fully prefixed field name (``contacts-0-email``), so a
    client-side renderer that matches errors to inputs by ``[name="..."]`` needs
    no special case for formsets.
    """
    errors: dict[str, list] = {}
    for subform in formset.forms:
        for field, field_errors in subform.errors.items():
            errors[subform.add_prefix(field)] = list(field_errors)
    non_form_errors = formset.non_form_errors()
    if non_form_errors:
        errors["__all__"] = list(errors.get("__all__", [])) + list(non_form_errors)
    return errors


def get_admin_edit_url(instance) -> str | None:
    """Absolute admin edit URL for ``instance``, or ``None`` if it has none.

    Notification e-mails link staff straight at the record that triggered them.
    """
{%- if cookiecutter.stack == "wagtail" %}
    # Imported here, not at module scope: this module must stay importable from
    # anything, including code that runs before the app registry is ready.
    from wagtail.admin.admin_url_finder import AdminURLFinder

    relative_url = AdminURLFinder().get_edit_url(instance)
    return absolute_url(relative_url) if relative_url else None
{%- else %}
    from django.urls import NoReverseMatch, reverse

    meta = instance._meta
    try:
        relative_url = reverse(
            f"admin:{meta.app_label}_{meta.model_name}_change", args=[instance.pk]
        )
    except NoReverseMatch:
        return None
    return absolute_url(relative_url)
{%- endif %}
