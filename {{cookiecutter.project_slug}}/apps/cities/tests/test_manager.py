"""The country-selection policy.

These are the tests that stop the defect this app exists to fix: in the project
this template is derived from the "selectable countries" filter was copy-pasted
into five forms and one copy drifted. The policy now lives in one queryset, and
these tests pin it there.
"""

import pytest
from django.test import override_settings

from apps.cities.models import Country


def make_country(name, code2, *, phone="965", is_active=True):
    return Country.objects.create(
        name=name,
        code2=code2,
        code3=f"{code2}X",
        continent="AS",
        phone=phone,
        is_active=is_active,
    )


@pytest.fixture
def countries(db):
    return {
        "active": make_country("Kuwait", "KW", phone="965"),
        "inactive": make_country("Nowhere", "NW", phone="999", is_active=False),
        "no_phone": make_country("Phoneless", "PL", phone=""),
        "null_phone": make_country("Nullphone", "NP", phone=None),
    }


@pytest.mark.django_db
def test_inactive_country_is_never_selectable(countries):
    selectable = Country.objects.selectable()

    assert countries["active"] in selectable
    assert countries["inactive"] not in selectable


@pytest.mark.django_db
def test_deactivating_removes_a_country_from_every_consumer(countries):
    country = countries["active"]
    country.is_active = False
    country.save(update_fields=["is_active"])

    assert country not in Country.objects.selectable()
    assert country not in Country.objects.with_phone_code()
    assert country not in Country.nationality_choices()


@pytest.mark.django_db
@override_settings(COUNTRY_EXCLUDED_CODES=["KW"])
def test_excluded_codes_are_not_selectable(countries):
    assert countries["active"] not in Country.objects.selectable()


@pytest.mark.django_db
def test_no_exclusions_configured_excludes_nothing(countries):
    # exclude(code2__in=[]) must not silently empty the queryset.
    with override_settings(COUNTRY_EXCLUDED_CODES=[]):
        assert countries["active"] in Country.objects.selectable()


@pytest.mark.django_db
def test_with_phone_code_drops_blank_and_null_dial_codes(countries):
    with_phone = Country.objects.with_phone_code()

    assert countries["active"] in with_phone
    assert countries["no_phone"] not in with_phone
    assert countries["null_phone"] not in with_phone


@pytest.mark.django_db
def test_with_phone_code_is_a_subset_of_selectable(countries):
    # The phone list is derived from the policy, not written alongside it: an
    # inactive country with a dial code must not reach the country-code select.
    inactive_with_phone = countries["inactive"]

    assert inactive_with_phone not in Country.objects.with_phone_code()
    assert set(Country.objects.with_phone_code()) <= set(Country.objects.selectable())


@pytest.mark.django_db
def test_nationality_choices_uses_the_same_policy(countries):
    assert set(Country.nationality_choices()) == set(Country.objects.selectable())
