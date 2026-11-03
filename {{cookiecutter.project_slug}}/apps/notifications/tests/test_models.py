import pytest
from django.conf import settings
from django.core.exceptions import ValidationError

from apps.notifications.defaults import DEFAULTS, get_default
from apps.notifications.models import (
    NotificationRecipient,
    NotificationTemplate,
    NotificationTrigger,
    RecipientType,
)
from apps.notifications.tests.factories import NotificationTemplateFactory


def test_every_default_has_copy_in_every_configured_language():
    """The enums and the copy registry drift apart silently otherwise."""
    for trigger, recipient_type in DEFAULTS:
        assert trigger in NotificationTrigger.values
        assert recipient_type in RecipientType.values
        for code, _label in settings.LANGUAGES:
            assert get_default(trigger, recipient_type, code, "subject")
            assert get_default(trigger, recipient_type, code, "body")


def test_every_trigger_has_at_least_one_default_template():
    covered = {trigger for trigger, _recipient_type in DEFAULTS}
    assert covered == set(NotificationTrigger.values)


@pytest.mark.django_db
def test_invalid_body_syntax_is_a_field_error_not_a_send_time_crash():
    template = NotificationTemplateFactory.build(
        subject="Fine",
        body="{% raw %}{% if unclosed %}oops{% endraw %}",
    )
    with pytest.raises(ValidationError) as excinfo:
        template.full_clean()
    assert "body" in excinfo.value.message_dict


@pytest.mark.django_db
def test_invalid_subject_syntax_is_rejected():
    template = NotificationTemplateFactory.build(
        subject="{% raw %}{% no_such_tag %}{% endraw %}",
        body="Fine",
    )
    with pytest.raises(ValidationError) as excinfo:
        template.full_clean()
    assert "subject" in excinfo.value.message_dict


@pytest.mark.django_db
def test_valid_template_syntax_passes_validation():
    template = NotificationTemplateFactory.build(
        subject="{% raw %}Enquiry from {{ name }}{% endraw %}",
        body="{% raw %}{% if name %}<p>Hello {{ name }}</p>{% endif %}{% endraw %}",
    )
    template.full_clean()


@pytest.mark.django_db
def test_reset_field_restores_the_built_in_body_and_leaves_the_subject_alone():
    template = NotificationTemplateFactory(subject="Edited subject", body="<p>Edited</p>")

    template.reset_field("body")

    template.refresh_from_db()
    assert template.body == get_default(
        template.trigger, template.recipient_type, template.language, "body"
    )
    assert template.body != "<p>Edited</p>"
    assert template.subject == "Edited subject"


@pytest.mark.django_db
def test_reset_field_refuses_a_field_that_is_not_resettable():
    template = NotificationTemplateFactory()
    with pytest.raises(ValueError, match="not resettable"):
        template.reset_field("updated_at")


@pytest.mark.django_db
def test_one_row_per_trigger_audience_and_language():
    NotificationTemplateFactory(language=settings.LANGUAGE_CODE)
    duplicate = NotificationTemplate(
        trigger=NotificationTrigger.CONTACT_SUBMISSION,
        recipient_type=RecipientType.ADMIN,
        language=settings.LANGUAGE_CODE,
        subject="Second",
    )
    with pytest.raises(ValidationError):
        duplicate.full_clean()


@pytest.mark.django_db
def test_recipient_list_rejects_a_malformed_address():
    recipient = NotificationRecipient(
        trigger=NotificationTrigger.CONTACT_SUBMISSION,
        recipients="ok@example.com, not-an-address",
    )
    with pytest.raises(ValidationError) as excinfo:
        recipient.full_clean()
    assert "recipients" in excinfo.value.message_dict


@pytest.mark.django_db
def test_recipient_list_is_split_and_trimmed():
    recipient = NotificationRecipient(
        trigger=NotificationTrigger.CONTACT_SUBMISSION,
        recipients=" one@example.com , two@example.com ,, ",
    )
    assert recipient.as_list() == ["one@example.com", "two@example.com"]
