"""Core models: shared abstract bases{% if cookiecutter.stack == "wagtail" %}, the project image model{% endif %} and the private-media permission."""

from django.db import models
from django.utils.translation import gettext_lazy as _
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
{%- endif %}
