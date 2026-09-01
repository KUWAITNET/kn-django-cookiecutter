"""One country contract, whichever countries backend the project was generated with.

A KUWAITNET project picks one of two country backends, and they have almost
nothing in common at the code level: one stores a foreign key to an imported
reference table, the other stores a two-letter code in a character column. Every
form, model, serializer, admin and template that touches a country would
otherwise have to know which one it got - and that knowledge, copy-pasted, is
exactly the defect this template exists to prevent.

So the rest of the project imports from here and never from a backend directly.
The five callables below are the whole contract, and they mean the same thing on
every backend:

===========================  ==================================================
``country_choices()``        ``[(alpha-2 code, localised name), ...]``
``phone_code_choices()``     ``[("+965", "Kuwait (+965)"), ...]``
``country_model_field()``    the model field that stores a country
``country_form_field()``     the form field that picks one
``country_display(value)``   the readable name of a stored value
===========================  ==================================================
{% if cookiecutter.countries_app == "cities" %}
This project uses the ``apps.cities`` backend. ``Country.objects.selectable()``
remains the single source of truth for "a country a visitor may pick": the
functions here read it and add nothing of their own, so deactivating a country in
the admin removes it from every consumer at once. Nothing may re-implement that
filter - in the project this template is derived from it was copy-pasted into
five forms and one copy had already drifted.

The country list is empty until ``manage.py cities_light`` has imported the
GeoNames data.
{%- elif cookiecutter.countries_app == "django_countries" %}
This project uses the KUWAITNET fork of ``django-countries``. There is no table
and no import step: the list is the data the package ships, and the country-list
policy is applied to that data rather than to a queryset - which is the point of
the fork, because data cannot be filtered back in by a caller who forgets.

``COUNTRY_EXCLUDED_CODES`` is still honoured here and is normally empty; it
exists for the per-client exclusions that are a commercial decision rather than a
company one.
{%- else %}
This project was generated with no countries backend. The contract still exists,
so a form or a template that reads it degrades to "no countries" instead of
raising: the choice lists are empty and there is no country field to build. Add a
backend by regenerating with ``countries_app`` set, not by importing a country
library here - a second, undocumented country list is the failure this module
prevents.
{%- endif %}
"""
{%- if cookiecutter.countries_app == "cities" %}

from django import forms
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.cities.models import Country

#: The same wording on both backends, so a project that switches does not have to
#: re-translate its own form.
COUNTRY_FIELD_ERRORS = {
    "required": _("Please select your country."),
    "invalid_choice": _("Select a country from the list."),
}


def country_choices() -> list[tuple[str, str]]:
    """Countries an end user may pick, as (alpha-2 code, localised name)."""
    return [(country.code2, country.localized_name) for country in Country.objects.selectable()]


def phone_code_choices() -> list[tuple[str, str]]:
    """Dial codes for the country-code select, as (``"+965"``, label).

    Read from the imported GeoNames column via ``with_phone_code()``, which drops
    the territories that share another country's calling code: a blank option in a
    dial-code select produces an unparseable number.
    """
    return [
        (country.phone_code, f"{country.localized_name} ({country.phone_code})")
        for country in Country.objects.with_phone_code()
    ]


def country_model_field(**kwargs):
    """The model field that stores a country on this backend."""
    # PROTECT because a submission must never lose its country to a deleted
    # reference row; the country admin deactivates rather than deletes for the
    # same reason. related_name="+" because nothing walks back from a country.
    kwargs.setdefault("on_delete", models.PROTECT)
    kwargs.setdefault("related_name", "+")
    kwargs.setdefault("verbose_name", _("country"))
    return models.ForeignKey("cities.Country", **kwargs)


def country_form_field(**kwargs):
    """The form field that picks a country on this backend."""
    kwargs.setdefault("label", _("Country"))
    kwargs.setdefault("empty_label", _("Select a country"))
    kwargs.setdefault("error_messages", dict(COUNTRY_FIELD_ERRORS))
    # The queryset, not a snapshot of it: a country deactivated after the process
    # started must be refused by the next submission, not by the next deploy.
    return forms.ModelChoiceField(queryset=Country.objects.selectable(), **kwargs)


