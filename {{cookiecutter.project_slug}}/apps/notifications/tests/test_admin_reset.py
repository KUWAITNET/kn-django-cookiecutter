"""The per-field "Reset to default" round-trip, through whichever admin is mounted."""

import pytest
from django.conf import settings
from django.urls import reverse

from apps.notifications.defaults import get_default
from apps.notifications.tests.factories import NotificationTemplateFactory
{% if cookiecutter.stack == "wagtail" %}
RESET_URL_NAME = "notification-templates:reset-field"
EDIT_URL_NAME = "notification-templates:edit"
LIST_URL_NAMES = [
    "notification-recipients:index",
    "notification-templates:index",
    "notification-log:index",
]
{%- else %}
RESET_URL_NAME = "admin:notifications_notificationtemplate_reset_field"
EDIT_URL_NAME = "admin:notifications_notificationtemplate_change"
LIST_URL_NAMES = [
    "admin:notifications_notificationrecipient_changelist",
    "admin:notifications_notificationtemplate_changelist",
    "admin:post_office_email_changelist",
]
{%- endif %}


@pytest.fixture
def admin_client_logged_in(client, django_user_model):
    user = django_user_model.objects.create_superuser(
        username="editor", email="editor@example.com", password="test-password-123"
    )
    client.force_login(user)
    return client


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", LIST_URL_NAMES)
def test_every_listing_renders(admin_client_logged_in, url_name):
    """Recipients, copy and the delivery log: the client's three questions."""
    NotificationTemplateFactory(language=settings.LANGUAGE_CODE)

    assert admin_client_logged_in.get(reverse(url_name)).status_code == 200


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
    assert template.body == get_default(
        template.trigger, template.recipient_type, template.language, "body"
    )


@pytest.mark.django_db
def test_only_allowlisted_fields_can_be_reset(admin_client_logged_in):
    """The field name comes from the URL, so it is an allowlist, not a denylist."""
    template = NotificationTemplateFactory(language=settings.LANGUAGE_CODE)

    # follow=True because a bilingual site's LocaleMiddleware answers a 404 with
    # a redirect to the language-prefixed path first.
    response = admin_client_logged_in.get(
        reverse(RESET_URL_NAME, args=[template.pk, "updated_at"]), follow=True
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_reset_requires_a_logged_in_editor(client):
    template = NotificationTemplateFactory(language=settings.LANGUAGE_CODE, body="Edited body")

    response = client.post(reverse(RESET_URL_NAME, args=[template.pk, "body"]))

    assert response.status_code in (302, 403)
    template.refresh_from_db()
    assert template.body == "Edited body"
