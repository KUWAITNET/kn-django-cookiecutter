import pytest
from django.conf import settings

from apps.newsletter import services
from apps.newsletter.models import AUDIENCE_ALL, Campaign
from apps.newsletter.tests.factories import SubscriberFactory


class RecordingConnection:
    """Stands in for the mail connection so the batching can be observed."""

    def __init__(self):
        self.batches = []

    def send_messages(self, messages):
        self.batches.append(list(messages))
        return len(messages)


def _content_for_every_language():
    return {
        code: {"subject": f"Subject {code}", "body": f"Body {code}"}
        for code, _label in settings.LANGUAGES
    }


@pytest.mark.django_db
def test_each_subscriber_is_written_in_their_own_language(mailoutbox):
    for code, _label in settings.LANGUAGES:
        SubscriberFactory(email=f"{code}@example.com", language=code)

    services.send_campaign(_content_for_every_language())

    assert len(mailoutbox) == len(settings.LANGUAGES)
    by_address = {message.to[0]: message for message in mailoutbox}
    for code, _label in settings.LANGUAGES:
        message = by_address[f"{code}@example.com"]
        assert message.subject == f"Subject {code}"
        assert message.body.startswith(f"Body {code}")


@pytest.mark.django_db
def test_a_language_nobody_composed_falls_back_rather_than_being_skipped(mailoutbox):
    subscriber = SubscriberFactory(language="zz")
    content = {settings.LANGUAGE_CODE: {"subject": "Only one", "body": "Body"}}

    campaign = services.send_campaign(content)

    assert campaign.recipient_count == 1
    assert mailoutbox[0].to == [subscriber.email]
    assert mailoutbox[0].subject == "Only one"


@pytest.mark.django_db
def test_every_message_carries_a_working_unsubscribe_link(mailoutbox):
    subscriber = SubscriberFactory()

    services.send_campaign({settings.LANGUAGE_CODE: {"subject": "S", "body": "B"}})

    assert str(subscriber.token) in mailoutbox[0].body


@pytest.mark.django_db
def test_messages_advertise_one_click_unsubscribe():
    subscriber = SubscriberFactory()

    message = services._build_message("Subject", "Body", subscriber)

    assert message.extra_headers["List-Unsubscribe"] == f"<{subscriber.unsubscribe_url}>"
    assert message.extra_headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"


@pytest.mark.django_db
def test_a_campaign_is_one_batch_over_one_connection_with_one_recipient_each(monkeypatch):
    SubscriberFactory.create_batch(3)
    connection = RecordingConnection()
    monkeypatch.setattr(services.mail, "get_connection", lambda *args, **kwargs: connection)

    campaign = services.send_campaign({settings.LANGUAGE_CODE: {"subject": "S", "body": "B"}})

    assert len(connection.batches) == 1
    assert len(connection.batches[0]) == 3
    assert campaign.recipient_count == 3
    # One message per subscriber, never a shared To: recipients must not see
    # each other's addresses.
    assert all(len(message.to) == 1 for message in connection.batches[0])


@pytest.mark.django_db
def test_only_confirmed_and_still_subscribed_addresses_are_mailed(mailoutbox):
    SubscriberFactory(email="yes@example.com")
    SubscriberFactory(email="unconfirmed@example.com", is_confirmed=False)
    SubscriberFactory(email="gone@example.com", is_active=False)

    services.send_campaign({settings.LANGUAGE_CODE: {"subject": "S", "body": "B"}})

    assert [message.to[0] for message in mailoutbox] == ["yes@example.com"]


@pytest.mark.django_db
def test_an_audience_narrows_to_one_language(mailoutbox):
    SubscriberFactory(email="target@example.com", language=settings.LANGUAGE_CODE)
    SubscriberFactory(email="other@example.com", language="zz")

    services.send_campaign(
        {settings.LANGUAGE_CODE: {"subject": "S", "body": "B"}},
        audience=settings.LANGUAGE_CODE,
    )

    assert [message.to[0] for message in mailoutbox] == ["target@example.com"]


@pytest.mark.django_db
def test_a_campaign_with_no_copy_at_all_is_refused():
    """The reference implementation raised StopIteration here instead."""
    with pytest.raises(ValueError, match="at least one language"):
        services.send_campaign({})


@pytest.mark.django_db
def test_the_send_is_logged(mailoutbox):
    SubscriberFactory.create_batch(2)

    services.send_campaign(
        {settings.LANGUAGE_CODE: {"subject": "Hello", "body": "Body"}},
        audience=AUDIENCE_ALL,
    )

    campaign = Campaign.objects.get()
    assert campaign.recipient_count == 2
    assert campaign.subject == "Hello"
    assert campaign.audience == AUDIENCE_ALL


@pytest.mark.django_db
def test_recipient_counts_cover_every_audience_option():
    SubscriberFactory(language=settings.LANGUAGE_CODE)
    SubscriberFactory(language=settings.LANGUAGE_CODE, is_active=False)

    counts = services.recipient_counts()

    assert counts[AUDIENCE_ALL] == 1
    assert counts[settings.LANGUAGE_CODE] == 1
    for code, _label in settings.LANGUAGES:
        assert code in counts


@pytest.mark.django_db
def test_body_placeholders_are_rendered_without_html_escaping(mailoutbox):
    SubscriberFactory(email="reader@example.com")

    services.send_campaign(
        {
            settings.LANGUAGE_CODE: {
                "subject": "{% raw %}Hello {{ email }}{% endraw %}",
                "body": "{% raw %}Smith & Sons wrote to {{ email }}{% endraw %}",
            }
        }
    )

    assert mailoutbox[0].subject == "Hello reader@example.com"
    assert "Smith & Sons wrote to reader@example.com" in mailoutbox[0].body


@pytest.mark.django_db
def test_invalid_campaign_syntax_is_caught_before_a_send():
    assert services.check_template_source("{% raw %}{% if x %}oops{% endraw %}") is not None
    assert services.check_template_source("{% raw %}{{ fine }}{% endraw %}") is None