def country_display(value) -> str:
    """The readable name for a stored country. Empty string when there is none."""
    if not value:
        return ""
    if isinstance(value, Country):
        return value.localized_name
    country = Country.objects.filter(pk=value).first()
    return country.localized_name if country else str(value)
{%- elif cookiecutter.countries_app == "django_countries" %}

import phonenumbers
from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django_countries import countries
from django_countries.fields import CountryField

#: The same wording on both backends, so a project that switches does not have to
#: re-translate its own form.
COUNTRY_FIELD_ERRORS = {
    "required": _("Please select your country."),
    "invalid_choice": _("Select a country from the list."),
}


def _excluded_codes() -> set[str]:
    """Per-client exclusions, normalised. Normally empty on this backend."""
    configured = getattr(settings, "COUNTRY_EXCLUDED_CODES", ())
    return {str(code).strip().upper() for code in configured if str(code).strip()}


def country_choices() -> list[tuple[str, str]]:
    """Countries an end user may pick, as (alpha-2 code, localised name).

    ``countries`` yields the shipped list already sorted by name in the active
    language, so the order follows the language rather than the code.
    """
    excluded = _excluded_codes()
    return [(code, str(name)) for code, name in countries if code not in excluded]


def phone_code_choices() -> list[tuple[str, str]]:
    """Dial codes for the country-code select, as (``"+965"``, label).

    This backend ships no dial codes, so the calling code comes from
    ``phonenumbers`` - the same library that validates the submitted number. One
    source for both means the select can never offer a code the validator would
    then reject. Regions ``phonenumbers`` has no calling code for are skipped: a
    blank option in a dial-code select produces an unparseable number.
    """
    choices = []
    for code, name in country_choices():
        calling_code = phonenumbers.country_code_for_region(code)
        if not calling_code:
            continue
        dial_code = f"+{calling_code}"
        choices.append((dial_code, f"{name} ({dial_code})"))
    return choices


def country_model_field(**kwargs):
    """The model field that stores a country on this backend."""
    kwargs.setdefault("verbose_name", _("country"))
    return CountryField(**kwargs)


def country_form_field(**kwargs):
    """The form field that picks a country on this backend.

    A plain ``ChoiceField`` over :func:`country_choices` rather than the field
    ``CountryField`` would build for itself, because that one offers the package's
    whole list and would ignore ``COUNTRY_EXCLUDED_CODES``.
    """
    kwargs.setdefault("label", _("Country"))
    kwargs.setdefault("error_messages", dict(COUNTRY_FIELD_ERRORS))
    # A callable, so the list is rebuilt per request: the names are translated and
    # the exclusions are a setting, both of which can change under a running
    # process.
    kwargs.setdefault("choices", lambda: [("", _("Select a country"))] + country_choices())
    return forms.ChoiceField(**kwargs)


def country_display(value) -> str:
    """The readable name for a stored country. Empty string when there is none."""
    if not value:
        return ""
    # A stored value is a django-countries Country object, whose .name is already
    # localised; a bare alpha-2 code arrives from a form or an import.
    name = getattr(value, "name", "")
    if name:
        return str(name)
    return str(countries.name(str(value))) or str(value)
{%- else %}

from django.core.exceptions import ImproperlyConfigured

#: Raised rather than returning a field nobody can store into: a model that
#: silently loses its country column is far harder to notice than a boot failure.
NO_BACKEND = (
    "This project was generated without a countries backend. Regenerate with "
    "countries_app set to django_countries or cities, or drop the country field."
)


def country_choices() -> list[tuple[str, str]]:
    """No countries backend, so nothing is offered."""
    return []


def phone_code_choices() -> list[tuple[str, str]]:
    """No countries backend, so no dial-code select is built."""
    return []


def country_model_field(**kwargs):
    """There is no country column to add on this project."""
    raise ImproperlyConfigured(NO_BACKEND)


def country_form_field(**kwargs):
    """There is no country field to render on this project."""
    raise ImproperlyConfigured(NO_BACKEND)


def country_display(value) -> str:
    """Whatever was stored, if anything ever was."""
    return str(value) if value else ""
{%- endif %}
