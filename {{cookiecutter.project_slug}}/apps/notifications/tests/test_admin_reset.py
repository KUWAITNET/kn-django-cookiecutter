"""The per-field "Reset to default" round-trip, through whichever admin is mounted."""

import pytest
from django.conf import settings
from django.urls import reverse

from apps.notifications.defaults import get_default
from apps.notifications.tests.factories import NotificationTemplateFactory
{% if cookiecutter.stack == "wagtail" %}
RESET_URL_NAME = "notification-templates:reset-field"
EDIT_URL_NAME = "notification-templates:edit"
{%- else %}
RESET_URL_NAME = "admin:notifications_notificationtemplate_reset_field"
EDIT_URL_NAME = "admin:notifications_notificationtemplate_change"
{%- endif %}


@pytest.fixture
def admin_client_logged_in(client, django_user_model):
    user = django_user_model.objects.create_superuser(
        username="editor", email="editor@example.com", password="test-password-123"
    )
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_edit_page_offers_a_reset_link(admin_client_logged_in):
    template = NotificationTemplateFactory(language=settings.LANGUAGE_CODE)

    response = admin_client_logged_in.get(reverse(EDIT_URL_NAME, args=[template.pk]))

    assert response.status_code == 200
    assert "Reset to default" in response.content.decode()


@pytest.mark.django_db
def test_reset_confirms_before_it_changes_anything(admin_client_logged_in):
    template = NotificationTemplateFactory(language=settings.LANGUAGE_CODE, body="Edited body")

    response = admin_client_logged_in.get(reverse(RESET_URL_NAME, args=[template.pk, "body"]))

    assert response.status_code == 200
    template.refresh_from_db()
    assert template.body == "Edited body"


@pytest.mark.django_db
def test_reset_restores_the_built_in_body(admin_client_logged_in):
    template = NotificationTemplateFactory(language=settings.LANGUAGE_CODE, body="Edited body")

    response = admin_client_logged_in.post(reverse(RESET_URL_NAME, args=[template.pk, "body"]))

    assert response.status_code == 302
    template.refresh_from_db()
    assert template.body == get_default(template.trigger, template.language, "body")


@pytest.mark.django_db
def test_only_allowlisted_fields_can_be_reset(admin_client_logged_in):
    """The field name comes from the URL, so it is an allowlist, not a denylist."""
    template = NotificationTemplateFactory(language=settings.LANGUAGE_CODE)

    response = admin_client_logged_in.get(
        reverse(RESET_URL_NAME, args=[template.pk, "updated_at"])
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_reset_requires_a_logged_in_editor(client):
    template = NotificationTemplateFactory(language=settings.LANGUAGE_CODE, body="Edited body")

    response = client.post(reverse(RESET_URL_NAME, args=[template.pk, "body"]))

    assert response.status_code in (302, 403)
    template.refresh_from_db()
    assert template.body == "Edited body"
