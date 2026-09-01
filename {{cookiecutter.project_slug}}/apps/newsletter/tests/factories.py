import factory
from django.conf import settings

from apps.newsletter.models import Subscriber
{% if cookiecutter.multisite == "multi" %}

def _default_site():
    """The site a test request resolves to, so a factory subscriber matches one."""
    from wagtail.models import Site

    return Site.objects.filter(is_default_site=True).first()
{% endif %}

class SubscriberFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Subscriber

    email = factory.Sequence(lambda n: f"subscriber{n}@example.com")
{%- if cookiecutter.multisite == "multi" %}
    site = factory.LazyFunction(_default_site)
{%- endif %}
    language = factory.LazyFunction(lambda: settings.LANGUAGE_CODE)
    is_confirmed = True
    is_active = True
