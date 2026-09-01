"""Country / region / city reference data.

django-cities-light's own concrete models are swapped out for local ones so the
country table can carry an editor-toggleable ``is_active`` flag. This is the
documented cities-light "customising models" path: ``CITIES_LIGHT_APP_NAME`` in
settings names this app's *label* (``cities``), and cities-light then looks here
for all four concrete models instead of creating its own.

django-countries is deliberately not used: it ships a frozen, code-only list with
no dial codes, no per-project activation and no place to hang a demonym.

Rows come from GeoNames via ``manage.py cities_light``. Everything except
``is_active`` and ``display_name`` is imported data and must not be hand-edited.
"""

import re

from cities_light.abstract_models import (
    AbstractCity,
    AbstractCountry,
    AbstractRegion,
    AbstractSubRegion,
    BaseManager,
)
from cities_light.receivers import connect_default_signals
from django.conf import settings
from django.db import models
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _

from apps.cities.utils import get_nationality

# GeoNames stores the dial code loosely: comma-joined alternatives ("599,5") and
# calling code plus area code ("1-340"). Only the leading run of digits is a
# country calling code.
_LEADING_DIGITS = re.compile(r"\d+")


class CountryQuerySet(models.QuerySet):
    """The country-selection policy, defined in exactly one place.

    In the project this template is derived from the same filter was copy-pasted
    into five form ``__init__``s and one copy had already lost its exclusion
    clause, so one public form silently offered a different country list from the
    other four. Nothing may re-implement these two methods: a form, a serializer
    or a management command that needs "the countries a visitor may pick" calls
    ``Country.objects.selectable()``.
    """

    def selectable(self):
        """Countries an end user may pick in a public form.

        The exclusion list is a per-client setting rather than a constant: which
        countries a site omits is a commercial or political decision, not a
        framework fact.
        """
        excluded = getattr(settings, "COUNTRY_EXCLUDED_CODES", ())
        return self.filter(is_active=True).exclude(code2__in=excluded)

    def with_phone_code(self):
        """``selectable()`` narrowed to countries that have a dial code.

        GeoNames leaves ``phone`` NULL or empty for territories that share
        another country's calling code, and a blank option in a phone
        country-code select produces an unparseable number.
        """
        return self.selectable().exclude(phone__isnull=True).exclude(phone="")


# BaseManager carries cities-light's ``get_by_natural_key``, which the GeoNames
# importer and dumpdata/loaddata both rely on; replacing the manager outright
# breaks them silently.
CountryManager = BaseManager.from_queryset(CountryQuerySet)


class Country(AbstractCountry):
    """A GeoNames country plus the two columns this project owns."""

    is_active = models.BooleanField(
        _("active"),
        default=True,
        db_index=True,
        help_text=_("Uncheck to hide this country from public form dropdowns."),
    )
    display_name = models.CharField(
        _("display name"),
        max_length=200,
        blank=True,
        help_text=_(
            "Overrides the imported GeoNames name for this language. "
            "Leave blank to use the imported name."
        ),
    )

    objects = CountryManager()

    class Meta(AbstractCountry.Meta):
        verbose_name = _("country")
        verbose_name_plural = _("countries")

    @property
    def phone_code(self) -> str:
        """The E.164 country calling code, e.g. ``+965``. Empty when unknown."""
        match = _LEADING_DIGITS.match((self.phone or "").strip())
        return f"+{match.group()}" if match else ""

    @property
    def localized_name(self) -> str:
        """The country name in the active language.

        The editor override wins; then the GeoNames alternate-name blob populated
        by ``CITIES_LIGHT_TRANSLATION_LANGUAGES`` (empty if the import ran before
        that setting existed); then the imported name.
        """
        if self.display_name:
            return self.display_name
        language = (get_language() or settings.LANGUAGE_CODE).split("-")[0]
        names = (self.translations or {}).get(language)
        return names[0] if names else self.name

    @property
    def nationality(self) -> str:
        """Demonym for this country, e.g. "Kuwaiti" for KW.

        Falls back to the country name for any code the table does not cover, so
        an incomplete table degrades instead of raising.
        """
        return get_nationality(self.code2, fallback=self.localized_name)

    @classmethod
    def nationality_choices(cls):
        """Countries offered in a nationality dropdown.

        Same policy as every other country dropdown, on purpose: a nationality
        list that disagrees with the country list is a bug report waiting to
        happen.
        """
        return cls.objects.selectable()


connect_default_signals(Country)


# Region, SubRegion and City are required by cities-light whenever
# CITIES_LIGHT_APP_NAME is set - it resolves all four models from this app - even
# though a project that only needs a country dropdown never imports rows into
# them. Delete them only if you also stop using cities-light.


class Region(AbstractRegion):
    pass


connect_default_signals(Region)


class SubRegion(AbstractSubRegion):
    pass


connect_default_signals(SubRegion)


class City(AbstractCity):
    pass


connect_default_signals(City)
