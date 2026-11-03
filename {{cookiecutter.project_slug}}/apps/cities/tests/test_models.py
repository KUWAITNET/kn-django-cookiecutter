"""Country display helpers. No import run needed: one row is enough."""

import pytest
{%- if cookiecutter.languages == "en_ar" %}
from django.utils import translation
{%- endif %}

from apps.cities.models import Country
from apps.cities.utils import NATIONALITY_BY_CODE2, get_nationality


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        ("965", "+965"),
        (" 965 ", "+965"),
        # GeoNames writes calling code + area code for dependent territories, and
        # comma-joins alternatives. Only the leading run is a calling code.
        ("1-340", "+1"),
        ("599,5", "+599"),
        ("", ""),
        (None, ""),
    ],
)
def test_phone_code_normalises_the_geonames_column(stored, expected):
    assert Country(name="X", code2="XX", phone=stored).phone_code == expected


def test_nationality_falls_back_to_the_country_name_for_an_unlisted_code():
    country = Country(name="Atlantis", code2="ZZ")

    assert country.nationality == "Atlantis"


def test_nationality_uses_the_table_when_the_code_is_listed():
    country = Country(name="Kuwait", code2="KW")

    assert country.nationality == NATIONALITY_BY_CODE2["KW"]["en"]


def test_get_nationality_is_case_insensitive_and_falls_back():
    assert get_nationality("kw") == NATIONALITY_BY_CODE2["KW"]["en"]
    assert get_nationality(None, fallback="Unknown") == "Unknown"
    assert get_nationality("ZZ", fallback="Unknown") == "Unknown"


def test_localized_name_prefers_the_editor_override():
    country = Country(name="Kuwait", code2="KW", display_name="State of Kuwait")

    assert country.localized_name == "State of Kuwait"


def test_localized_name_falls_back_to_the_imported_alternate_name():
    country = Country(name="Kuwait", code2="KW", translations={"en": ["Kuwait (alt)"]})

    assert country.localized_name == "Kuwait (alt)"


def test_localized_name_falls_back_to_the_imported_name():
    assert Country(name="Kuwait", code2="KW", translations={}).localized_name == "Kuwait"
{%- if cookiecutter.languages == "en_ar" %}


def test_localized_name_reads_the_active_language():
    country = Country(
        name="Kuwait",
        code2="KW",
        translations={"en": ["Kuwait"], "ar": ["الكويت"]},
    )

    with translation.override("ar"):
        assert country.localized_name == "الكويت"


def test_nationality_reads_the_active_language():
    with translation.override("ar"):
        assert Country(name="Kuwait", code2="KW").nationality == NATIONALITY_BY_CODE2["KW"]["ar"]
{%- endif %}
