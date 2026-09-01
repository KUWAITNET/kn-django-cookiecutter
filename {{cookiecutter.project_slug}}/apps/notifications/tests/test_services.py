import pytest
from django.conf import settings

from apps.notifications import services
from apps.notifications.defaults import get_default
from apps.notifications.models import NotificationTrigger, RecipientType
from apps.notifications.tests.factories import (
    NotificationRecipientFactory,
    NotificationTemplateFactory,
)

TRIGGER = NotificationTrigger.CONTACT_SUBMISSION


def _seed_one_row_per_language():
    for code, _label in settings.LANGUAGES:
        NotificationTemplateFactory(
            trigger=TRIGGER,
            language=code,
            subject=f"Subject {code}",
            body="{% raw %}<p>Hello {{ name }}{% endraw %}" + f" [{code}]</p>",
        )


@pytest.mark.django_db
def test_renders_the_row_for_each_configured_language():
    _seed_one_row_per_language()

    for code, _label in settings.LANGUAGES:
        subject, body = services.render_notification_template(
            TRIGGER, RecipientType.ADMIN, {"name": "Sara"}, code
        )
        assert subject == f"Subject {code}"
        assert body == f"<p>Hello Sara [{code}]</p>"


@pytest.mark.django_db
def test_falls_back_to_the_built_in_copy_when_nothing_is_seeded():
    subject, body = services.render_notification_template(
        TRIGGER,
        RecipientType.ADMIN,
        {"name": "Sara", "email": "sara@example.com", "message": "Hi"},
    )

    assert subject
    assert "Sara" in subject or "Sara" in body


@pytest.mark.django_db
def test_visitor_values_are_escaped_into_the_body():
    """Bodies are HTML, so a visitor must not be able to put markup in one."""
    NotificationTemplateFactory(
        subject="Subject",
        body="{% raw %}<p>{{ message }}</p>{% endraw %}",
    )

    _subject, body = services.render_notification_template(
        TRIGGER, RecipientType.ADMIN, {"message": "<script>alert(1)</script>"}
    )

    assert "<script>" not in body
    assert "&lt;script&gt;" in body


@pytest.mark.django_db
def test_the_subject_is_not_html_escaped():
    """A subject is a header, not markup: an ampersand must stay an ampersand."""
    NotificationTemplateFactory(subject="{% raw %}Enquiry from {{ name }}{% endraw %}")

    subject, _body = services.render_notification_template(
        TRIGGER, RecipientType.ADMIN, {"name": "Smith & Sons"}
    )

    assert subject == "Enquiry from Smith & Sons"


@pytest.mark.django_db
def test_subject_cannot_carry_an_injected_header():
    NotificationTemplateFactory(subject="{% raw %}Enquiry from {{ name }}{% endraw %}")

    subject, _body = services.render_notification_template(
        TRIGGER, RecipientType.ADMIN, {"name": "Sara\nBcc: attacker@example.com"}
    )

    assert "\n" not in subject
    assert subject == "Enquiry from Sara Bcc: attacker@example.com"


@pytest.mark.django_db
def test_send_lands_in_the_outbox_for_each_configured_language(mailoutbox):
    _seed_one_row_per_language()

    for code, _label in settings.LANGUAGES:
        mailoutbox.clear()
        sent = services.send_notification(
            TRIGGER, {"name": "Sara"}, recipients=["staff@example.com"], language=code
        )

        assert sent == 1
        assert len(mailoutbox) == 1
        assert mailoutbox[0].subject == f"Subject {code}"
        assert f"Hello Sara [{code}]" in mailoutbox[0].body
        assert mailoutbox[0].to == ["staff@example.com"]


@pytest.mark.django_db
def test_send_uses_the_configured_recipients_for_the_trigger(mailoutbox):
    NotificationRecipientFactory(trigger=TRIGGER, recipients="one@example.com,two@example.com")

    services.send_notification(TRIGGER, {"name": "Sara"})

    # One message per address: recipients never see each other.
    assert len(mailoutbox) == 2
    assert [message.to for message in mailoutbox] == [["one@example.com"], ["two@example.com"]]


@pytest.mark.django_db
def test_send_falls_back_to_the_default_admin_address(settings, mailoutbox):
    settings.DEFAULT_ADMIN_EMAIL = "fallback@example.com"

    services.send_notification(TRIGGER, {"name": "Sara"})

    assert [message.to for message in mailoutbox] == [["fallback@example.com"]]


@pytest.mark.django_db
def test_send_with_no_recipients_at_all_is_a_no_op(settings, mailoutbox):
    settings.DEFAULT_ADMIN_EMAIL = ""

    assert services.send_notification(TRIGGER, {"name": "Sara"}) == 0
    assert mailoutbox == []


@pytest.mark.django_db
def test_context_may_be_a_callable_resolved_inside_the_language_override():
    calls = []

    def build_context():
        calls.append(1)
        return {"name": "Sara"}

    services.send_notification(
        TRIGGER, build_context, recipients=["a@example.com", "b@example.com"]
    )

    # Once per language group, not once per address and not once overall.
    assert len(calls) == 1


@pytest.mark.django_db
def test_a_broken_send_never_reaches_the_caller(monkeypatch, caplog):
    def explode(*args, **kwargs):
        raise OSError("smtp is down")

    monkeypatch.setattr(services, "_send", explode)

    assert services.send_notification(TRIGGER, {}, recipients=["a@example.com"]) == 0
    assert "could not be sent" in caplog.text


@pytest.mark.django_db
def test_an_unseeded_send_still_carries_real_copy(mailoutbox):
    services.send_notification(
        TRIGGER,
        {"name": "Sara", "email": "sara@example.com", "message": "Hi"},
        recipients=["staff@example.com"],
        language=settings.LANGUAGE_CODE,
    )

    assert len(mailoutbox) == 1
    assert mailoutbox[0].body.strip()
    assert mailoutbox[0].subject != TRIGGER
    assert get_default(TRIGGER, RecipientType.ADMIN, settings.LANGUAGE_CODE, "body")
