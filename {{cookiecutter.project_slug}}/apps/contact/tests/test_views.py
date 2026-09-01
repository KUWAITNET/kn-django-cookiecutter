{%- if cookiecutter.frontend != "api_only" %}
"""The submission path and the AJAX contract every KUWAITNET form speaks.

The contract is tested rather than documented-and-hoped-for because the
JavaScript in every form template indexes the error dictionary by input name, so
a change in its shape breaks error display silently.
"""

import pytest
from django.core import mail

from apps.contact.models import ContactSubmission

AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


@pytest.mark.django_db
def test_the_page_renders(client, contact_url):
    response = client.get(contact_url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_an_ajax_submission_returns_ok_and_is_stored(client, contact_url, form_data):
    response = client.post(contact_url, form_data, **AJAX)

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert ContactSubmission.objects.count() == 1


@pytest.mark.django_db
def test_a_submission_notifies_staff(client, contact_url, form_data, settings):
    settings.DEFAULT_ADMIN_EMAIL = "enquiries@example.com"

    client.post(contact_url, form_data, **AJAX)

    # One message, to the configured address. The wording is deliberately not
    # asserted here: {% if cookiecutter.notifications_app == "yes" %}it comes from the admin-editable template when one
    # exists{% else %}it is editable copy{% endif %}, and a test that pins it turns a copy change into a
    # failing build.
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["enquiries@example.com"]


@pytest.mark.django_db
def test_an_invalid_ajax_submission_returns_400_with_field_errors(client, contact_url, form_data):
    response = client.post(contact_url, {**form_data, "email": ""}, **AJAX)

    assert response.status_code == 400
    payload = response.json()
    assert payload["ok"] is False
    # Keyed by input name, which is what the client uses to place the message.
    assert "email" in payload["errors"]
    assert isinstance(payload["errors"]["email"], list)
    assert ContactSubmission.objects.count() == 0


@pytest.mark.django_db
def test_a_non_ajax_submission_re_renders_with_the_submitted_flag(client, contact_url, form_data):
    response = client.post(contact_url, form_data)

    assert response.status_code == 200
    assert response.context["submitted"] is True
    # A fresh form, so the visitor is not shown their message still in the box.
    assert not response.context["form"].is_bound
    assert ContactSubmission.objects.count() == 1


@pytest.mark.django_db
def test_a_non_ajax_invalid_submission_re_renders_with_the_bound_form(
    client, contact_url, form_data
):
    response = client.post(contact_url, {**form_data, "message": ""})

    assert response.status_code == 200
    assert "message" in response.context["form"].errors
    assert ContactSubmission.objects.count() == 0
{%- if cookiecutter.spam_protection != "none" %}


@pytest.mark.django_db
def test_a_filled_honeypot_is_rejected_and_stores_nothing(client, contact_url, form_data):
    from apps.core.spam import HONEYPOT_FIELD_NAME

    response = client.post(
        contact_url,
        {**form_data, HONEYPOT_FIELD_NAME: "http://spam.example"},
        **AJAX,
    )

    assert response.status_code == 400
    assert ContactSubmission.objects.count() == 0
    assert mail.outbox == []
{%- endif %}
{%- if cookiecutter.rate_limiting == "yes" %}


@pytest.mark.django_db
def test_the_submission_budget_is_enforced(client, contact_url, form_data, settings):
    from django.core.cache import cache

    # Rate limiting is off by default in the test settings so unrelated tests are
    # not throttled; this is the one place it is turned on deliberately.
    settings.RATELIMIT_ENABLE = True
    settings.RATELIMIT_FORM_SUBMIT = "1/h"
    cache.clear()

    first = client.post(contact_url, form_data, **AJAX)
    second = client.post(contact_url, form_data, **AJAX)

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["ok"] is False
    # Every submission costs an outbound e-mail; the point of the budget is that
    # the second one does not happen.
    assert ContactSubmission.objects.count() == 1
    cache.clear()


@pytest.mark.django_db
def test_a_get_is_never_rate_limited(client, contact_url, settings):
    from django.core.cache import cache

    settings.RATELIMIT_ENABLE = True
    settings.RATELIMIT_FORM_SUBMIT = "1/h"
    cache.clear()

    assert client.get(contact_url).status_code == 200
    assert client.get(contact_url).status_code == 200
    cache.clear()
{%- endif %}
{%- endif %}
