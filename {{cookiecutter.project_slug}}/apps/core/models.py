"""Core models: shared abstract bases{% if cookiecutter.stack == "wagtail" %}, the project image model{% endif %}, the private-media permission and the site-wide configuration singleton."""

{% if cookiecutter.stack == "wagtail" -%}
from django.conf import settings
{% endif -%}
from django.db import models
from django.utils.translation import gettext_lazy as _
from solo.models import SingletonModel
{%- if cookiecutter.stack == "django" %}

from apps.core.utils import absolute_url
from apps.core.validators import SecureImageField
{%- endif %}
{%- if cookiecutter.stack == "wagtail" %}
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.images.models import AbstractImage, AbstractRendition, Image
{%- if cookiecutter.multisite == "multi" %}
from wagtail.models import Page, PageManager
from wagtail.query import PageQuerySet
{%- else %}
from wagtail.models import Page
{%- endif %}
from wagtail.search import index
{%- endif %}


class TimeStampedModel(models.Model):
    """Abstract base recording when a row was created and last changed.

    Cheap, and the first thing anyone asks for when investigating a support
    ticket about a record.
    """

    created_at = models.DateTimeField(_("created at"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        abstract = True


class PrivateMediaAccess(models.Model):
    """Owns the permission that guards downloads from ``PRIVATE_MEDIA_ROOT``.

    It has no rows and is never instantiated: Django needs a model to hang a
    custom permission off, and the permission is what
    ``apps.core.views.serve_private_file`` checks. Grant
    ``core.access_private_media`` to the group that legitimately reads
    submissions - not to everyone with ``is_staff``.
    """

    class Meta:
        default_permissions = ()
        permissions = [("access_private_media", _("Can download private media"))]
        verbose_name = _("private media access")
        verbose_name_plural = _("private media access")

    def __str__(self):
        return str(self._meta.verbose_name)
{%- if cookiecutter.stack == "wagtail" %}


class CustomImage(AbstractImage):
    """The project's image model.

    Declared before the first migration because swapping Wagtail's image model
    afterwards is a data migration nobody enjoys. ``caption`` is translatable, so
    editors can localise the text rendered next to an image.
    """

    caption = models.CharField(_("caption"), max_length=255, blank=True)

    admin_form_fields = (*Image.admin_form_fields, "caption")


class CustomRendition(AbstractRendition):
    image = models.ForeignKey(
        CustomImage,
        on_delete=models.CASCADE,
        related_name="renditions",
    )

    class Meta:
        unique_together = (("image", "filter_spec", "focal_point_key"),)
{%- if cookiecutter.multisite == "multi" %}


class SiteScopedModel(models.Model):
    """Abstract base for submission models in a multi-site install.

    ``site`` records which site a submission came in through. It is set from
    ``Site.find_for_request(request)`` at save time and is never editable, so it
    stays out of every ``ModelForm.Meta.fields``.
    """

    site = models.ForeignKey(
        "wagtailcore.Site",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("site"),
    )

    class Meta:
        abstract = True


class SiteFilterableQuerySet(models.QuerySet):
    def for_site(self, site):
        """Rows explicitly checked for ``site``.

        Strict by design: a row with no site checked is visible nowhere, so a
        half-configured snippet fails loudly rather than leaking onto the wrong
        site. ``None`` (block preview, a management command) returns everything.
        """
        if site is None:
            return self
        return self.filter(sites=site).distinct()


class SiteFilterableModel(models.Model):
    """Abstract base for content an editor can scope to specific sites."""

    sites = models.ManyToManyField(
        "wagtailcore.Site",
        blank=True,
        related_name="+",
        verbose_name=_("sites"),
        help_text=_("Which site(s) this appears on. Leave blank to hide it everywhere."),
    )

    objects = SiteFilterableQuerySet.as_manager()

    class Meta:
        abstract = True

    @property
    def sites_display(self):
        names = [str(site) for site in self.sites.all()]
        return ", ".join(names) if names else str(_("Hidden (no site checked)"))


class SiteScopedPageQuerySet(PageQuerySet):
    """PageQuerySet that can restrict results to one site's tree.

    Pages carry no ``site`` column: membership comes from tree position, so
    "latest N" queries in a block's ``get_context`` otherwise pull matching pages
    from every site's tree at once.
    """

    def for_site(self, site):
        if site is None:
            return self
        return self.descendant_of(site.root_page)


#: Must live on an abstract *concrete-model* ancestor, not a plain mixin: Django
#: only inherits managers from abstract model bases. Wagtail's own
#: ``AbstractPage.objects`` uses the same trick for the same reason.
SiteScopedPageManager = PageManager.from_queryset(SiteScopedPageQuerySet)
{%- endif %}


class BasePage(Page):
    """Abstract base for every content page.

    Provides the shared banner (background image, subtitle), the lead paragraph
    and the social-sharing image, so SEO metadata is a property of every page
    rather than something each page type reinvents.
    """
{%- if cookiecutter.multisite == "multi" %}

    # Site-aware for free on every concrete subclass: NewsPage.objects.for_site(site).
    objects = SiteScopedPageManager()
{%- endif %}

    hero_image = models.ForeignKey(
        "core.CustomImage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("hero image"),
        help_text=_("Background image for the page banner. Recommended size: 1920x520px."),
    )
    hero_subtitle = models.CharField(_("hero subtitle"), max_length=255, blank=True)
    introduction = models.TextField(
        _("introduction"),
        blank=True,
        help_text=_("Short lead paragraph shown under the page title."),
    )
    show_hero = models.BooleanField(
        _("show banner"),
        default=True,
        help_text=_("Uncheck to hide the standard page banner (e.g. on form pages)."),
    )
    social_image = models.ForeignKey(
        "core.CustomImage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("social sharing image"),
        help_text=_(
            "Used as the Open Graph image when this page is shared. "
            "Recommended size: 1200x630px. Falls back to the hero image."
        ),
    )

    class Meta:
        abstract = True

    search_fields = Page.search_fields + [
        index.SearchField("introduction"),
{%- if cookiecutter.languages == "en_ar" %}
        # Translated content lives in the per-language columns. Without these an
        # Arabic query never matches Arabic content - a real defect in the
        # project this template is derived from.
        index.SearchField("introduction_en"),
        index.SearchField("introduction_ar"),
{%- endif %}
    ]

    hero_panels = [
        MultiFieldPanel(
            [
                FieldPanel("show_hero"),
                FieldPanel("hero_image"),
                FieldPanel("hero_subtitle"),
                FieldPanel("introduction"),
            ],
            heading=_("Banner"),
        ),
    ]

    content_panels = Page.content_panels + hero_panels

    promote_panels = Page.promote_panels + [
        MultiFieldPanel([FieldPanel("social_image")], heading=_("Sharing")),
    ]

    @property
    def social_sharing_image(self):
        """The image to use for ``og:image``, with a sensible fallback."""
        return self.social_image or self.hero_image


class OperationalSettings(SingletonModel):
    """Global operational configuration, edited in the Django admin.

    There are two homes for a setting on this stack, and the boundary between
    them is the whole point of this model:

    * **a content editor changes it** - branding, contact details, social
      profiles, footer copy, menus - so it is a Wagtail site setting in
      ``apps/navigation``, where editors already look for it, and it is per
      ``Site`` so a second site can differ;
    * **an administrator or a developer changes it** - integration toggles,
      thresholds, operational addresses - so it lives here. One row for the whole
      installation however many sites it serves, and it never appears in the CMS
      at all.

    On a multi-site project the deciding question is per-Site versus global: an
    outbound kill switch that only applies to one of three sites is not a kill
    switch. Never model the same setting in both places - a value with two homes
    is a value that will eventually disagree with itself.

    django-solo pins the row to primary key 1 in ``save()``, so there is no
    "which row is live?" question and no second copy to drift. Read it with
    ``OperationalSettings.get_solo()``.

    The two fields below are the shipped example of the rule. Both are real; if
    the project has nothing operational to configure yet, replace them rather than
    inventing an editorial field to justify keeping the model.
    """

    outbound_integrations_enabled = models.BooleanField(
        _("outbound integrations enabled"),
        default=True,
        help_text=_(
            "Uncheck to stop the site calling third-party services. Intended for an "
            "incident, when a failing or compromised provider must be cut off in "
            "seconds without a deploy."
        ),
    )
    technical_alert_email = models.EmailField(
        _("technical alert e-mail"),
        blank=True,
        help_text=_(
            "Where failed jobs and integration errors are reported. Falls back to "
            "DEFAULT_ADMIN_EMAIL when empty. This is an operations address, not the "
            "public contact address shown on the site."
        ),
    )

    class Meta:
        verbose_name = _("Operational settings")
        verbose_name_plural = _("Operational settings")

    def __str__(self):
        return str(self._meta.verbose_name)

    @property
    def alert_email(self) -> str:
        """The address technical alerts go to, configured or deployed."""
        return self.technical_alert_email or settings.DEFAULT_ADMIN_EMAIL
{%- else %}


class SocialNetwork(models.TextChoices):
    """Networks the site can link to, in display order."""

    FACEBOOK = "facebook", _("Facebook")
    X_TWITTER = "x_twitter", _("X (Twitter)")
    INSTAGRAM = "instagram", _("Instagram")
    LINKEDIN = "linkedin", _("LinkedIn")
    YOUTUBE = "youtube", _("YouTube")
    TIKTOK = "tiktok", _("TikTok")


class SiteConfiguration(SingletonModel):
    """Site-wide settings an administrator edits, instead of a developer deploying.

    Everything a client would otherwise ask us to change in markup - the site
    name, the logo, the sharing image, contact details, social profiles - is
    editable here, in the Django admin. Without a CMS there is nowhere else for it
    to live, which is why every non-CMS project ends up hand-rolling this model,
    each one slightly differently.

    django-solo pins the row to primary key 1 in ``save()``, so there is no "which
    row is live?" question and no second copy to drift out of step. Read it with
    ``SiteConfiguration.get_solo()``; the caller never needs a ``get_or_create``.

    **Every field is optional and every reader falls back to the corresponding
    Django setting** (see ``apps.core.context_processors``). A blank field means
    "use the deployed default", never "render nothing", so the site works
    correctly before anyone has opened this form and stays working if a field is
    cleared.

    Image fields go through ``SecureImageField``: bounded, re-encoded on upload,
    stored under a generated name, and never an SVG. An administrator account is
    a smaller blast radius than a public form, not a zero one.
    """

    site_name = models.CharField(
        _("site name"),
        max_length=255,
        blank=True,
        help_text=_("Overrides the deployed SITE_NAME. Leave empty to use it unchanged."),
    )
    logo = SecureImageField(
        _("logo"),
        blank=True,
        help_text=_("Shown in the site header."),
    )
    default_share_image = SecureImageField(
        _("default share image"),
        blank=True,
        help_text=_(
            "Used for Open Graph and Twitter cards when a page has no image of its own. "
            "Recommended size: 1200x630px."
        ),
    )

    contact_email = models.EmailField(_("contact e-mail"), blank=True)
    contact_phone = models.CharField(
        _("contact phone"),
        max_length=100,
        blank=True,
        help_text=_("Displayed as entered. One number per line for several numbers."),
    )
    address = models.TextField(_("address"), blank=True)

    facebook = models.URLField(_("Facebook"), blank=True)
    x_twitter = models.URLField(_("X (Twitter)"), blank=True)
    instagram = models.URLField(_("Instagram"), blank=True)
    linkedin = models.URLField(_("LinkedIn"), blank=True)
    youtube = models.URLField(_("YouTube"), blank=True)
    tiktok = models.URLField(_("TikTok"), blank=True)

    class Meta:
        verbose_name = _("Site configuration")
        verbose_name_plural = _("Site configuration")

    def __str__(self):
        return str(self._meta.verbose_name)

    @property
    def social_links(self):
        """Configured profiles as ``{name, label, url}`` dicts.

        Lets a template loop once instead of carrying one ``if`` per network,
        which is how a new network ends up rendered in the header and forgotten in
        the footer.
        """
        return [
            {"name": network, "label": label, "url": getattr(self, network)}
            for network, label in SocialNetwork.choices
            if getattr(self, network)
        ]

    @property
    def share_image_url(self) -> str:
        """Absolute URL of the share image, or "" when none is uploaded.

        Absolute because the only consumers are ``og:image`` and structured data,
        where a root-relative path is ignored by every scraper that reads it.
        """
        if not self.default_share_image:
            return ""
        return absolute_url(self.default_share_image.url)
{%- endif %}
