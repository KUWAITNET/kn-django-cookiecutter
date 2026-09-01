import pytest
from django.conf import settings
from django.core.management import call_command

from apps.notifications.defaults import DEFAULTS
from apps.notifications.models import (
    NotificationRecipient,
    NotificationTemplate,
    NotificationTrigger,
)


@pytest.mark.django_db
def test_seeding_creates_one_row_per_template_and_language():
    call_command("seed_notifications")

    assert NotificationTemplate.objects.count() == len(DEFAULTS) * len(settings.LANGUAGES)
    assert NotificationRecipient.objects.count() == len(NotificationTrigger.values)


@pytest.mark.django_db
def test_recipients_start_at_the_configured_admin_address(settings):
    settings.DEFAULT_ADMIN_EMAIL = "ops@example.com"

    call_command("seed_notifications")

    assert NotificationRecipient.objects.first().as_list() == ["ops@example.com"]


@pytest.mark.django_db
def test_seeding_again_never_overwrites_an_editor(capsys):
    """A seeder that is not safe to re-run cannot be a deploy step."""
    call_command("seed_notifications")
    template = NotificationTemplate.objects.first()
    template.subject = "Reworded by the client"
    template.save(update_fields=["subject"])
    before = NotificationTemplate.objects.count()

    call_command("seed_notifications")

    template.refresh_from_db()
    assert template.subject == "Reworded by the client"
    assert NotificationTemplate.objects.count() == before
