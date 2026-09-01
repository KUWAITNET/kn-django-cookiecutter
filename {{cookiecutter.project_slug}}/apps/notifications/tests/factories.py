import factory
from django.conf import settings

from apps.notifications.models import (
    NotificationRecipient,
    NotificationTemplate,
    NotificationTrigger,
)


class NotificationTemplateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = NotificationTemplate
        django_get_or_create = ("trigger", "language")

    trigger = NotificationTrigger.CONTACT_ENQUIRY_ADMIN
    language = factory.LazyFunction(lambda: settings.LANGUAGE_CODE)
    subject = "Enquiry"
    body = "Body"


class NotificationRecipientFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = NotificationRecipient
        django_get_or_create = ("trigger",)

    trigger = NotificationTrigger.CONTACT_ENQUIRY_ADMIN
    recipients = "staff@example.com"
