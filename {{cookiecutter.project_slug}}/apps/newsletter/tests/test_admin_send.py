"""The admin composer, through whichever admin is mounted."""

import pytest
from django.conf import settings
from django.urls import reverse

from apps.newsletter.models import AUDIENCE_ALL, Campaign
from apps.newsletter.tests.factories import SubscriberFactory
{% if cookiecutter.stack == "wagtail" %}
SEND_URL_NAME = "send-newsletter:index"
{%- else %}
SEND_URL_NAME = "admin:newsletter_campaign_add"
{%- endif %}


@pytest.fixture
def send_url():
    return reverse(SEND_URL_NAME)


@pytest.fixture
def editor_client(client, django_user_model):
    user = django_user_model.objects.create_superuser(
        username="sender", email="sender@example.com", password="test-password-123"
    )
    client.force_login(user)
    return client


def _payload(audience=AUDIENCE_ALL):
    payload = {"audience": audience}
    for code, _label in settings.LANGUAGES:
        payload[f"subject_{code}"] = f"Subject {code}"
        payload[f"body_{code}"] = f"Body {code}"
    return payload


@pytest.mark.django_db
def test_the_composer_previews_how_many_people_it_would_reach(editor_client, send_url):
    SubscriberFactory.create_batch(2)
    SubscriberFactory(is_active=False)

    response = editor_client.get(send_url)

    assert response.status_code == 200
    content = response.content.decode()
    assert "newsletter-recipient-counts" in content
    assert '"all": 2' in content or '"all":2' in content


@pytest.mark.django_db
def test_composing_and_sending_happen_in_one_step(editor_client, send_url, mailoutbox):
    SubscriberFactory.create_batch(2)

    response = editor_client.post(send_url, _payload())

    assert response.status_code == 302
    assert len(mailoutbox) == 2
    campaign = Campaign.objects.get()
    assert campaign.recipient_count == 2
    assert campaign.sent_by is not None


@pytest.mark.django_db
def test_a_campaign_with_no_copy_is_rejected_before_anything_is_sent(
    editor_client, send_url, mailoutbox
):
    SubscriberFactory()
    payload = {"audience": AUDIENCE_ALL}

    response = editor_client.post(send_url, payload)

    assert response.status_code == 200
    assert mailoutbox == []
    assert not Campaign.objects.exists()


@pytest.mark.django_db
def test_invalid_template_syntax_is_rejected_before_anything_is_sent(
    editor_client, send_url, mailoutbox
):
    SubscriberFactory()
    payload = _payload()
    payload[f"body_{settings.LANGUAGE_CODE}"] = "{% raw %}{% if broken %}{% endraw %}"

    response = editor_client.post(send_url, payload)

    assert response.status_code == 200
    assert mailoutbox == []
    assert not Campaign.objects.exists()


@pytest.mark.django_db
def test_the_composer_is_not_public(client, send_url):
    response = client.get(send_url)

    assert response.status_code in (302, 403)
