"""Server-side validation on the reference public form.

Every rejection path here is one the browser also checks. That is the point: the
browser's checks are for people, and an attacker does not use a browser.
"""

import pytest

from apps.contact.forms import ContactForm
from apps.contact.models import ContactSubmission
from apps.contact.tests.conftest import VALID_KUWAIT_E164


@pytest.mark.django_db
def test_a_complete_submission_is_accepted_and_stored(form_data):
    form = ContactForm(data=form_data)

    assert form.is_valid(), form.errors
    submission = form.save()

    assert ContactSubmission.objects.count() == 1
    assert submission.full_name == "Aisha Al-Salem"
    assert submission.message.startswith("Please send")


@pytest.mark.django_db
@pytest.mark.parametrize("field", ["full_name", "email", "subject", "message", "enquiry_type"])
def test_a_missing_required_field_is_rejected(form_data, field):
    form = ContactForm(data={**form_data, field: ""})

    assert not form.is_valid()
    assert field in form.errors


@pytest.mark.django_db
def test_an_invalid_email_is_rejected(form_data):
    form = ContactForm(data={**form_data, "email": "not-an-address"})

    assert not form.is_valid()
    assert "email" in form.errors


@pytest.mark.django_db
def test_an_enquiry_type_outside_the_choices_is_rejected(form_data):
    # The select is a hint. The value arriving on the wire is what matters.
    form = ContactForm(data={**form_data, "enquiry_type": "board-takeover"})

    assert not form.is_valid()
    assert "enquiry_type" in form.errors


@pytest.mark.django_db
def test_the_phone_number_is_normalised_to_e164(form_data):
    form = ContactForm(data=form_data)

    assert form.is_valid(), form.errors
    submission = form.save()

    assert str(submission.phone) == VALID_KUWAIT_E164


@pytest.mark.django_db
def test_a_phone_number_written_with_separators_is_accepted(form_data):
{%- if cookiecutter.countries_app != "none" %}
    form = ContactForm(data={**form_data, "mobile_no": "2234 - 5678"})
{%- else %}
    form = ContactForm(data={**form_data, "mobile_no": "+965 2234 - 5678"})
{%- endif %}

    assert form.is_valid(), form.errors
    assert form.save().phone == VALID_KUWAIT_E164


@pytest.mark.django_db
def test_a_number_that_cannot_exist_is_rejected(form_data):
    # Parses fine as a string; is not a number Kuwait's plan can issue.
{%- if cookiecutter.countries_app != "none" %}
    form = ContactForm(data={**form_data, "mobile_no": "123"})
{%- else %}
    form = ContactForm(data={**form_data, "mobile_no": "+965123"})
{%- endif %}

    assert not form.is_valid()
    assert "mobile_no" in form.errors
{%- if cookiecutter.countries_app != "none" %}


@pytest.mark.django_db
def test_a_number_without_a_country_code_is_rejected(form_data):
    form = ContactForm(data={**form_data, "country_code": ""})

    assert not form.is_valid()
    assert "country_code" in form.errors


@pytest.mark.django_db
def test_the_phone_is_optional(form_data):
    form = ContactForm(data={**form_data, "country_code": "", "mobile_no": ""})

    assert form.is_valid(), form.errors
    assert form.save().phone == ""
{%- else %}


@pytest.mark.django_db
def test_a_number_without_the_international_prefix_is_rejected(form_data):
    # With no dial-code field there is nothing to infer a region from, so a
    # number typed as if it were local cannot be turned into E.164.
    form = ContactForm(data={**form_data, "mobile_no": "22345678"})

    assert not form.is_valid()
    assert "mobile_no" in form.errors


@pytest.mark.django_db
def test_the_phone_is_optional(form_data):
    form = ContactForm(data={**form_data, "mobile_no": ""})

    assert form.is_valid(), form.errors
    assert form.save().phone == ""
{%- endif %}
{%- if cookiecutter.countries_app == "cities" %}


@pytest.mark.django_db
def test_an_inactive_country_cannot_be_submitted(form_data, country):
    country.is_active = False
    country.save(update_fields=["is_active"])

    form = ContactForm(data=form_data)

    # The queryset narrowing is validation, not decoration: a country removed
    # from the dropdown must also be refused when it is posted anyway.
    assert not form.is_valid()
    assert "country" in form.errors


@pytest.mark.django_db
def test_the_country_choices_come_from_the_shared_contract(country):
    # Nothing re-implements the policy: the form asks apps.core.countries, which
    # is the only module that knows which backend this project has.
    from apps.core.countries import country_choices

    form = ContactForm()
    offered = {selectable.code2 for selectable in form.fields["country"].queryset}

    assert offered == {code for code, _label in country_choices()}
{%- elif cookiecutter.countries_app == "django_countries" %}


@pytest.mark.django_db
def test_a_code_that_is_not_a_country_is_rejected(form_data):
    form = ContactForm(data={**form_data, "country": "ZZ"})

    assert not form.is_valid()
    assert "country" in form.errors


