import pytest
from django.urls import reverse

from apps.newsletter.models import Subscriber
from apps.newsletter.tests.factories import SubscriberFactory


@pytest.fixture
def url():
    return reverse("newsletter:subscribe")


@pytest.mark.django_db
def test_the_signup_page_renders(client, url):
    assert client.get(url).status_code == 200


@pytest.mark.django_db
def test_subscribing_records_the_address_and_mails_a_confirmation_link(client, url, mailoutbox):
    response = client.post(url, {"email": "Reader@Example.com"})

    assert response.status_code == 200
    subscriber = Subscriber.objects.get()
    # Normalised, so the same person cannot end up on the list twice.
    assert subscriber.email == "reader@example.com"
    assert subscriber.is_confirmed is False

    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ["reader@example.com"]
    assert str(subscriber.token) in mailoutbox[0].body


@pytest.mark.django_db
def test_an_already_confirmed_address_is_not_mailed_again(client, url, mailoutbox):
    """Otherwise the endpoint is a way to mail somebody else repeatedly."""
    SubscriberFactory(email="reader@example.com", is_confirmed=True)

    response = client.post(url, {"email": "reader@example.com"})

    assert response.status_code == 200
    assert Subscriber.objects.count() == 1
    assert mailoutbox == []


@pytest.mark.django_db
def test_resubscribing_after_unsubscribing_works(client, url):
    SubscriberFactory(email="reader@example.com", is_confirmed=True, is_active=False)

    client.post(url, {"email": "reader@example.com"})

    subscriber = Subscriber.objects.get()
    assert subscriber.is_active is True
    assert subscriber.unsubscribed_at is None


@pytest.mark.django_db
def test_an_invalid_address_is_rejected_server_side(client, url, mailoutbox):
    response = client.post(url, {"email": "not-an-address"})

    assert response.status_code == 400
    assert not Subscriber.objects.exists()
    assert mailoutbox == []


@pytest.mark.django_db
def test_the_ajax_path_answers_json(client, url):
    response = client.post(
        url, {"email": "reader@example.com"}, headers={"x-requested-with": "XMLHttpRequest"}
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}

{% if cookiecutter.spam_protection != "none" %}
@pytest.mark.django_db
def test_a_bot_that_fills_every_field_it_can_see_is_rejected(client, url, mailoutbox):
    """Whatever apps.core.spam adds - a honeypot, a challenge - filling it must fail."""
    from apps.newsletter.forms import SubscribeForm

    payload = {"email": "bot@example.com"}
    for name in SubscribeForm().fields:
        if name != "email":
            payload[name] = "bot"

    response = client.post(url, payload)

    assert response.status_code == 400
    assert not Subscriber.objects.exists()
    assert mailoutbox == []

{% endif %}{% if cookiecutter.rate_limiting == "yes" %}
@pytest.mark.django_db
def test_subscribing_is_rate_limited(client, url, settings):
    """Each request sends an e-mail, so the budget is deliberately small."""
    from django.core.cache import cache

    settings.RATELIMIT_ENABLE = True
    settings.RATELIMIT_NEWSLETTER = "1/h"
    cache.clear()

    try:
        first = client.post(url, {"email": "one@example.com"})
        second = client.post(url, {"email": "two@example.com"})
    finally:
        cache.clear()

    assert first.status_code == 200
    assert second.status_code == 429
    assert second["Retry-After"] == "3600"
    assert Subscriber.objects.count() == 1

{% endif %}
@pytest.mark.django_db
def test_get_is_allowed_but_put_is_not(client, url):
    assert client.put(url).status_code == 405
