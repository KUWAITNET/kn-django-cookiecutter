"""The countries contract in :mod:`apps.core.countries`.

Written against the contract rather than against the backend, because the point
of that module is that a form, a serializer or an admin never learns which
backend it got. What differs below is only what genuinely differs between the
two: what a country is stored as, and where a dial code comes from.
"""

{% if cookiecutter.countries_app != "django_countries" -%}
import pytest

{% endif -%}
{% if cookiecutter.countries_app == "cities" -%}
from apps.cities.models import Country
{% endif -%}
from apps.core.countries import (
    country_choices,
    country_display,
    country_form_field,
    country_model_field,
    phone_code_choices,
)
{%- if cookiecutter.countries_app == "cities" %}


@pytest.fixture
def countries(db):
    """Three rows covering the cases the policy has to keep apart."""
    return {
        "active": Country.objects.create(
            name="Kuwait", code2="KW", code3="KWT", continent="AS", phone="965"
        ),
        "inactive": Country.objects.create(
            name="Nowhere", code2="NW", code3="NWX", continent="AS", phone="998", is_active=False
        ),
        "no_phone": Country.objects.create(
            name="Phoneless", code2="PL", code3="PLX", continent="AS", phone=""
        ),
    }


@pytest.mark.django_db
def test_country_choices_offers_only_selectable_countries(countries):
    assert {code for code, _label in country_choices()} == {"KW", "PL"}


@pytest.mark.django_db
def test_country_choices_honours_the_exclusion_setting(countries, settings):
    # Through Country.objects.selectable(), which remains the single source of
    # truth on this backend: this module adds no filter of its own.
    settings.COUNTRY_EXCLUDED_CODES = ["KW"]

    assert {code for code, _label in country_choices()} == {"PL"}


@pytest.mark.django_db
def test_phone_code_choices_drop_countries_with_no_dial_code(countries):
    assert phone_code_choices() == [("+965", "Kuwait (+965)")]


@pytest.mark.django_db
def test_country_display_reads_the_localised_name(countries):
    assert country_display(countries["active"]) == "Kuwait"
    assert country_display(countries["active"].pk) == "Kuwait"
    assert country_display(None) == ""


def test_the_model_field_is_a_protected_reference():
    from django.db import models

    field = country_model_field()

    assert isinstance(field, models.ForeignKey)
    # PROTECT: a submission must never lose its country to a deleted reference row.
    assert field.remote_field.on_delete is models.PROTECT


@pytest.mark.django_db
def test_the_form_field_offers_exactly_the_selectable_countries(countries):
    assert set(country_form_field().queryset) == set(Country.objects.selectable())
{%- elif cookiecutter.countries_app == "django_countries" %}


def test_the_installed_package_is_the_kuwaitnet_fork():
    """Where the data came from is the whole point of this backend.

    The country-list policy lives in the shipped data rather than in a filter, so
    upstream django-countries from PyPI would install cleanly, pass every other
    test on this page, and silently reinstate what the fork removes. PEP 610
    records where a distribution actually came from; nothing else notices.
    """
    from importlib.metadata import distribution

    origin = distribution("django-countries").read_text("direct_url.json") or ""

    assert "KUWAITNET/django-countries" in origin


def test_country_choices_are_alpha_2_codes_with_readable_names():
    choices = dict(country_choices())

    assert choices["KW"] == "Kuwait"
    # No table and no import step: the list is the data the package ships.
    assert len(choices) > 200


def test_country_choices_honour_the_exclusion_setting(settings):
    settings.COUNTRY_EXCLUDED_CODES = ["KW", "qa"]

    codes = {code for code, _label in country_choices()}

    # Case-insensitive, because the value is typed by a person into an
    # environment variable.
    assert "KW" not in codes
    assert "QA" not in codes
    assert "SA" in codes


def test_phone_code_choices_are_derived_from_phonenumbers():
    import phonenumbers

    choices = dict(phone_code_choices())

    assert choices["+965"] == "Kuwait (+965)"
    # The same library that validates the submitted number, so the select can
    # never offer a code the validator would then reject.
    assert f"+{phonenumbers.country_code_for_region('KW')}" in choices


def test_phone_code_choices_never_offer_a_blank_code():
    # A region phonenumbers has no calling code for is skipped, and there are
    # several: a blank option in a dial-code select produces an unparseable
    # number.
    codes = [dial_code for dial_code, _label in phone_code_choices()]

    assert codes
    assert all(dial_code.startswith("+") and dial_code[1:].isdigit() for dial_code in codes)
    assert len(codes) < len(country_choices())


def test_country_display_reads_the_stored_code():
    assert country_display("KW") == "Kuwait"
    assert country_display("") == ""
    assert country_display(None) == ""


def test_the_model_field_stores_the_code_itself():
    from django_countries.fields import CountryField

    assert isinstance(country_model_field(), CountryField)


def test_the_form_field_offers_exactly_the_country_choices():
    offered = {value for value, _label in country_form_field().choices if value}

    assert offered == {code for code, _label in country_choices()}
{%- else %}


def test_there_are_no_countries_to_offer():
    assert country_choices() == []
    assert phone_code_choices() == []


def test_a_field_factory_refuses_rather_than_returning_something_unusable():
    from django.core.exceptions import ImproperlyConfigured

    # A model that silently loses its country column is far harder to notice than
    # a boot failure, so this refuses loudly.
    with pytest.raises(ImproperlyConfigured):
        country_model_field()
    with pytest.raises(ImproperlyConfigured):
        country_form_field()


def test_country_display_degrades_instead_of_raising():
    assert country_display(None) == ""
    assert country_display("KW") == "KW"
{%- endif %}
