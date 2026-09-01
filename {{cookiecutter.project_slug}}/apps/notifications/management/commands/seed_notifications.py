"""Provision the notification rows an editor then owns.

Idempotent and non-destructive by construction: ``get_or_create`` only, so
running it again on an environment that has content never overwrites copy an
editor has changed. Safe as a deploy step, and safe to call from a broader
seeder.
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.notifications.defaults import get_default
from apps.notifications.models import (
    NotificationRecipient,
    NotificationTemplate,
    NotificationTrigger,
)


class Command(BaseCommand):
    help = "Create the notification template and recipient rows that do not exist yet."

    def handle(self, *args, **options):
        created_templates = 0
        created_recipients = 0

        for trigger in NotificationTrigger.values:
            for code, _label in settings.LANGUAGES:
                _row, created = NotificationTemplate.objects.get_or_create(
                    trigger=trigger,
                    language=code,
                    defaults={
                        "subject": get_default(trigger, code, "subject"),
                        "body": get_default(trigger, code, "body"),
                    },
                )
                created_templates += int(created)

            _recipient, created = NotificationRecipient.objects.get_or_create(
                trigger=trigger,
                defaults={"recipients": settings.DEFAULT_ADMIN_EMAIL or ""},
            )
            created_recipients += int(created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Notifications seeded: {created_templates} template(s), "
                f"{created_recipients} recipient list(s) created."
            )
        )
