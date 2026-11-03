import factory
from django.conf import settings

from apps.notifications.models import (
    NotificationRecipient,
    NotificationTemplate,
    NotificationTrigger,
    RecipientType,
)


class NotificationTemplateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = NotificationTemplate
        django_get_or_create = ("trigger", "recipient_type", "language")

    trigger = NotificationTrigger.CONTACT_SUBMISSION
    recipient_type = RecipientType.ADMIN
    language = factory.LazyFunction(lambda: settings.LANGUAGE_CODE)
    subject = "Enquiry"
    body = "<p>Body</p>"


class NotificationRecipientFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = NotificationRecipient
        django_get_or_create = ("trigger",)

    trigger = NotificationTrigger.CONTACT_SUBMISSION
    recipients = "staff@example.com"