@pytest.mark.django_db
def test_an_excluded_country_cannot_be_submitted(form_data, settings):
    # The exclusion is validation, not decoration: a country removed from the
    # dropdown must also be refused when it is posted anyway.
    settings.COUNTRY_EXCLUDED_CODES = ["KW"]

    form = ContactForm(data=form_data)

    assert not form.is_valid()
    assert "country" in form.errors


@pytest.mark.django_db
def test_the_country_choices_come_from_the_shared_contract():
    # Nothing re-implements the policy: the form asks apps.core.countries, which
    # is the only module that knows which backend this project has.
    from apps.core.countries import country_choices

    form = ContactForm()
    offered = {value for value, _label in form.fields["country"].choices if value}

    assert offered == {code for code, _label in country_choices()}
{%- endif %}
{%- if cookiecutter.countries_app != "none" %}


@pytest.mark.django_db
def test_the_country_code_choices_come_from_the_shared_contract({% if cookiecutter.countries_app == "cities" %}country{% endif %}):
    from apps.core.countries import phone_code_choices

    form = ContactForm()
    offered = {value for value, _label in form.fields["country_code"].choices if value}

    assert offered == {value for value, _label in phone_code_choices()}
    assert "+965" in offered


@pytest.mark.django_db
def test_a_dial_code_that_is_not_offered_is_rejected(form_data):
    form = ContactForm(data={**form_data, "country_code": "+999"})

    assert not form.is_valid()
    assert "country_code" in form.errors
{%- else %}


@pytest.mark.django_db
def test_the_form_carries_no_country_or_dial_code_field():
    form = ContactForm()

    assert "country" not in form.fields
    assert "country_code" not in form.fields
{%- endif %}


# --- Attachments --------------------------------------------------------------


@pytest.mark.django_db
def test_a_valid_attachment_is_accepted_and_the_original_name_is_kept(
    form_data, upload_file, pdf_bytes
):
    form = ContactForm(
        data=form_data,
        files={"attachment": upload_file("specification.pdf", pdf_bytes, "application/pdf")},
    )

    assert form.is_valid(), form.errors
    submission = form.save()

    assert submission.attachment_original_name == "specification.pdf"
    # The name on disk is generated, so nothing an attacker chose reaches the
    # filesystem and stored files cannot be found by guessing a person's name.
    assert not submission.attachment.name.endswith("specification.pdf")


@pytest.mark.django_db
def test_a_path_in_the_uploaded_name_never_reaches_the_stored_name(
    form_data, upload_file, pdf_bytes
):
    form = ContactForm(
        data=form_data,
        files={"attachment": upload_file("../../etc/passwd.pdf", pdf_bytes, "application/pdf")},
    )

    assert form.is_valid(), form.errors
    submission = form.save()

    assert ".." not in submission.attachment.name
    assert ".." not in submission.attachment_original_name


@pytest.mark.django_db
def test_a_disallowed_extension_is_rejected(form_data, upload_file):
    form = ContactForm(
        data=form_data,
        files={"attachment": upload_file("payload.svg", b"<svg onload=alert(1)>", "image/svg+xml")},
    )

    assert not form.is_valid()
    assert "attachment" in form.errors


@pytest.mark.django_db
def test_an_oversized_attachment_is_rejected(form_data, upload_file):
    from apps.contact.models import ATTACHMENT_MAX_MB

    oversized = b"%PDF-1.4\n" + b"0" * ((ATTACHMENT_MAX_MB + 1) * 1024 * 1024)
    form = ContactForm(
        data=form_data,
        files={"attachment": upload_file("huge.pdf", oversized, "application/pdf")},
    )

    assert not form.is_valid()
    assert "attachment" in form.errors


@pytest.mark.django_db
def test_content_that_does_not_match_the_extension_is_rejected(form_data, upload_file, png_bytes):
    # A PNG renamed to .pdf gets past an extension check, past the browser's
    # accept= filter, and past a content_type the client chose. libmagic reads
    # the bytes.
    form = ContactForm(
        data=form_data,
        files={"attachment": upload_file("cv.pdf", png_bytes, "application/pdf")},
    )

    assert not form.is_valid()
    assert "attachment" in form.errors


@pytest.mark.django_db
def test_the_attachment_is_optional(form_data):
    form = ContactForm(data=form_data)

    assert form.is_valid(), form.errors
    assert not form.save().attachment
{%- if cookiecutter.spam_protection != "none" %}


# --- Bot protection -----------------------------------------------------------


@pytest.mark.django_db
def test_the_form_carries_protection_fields(form_data):
    # The template renders these generically, so renaming the honeypot per
    # project stays a configuration change rather than a template edit.
    assert ContactForm().protection_fields


@pytest.mark.django_db
def test_a_filled_honeypot_is_rejected(form_data):
    from apps.core.spam import HONEYPOT_FIELD_NAME

    form = ContactForm(data={**form_data, HONEYPOT_FIELD_NAME: "http://spam.example"})

    assert not form.is_valid()
    assert ContactSubmission.objects.count() == 0
{%- endif %}
