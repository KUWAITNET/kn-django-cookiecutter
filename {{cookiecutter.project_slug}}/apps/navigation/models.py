"""Site-wide configuration: branding, contact, social, footer and the menus.

Everything a client would otherwise ask us to change in markup - logos, contact
details, social links, copyright, the navigation tree - is editable here.

All five are ``BaseSiteSetting`` (one row per Wagtail ``Site``) rather than
``BaseGenericSetting``. That costs nothing on a single-site project and is the
only thing that makes a second site work later without a data migration.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.contrib.settings.models import BaseSiteSetting, register_setting
from wagtail.fields import StreamField

from apps.navigation.blocks import MenuStreamBlock

#: Degrees of longitude in a whole world, halved once per zoom level to derive the
#: map embed's bounding box. Zoom 15 lands on "one city block fills the frame".
_WORLD_DEGREES = Decimal("360")


@register_setting(icon="image")
class BrandingSettings(BaseSiteSetting):
    """Logos and the images the site presents to other systems."""

    logo = models.ForeignKey(
        "core.CustomImage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("Header logo"),
        help_text=_("Shown in the site header and in the CMS admin."),
    )
    footer_logo = models.ForeignKey(
        "core.CustomImage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("Footer logo"),
        help_text=_("Optional. Falls back to the header logo when empty."),
    )
    default_share_image = models.ForeignKey(
        "core.CustomImage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("Default share image"),
        help_text=_(
            "Used for Open Graph and Twitter cards by the SEO partial when a page has "
            "no image of its own. Recommended size: 1200x630px."
        ),
    )
    favicon = models.ForeignKey(
        "core.CustomImage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("Favicon"),
        help_text=_("Square image, at least 512x512px. Also used in the CMS admin."),
    )

    panels = [
        FieldPanel("logo"),
        FieldPanel("footer_logo"),
        FieldPanel("favicon"),
        FieldPanel("default_share_image"),
    ]

    class Meta:
        verbose_name = _("Branding")


@register_setting(icon="mail")
class ContactSettings(BaseSiteSetting):
    """Contact details and the location shown on the contact page.

    The location is stored as **coordinates, not as an embed snippet**. A
    settings field holding editor-supplied HTML or an iframe, rendered with
    ``|safe``, is stored cross-site scripting: whoever takes over one editor
    account then owns every page that renders the footer, on every visit. There
    is no way to sanitise that field and still let it do its job, so the field
    does not exist. We take numbers we can validate and build the map ourselves.
    """

    address = models.TextField(blank=True, verbose_name=_("Address"))
    po_box = models.CharField(max_length=100, blank=True, verbose_name=_("P.O. Box"))
    phone = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Phone"),
        help_text=_("Displayed as entered. One number per line for several numbers."),
    )
    fax = models.CharField(max_length=100, blank=True, verbose_name=_("Fax"))
    email = models.EmailField(blank=True, verbose_name=_("E-mail"))
    working_hours = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Working hours"),
        help_text=_("For example: Sunday to Thursday, 8:00 - 16:00."),
    )

    map_label = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Map label"),
        help_text=_("Name shown on the map link, e.g. the office name."),
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name=_("Latitude"),
        validators=[MinValueValidator(Decimal("-90")), MaxValueValidator(Decimal("90"))],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name=_("Longitude"),
        validators=[MinValueValidator(Decimal("-180")), MaxValueValidator(Decimal("180"))],
    )
    map_zoom = models.PositiveSmallIntegerField(
        default=15,
        verbose_name=_("Map zoom"),
        validators=[MinValueValidator(1), MaxValueValidator(19)],
        help_text=_("1 is the whole world, 19 is building level."),
    )
    map_image = models.ForeignKey(
        "core.CustomImage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("Map image"),
        help_text=_(
            "Shown instead of a live map. Keeps the contact page free of third-party "
            "frames and trackers, which is the default."
        ),
    )
    use_live_map = models.BooleanField(
        default=False,
        verbose_name=_("Embed a live map"),
        help_text=_(
            "Off by default. The map provider must first be added to the site's "
            "Content-Security-Policy frame-src, otherwise the browser blocks the frame "
            "and visitors see nothing at all."
        ),
    )

    panels = [
        MultiFieldPanel(
            [
                FieldPanel("address"),
                FieldPanel("po_box"),
                FieldPanel("phone"),
                FieldPanel("fax"),
                FieldPanel("email"),
                FieldPanel("working_hours"),
            ],
            heading=_("Contact details"),
        ),
        MultiFieldPanel(
            [
                FieldPanel("map_label"),
                FieldPanel("latitude"),
                FieldPanel("longitude"),
                FieldPanel("map_zoom"),
                FieldPanel("map_image"),
                FieldPanel("use_live_map"),
            ],
            heading=_("Location"),
        ),
    ]

    class Meta:
        verbose_name = _("Contact details")

    def clean(self):
        super().clean()
        if (self.latitude is None) != (self.longitude is None):
            raise ValidationError(
                {
                    "latitude": _("Enter both latitude and longitude, or neither."),
                    "longitude": _("Enter both latitude and longitude, or neither."),
                }
            )

    @property
    def has_map(self):
        return self.latitude is not None and self.longitude is not None

    @property
    def map_link_url(self):
        """Link to the location on an external map, or an empty string."""
        if not self.has_map:
            return ""
        return (
            f"https://www.openstreetmap.org/?mlat={self.latitude}&mlon={self.longitude}"
            f"#map={self.map_zoom}/{self.latitude}/{self.longitude}"
        )

    @property
    def map_embed_url(self):
        """Embed URL for the live map, built entirely from validated numbers.

        The bounding box is derived from the zoom level rather than stored, so
        there is no editor-supplied string anywhere in this URL.
        """
        if not self.has_map:
            return ""
        span = _WORLD_DEGREES / Decimal(2**self.map_zoom)
        west = self.longitude - span
        east = self.longitude + span
        south = self.latitude - span / 2
        north = self.latitude + span / 2
        # Every component is a Decimal we validated, so the URL needs no escaping
        # and carries no editor-supplied string.
        return (
            "https://www.openstreetmap.org/export/embed.html"
            f"?bbox={west},{south},{east},{north}"
            f"&layer=mapnik&marker={self.latitude},{self.longitude}"
        )


class SocialNetwork(models.TextChoices):
    """Networks the footer can link to, in display order."""

    FACEBOOK = "facebook", _("Facebook")
    X_TWITTER = "x_twitter", _("X (Twitter)")
    INSTAGRAM = "instagram", _("Instagram")
    LINKEDIN = "linkedin", _("LinkedIn")
    YOUTUBE = "youtube", _("YouTube")
    TIKTOK = "tiktok", _("TikTok")


@register_setting(icon="site")
class SocialMediaSettings(BaseSiteSetting):
    """Profile URLs. Only the ones that are filled in are rendered."""

    facebook = models.URLField(blank=True, verbose_name=_("Facebook"))
    x_twitter = models.URLField(blank=True, verbose_name=_("X (Twitter)"))
    instagram = models.URLField(blank=True, verbose_name=_("Instagram"))
    linkedin = models.URLField(blank=True, verbose_name=_("LinkedIn"))
    youtube = models.URLField(blank=True, verbose_name=_("YouTube"))
    tiktok = models.URLField(blank=True, verbose_name=_("TikTok"))

    panels = [FieldPanel(network) for network in SocialNetwork.values]

    class Meta:
        verbose_name = _("Social media")

    @property
    def links(self):
        """Configured profiles as ``(name, label, url)`` triples.

        Lets the footer loop once instead of carrying one ``if`` per network,
        which is how a new network ends up rendered in one template and
        forgotten in the other.
        """
        return [
            {"name": network, "label": label, "url": getattr(self, network)}
            for network, label in SocialNetwork.choices
            if getattr(self, network)
        ]


@register_setting(icon="cog")
class FooterSettings(BaseSiteSetting):
    """Footer copy and the secondary menu shown as footer columns."""

    about_text = models.TextField(
        blank=True,
        verbose_name=_("About text"),
        help_text=_("Short paragraph shown beside the footer logo."),
    )
    footer_menu = StreamField(
        MenuStreamBlock(),
        blank=True,
        verbose_name=_("Footer menu"),
        help_text=_("Each top-level item becomes a footer column; its children are the links."),
    )
{%- if cookiecutter.newsletter == "yes" %}
    newsletter_heading = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Newsletter heading"),
        help_text=_("Heading above the newsletter sign-up form."),
    )
{%- endif %}
    copyright_text = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_("Copyright"),
        help_text=_("Shown after the current year, which the template adds automatically."),
    )

    panels = [
        FieldPanel("about_text"),
        FieldPanel("footer_menu"),
{%- if cookiecutter.newsletter == "yes" %}
        FieldPanel("newsletter_heading"),
{%- endif %}
        FieldPanel("copyright_text"),
    ]

    class Meta:
        verbose_name = _("Footer")


@register_setting(icon="list-ul")
class NavigationSettings(BaseSiteSetting):
    """The header menu.

    Settings-driven rather than derived from the page tree: menu order, grouping
    and labels are an editorial decision that rarely matches the tree, and a
    tree-driven menu forces content to be restructured to fix navigation.
    """

    primary_menu = StreamField(
        MenuStreamBlock(),
        blank=True,
        verbose_name=_("Main menu"),
    )

    panels = [FieldPanel("primary_menu")]

    class Meta:
        verbose_name = _("Main menu")
