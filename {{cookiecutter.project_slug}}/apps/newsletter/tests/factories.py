import factory
from django.conf import settings

from apps.newsletter.models import Subscriber


class SubscriberFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Subscriber

    email = factory.Sequence(lambda n: f"subscriber{n}@example.com")
    language = factory.LazyFunction(lambda: settings.LANGUAGE_CODE)
    is_confirmed = True
    is_active = True
