"""Fixtures shared by the contact-form tests."""

import pytest
{%- if cookiecutter.countries_app == "yes" %}

from apps.cities.models import Country
{%- endif %}

VALID_KUWAIT_NUMBER = "22345678"
VALID_KUWAIT_E164 = "+96522345678"


@pytest.fixture
def pdf_bytes():
    """A real, minimal PDF. The attachment is validated by content, so a fake fails."""
    return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
{%- if cookiecutter.countries_app == "yes" %}


@pytest.fixture
def country(db):
    return Country.objects.create(
        name="Kuwait",
        code2="KW",
        code3="KWT",
        continent="AS",
        phone="965",
        is_active=True,
    )
{%- endif %}


@pytest.fixture
def form_data({% if cookiecutter.countries_app == "yes" %}country{% endif %}):
    """A submission that must always be accepted. Tests break one field at a time."""
    return {
        "full_name": "Aisha Al-Salem",
        "company_name": "Example Trading",
        "email": "aisha@example.com",
{%- if cookiecutter.countries_app == "yes" %}
        "country": str(country.pk),
{%- endif %}
        "country_code": "+965",
        "mobile_no": VALID_KUWAIT_NUMBER,
        "enquiry_type": "sales",
        "subject": "Cable specification",
        "message": "Please send the datasheet for the 11 kV range.",
    }
{% if cookiecutter.frontend != "api_only" %}
{%- if cookiecutter.stack == "wagtail" %}

@pytest.fixture
def contact_page(db):
    """A published contact page under the default site's root."""
    from wagtail.models import Site

    from apps.contact.models import ContactPage

    root = Site.objects.get(is_default_site=True).root_page
    page = ContactPage(title="Contact us", slug="contact")
{%- if cookiecutter.languages == "en_ar" %}
    # Both language columns, or the page renders blank in one of them and
    # url_path is built from a NULL slug.
    page.title_en = page.title_ar = "Contact us"
    page.slug_en = page.slug_ar = "contact"
{%- endif %}
    root.add_child(instance=page)
    return ContactPage.objects.get(pk=page.pk)


@pytest.fixture
def contact_url(contact_page):
{%- if cookiecutter.languages == "en_ar" %}
    # Already language-prefixed: the translated url_path carries it, which is
    # also why a language switcher that only swaps the prefix is wrong.
{%- endif %}
    return contact_page.url
{%- else %}

@pytest.fixture
def contact_url(db):
    from django.urls import reverse

    return reverse("contact:contact")
{%- endif %}
{%- endif %}
