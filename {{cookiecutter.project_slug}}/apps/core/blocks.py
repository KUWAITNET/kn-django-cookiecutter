"""Semantic StreamField blocks shared by every page type.

Blocks are named after what they *mean* (a card grid, an accordion), not after
how the current theme paints them, so a redesign changes templates rather than
content. Each renders from ``templates/blocks/<name>.html``.

Keep this library small. Every block added here is one more thing an editor has
to choose between, and one more template to maintain in both text directions.
"""

from django.core.exceptions import ValidationError
from django.templatetags.static import static
{%- if cookiecutter.multisite == "multi" %}
from django.utils.functional import cached_property, lazy
{%- else %}
from django.utils.functional import lazy
{%- endif %}
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _
from wagtail import blocks
from wagtail.blocks.struct_block import StructBlockValidationError
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.embeds.blocks import EmbedBlock
from wagtail.images.blocks import ImageChooserBlock
{%- if cookiecutter.multisite == "multi" or cookiecutter.newsroom == "yes" %}
from wagtail.snippets.blocks import SnippetChooserBlock
{%- endif %}
{%- if cookiecutter.multisite == "multi" %}
from wagtail.snippets.widgets import AdminSnippetChooser

from apps.core.site_context import current_editing_site
{%- endif %}

ALIGN_CHOICES = [("start", _("Left")), ("center", _("Centre")), ("end", _("Right"))]

_lazy_static = lazy(static, str)


def default_asset_help_text(label, static_path):
    """Help text for a chooser that falls back to a bundled static asset.

    Lazy on purpose. Calling ``static()`` at import time resolves the URL while
    the module is being imported, which bakes a hashed filename into any
    migration that captures the help text and raises outright under a manifest
    storage before ``collectstatic`` has run.
    """
    return format_lazy(
        "{label} Defaults to the bundled asset at {url} when left empty.",
        label=label,
        url=_lazy_static(static_path),
    )
{%- if cookiecutter.multisite == "multi" %}


def scoped_to_page_site(queryset, context):
    """Restrict an auto-pulled page queryset to the current page's site.

    Sites share one database but keep separate trees, so an unscoped "latest N"
    query in a block's ``get_context`` pulls pages from every tree at once - which
    shows up as duplicate cards. Falls back to the unscoped queryset when there is
    no page in context, e.g. a block preview.
    """
    page = context.get("page")
    site = page.get_site() if page is not None else None
    return queryset.for_site(site)


class SiteFilteredSnippetChooserWidget(AdminSnippetChooser):
    """Chooser modal restricted to snippets checked for the editing page's site."""

    def get_chooser_modal_url(self):
        url = super().get_chooser_modal_url()
        site = current_editing_site.get()
        if site is not None:
            url = f"{url}?sites__id={site.pk}"
        return url


class SiteFilteredSnippetChooserBlock(SnippetChooserBlock):
    """``SnippetChooserBlock`` whose modal is scoped to the editing page's site.

    Use for site-filterable snippets, where picking one that belongs to the other
    site is an easy and invisible editor mistake.
    """

    @cached_property
    def widget(self):
        icon = self.target_model.snippet_viewset.icon
        self.set_meta_options({"icon": icon})
        return SiteFilteredSnippetChooserWidget(self.target_model, icon=self.meta.icon)
{%- endif %}


class ToggleableStructBlock(blocks.StructBlock):
    """Base for every page-level section block.

    The ``enabled`` checkbox lets an editor switch a section off without deleting
    it - so seasonal content, or a section waiting on copy, survives instead of
    being retyped later.

    The rule: anything that can appear directly in a page's StreamField subclasses
    this. Item-level blocks used inside a ``ListBlock`` do not.
    """

    enabled = blocks.BooleanBlock(
        required=False,
        default=True,
        label=_("Enabled"),
        help_text=_("Uncheck to hide this section without deleting it."),
    )

    def render(self, value, context=None):
        if not value.get("enabled", True):
            return ""
        return super().render(value, context)


class PageOrURLBlock(blocks.StructBlock):
    """A destination: a page from the tree, or a raw URL - not both."""

    page = blocks.PageChooserBlock(
        required=False, help_text=_("Takes priority over the URL below.")
    )
    url = blocks.CharBlock(
        required=False,
        help_text=_("External URL, absolute path or #anchor. Used only when no page is chosen."),
    )

    class Meta:
        collapsed = True
        icon = "link"
        label = _("Link")
        form_classname = "struct-block"

    def clean(self, value):
        result = super().clean(value)
        targets = {name: result[name] for name in ("page", "url") if result[name]}
        if len(targets) > 1:
            # Both a per-child error (so each offending field is outlined) and a
            # summary on the struct itself (so the collapsed block shows why).
            error = ValidationError(_("Only one of page or URL may be set."))
            raise StructBlockValidationError(
                block_errors=dict.fromkeys(targets, error),
                non_block_errors=[_("Choose either a page or a URL, not both.")],
            )
        return result


class LinkBlock(blocks.StructBlock):
    """A labelled link to a page, a document or an external URL - exactly one."""

    label = blocks.CharBlock(required=False)
    page = blocks.PageChooserBlock(required=False)
    document = DocumentChooserBlock(required=False)
    url = blocks.CharBlock(required=False, help_text=_("External URL or #anchor."))

    class Meta:
        collapsed = True
        icon = "link"
        form_classname = "struct-block link-block"

    def clean(self, value):
        result = super().clean(value)
        targets = {name: result[name] for name in ("page", "document", "url") if result[name]}
        if len(targets) > 1:
            error = ValidationError(_("Only one of page, document or URL may be set."))
            raise StructBlockValidationError(
                block_errors=dict.fromkeys(targets, error),
                non_block_errors=[_("Choose exactly one of: page, document or URL.")],
            )
        return result


class ButtonBlock(LinkBlock):
    """A ``LinkBlock`` rendered as a button.

    ``download`` is an explicit checkbox rather than something inferred from the
    label text: the reference project matched the English substring "download",
    which was silently false on every Arabic page.
    """

    style = blocks.ChoiceBlock(
        choices=[
            ("primary", _("Primary")),
            ("secondary", _("Secondary")),
            ("outline", _("Outline")),
        ],
        default="primary",
        required=False,
    )
    download = blocks.BooleanBlock(
        required=False, help_text=_("Offer the target as a download rather than a page visit.")
    )

    class Meta:
        collapsed = True
        icon = "link"
        template = "blocks/button.html"


class SectionTitleBlock(ToggleableStructBlock):
    """A heading (and optional standfirst) introducing the section below it."""

    heading = blocks.CharBlock(max_length=255)
    subheading = blocks.CharBlock(max_length=255, required=False)
    alignment = blocks.ChoiceBlock(choices=ALIGN_CHOICES, default="start", required=False)

    class Meta:
        collapsed = True
        icon = "title"
        label = _("Section title")
        template = "blocks/section_title.html"


class RichTextContentBlock(ToggleableStructBlock):
    """Free prose.

    The feature list is deliberately short: everything an editor can produce here
    has to be styled and has to work in both text directions.
    """

    body = blocks.RichTextBlock(
        features=["h2", "h3", "h4", "bold", "italic", "ol", "ul", "link", "document-link", "hr"]
    )

    class Meta:
        collapsed = True
        icon = "doc-full"
        label = _("Rich text")
        template = "blocks/rich_text.html"


class ImageTextBlock(ToggleableStructBlock):
    """An image beside a block of text."""

    image = ImageChooserBlock()
    alt_text = blocks.CharBlock(
        max_length=255,
        required=False,
        help_text=_("Describes the image for screen readers. Leave empty if decorative."),
    )
    heading = blocks.CharBlock(max_length=255, required=False)
    body = blocks.RichTextBlock(features=["bold", "italic", "ol", "ul", "link"], required=False)
    image_position = blocks.ChoiceBlock(
        choices=[("start", _("Image first")), ("end", _("Text first"))],
        default="start",
        required=False,
    )
    button = ButtonBlock(required=False)

    class Meta:
        collapsed = True
        icon = "image"
        label = _("Image and text")
        template = "blocks/image_text.html"


class CardBlock(blocks.StructBlock):
    """One card. Item level, so not toggleable - delete it instead."""

    image = ImageChooserBlock(required=False)
    heading = blocks.CharBlock(max_length=255)
    body = blocks.TextBlock(required=False)
    link = PageOrURLBlock(required=False)

    class Meta:
        icon = "form"
        label = _("Card")


class CardGridBlock(ToggleableStructBlock):
    """A grid of cards."""

    heading = blocks.CharBlock(max_length=255, required=False)
    columns = blocks.ChoiceBlock(
        choices=[("2", "2"), ("3", "3"), ("4", "4")], default="3", required=False
    )
    cards = blocks.ListBlock(CardBlock(), min_num=1, max_num=12)

    class Meta:
        collapsed = True
        icon = "grip"
        label = _("Card grid")
        template = "blocks/card_grid.html"


class AccordionItemBlock(blocks.StructBlock):
    question = blocks.CharBlock(max_length=255)
    answer = blocks.RichTextBlock(features=["bold", "italic", "ol", "ul", "link"])

    class Meta:
        icon = "help"
        label = _("Accordion item")


class AccordionBlock(ToggleableStructBlock):
    """Collapsible question/answer rows, for FAQs and long reference content."""

    heading = blocks.CharBlock(max_length=255, required=False)
    items = blocks.ListBlock(AccordionItemBlock(), min_num=1, max_num=30)

    class Meta:
        collapsed = True
        icon = "list-ul"
        label = _("Accordion")
        template = "blocks/accordion.html"


class CTABannerBlock(ToggleableStructBlock):
    """A full-width band with a heading and one or two buttons."""

    heading = blocks.CharBlock(max_length=255)
    body = blocks.TextBlock(required=False)
    background_image = ImageChooserBlock(required=False)
    buttons = blocks.ListBlock(ButtonBlock(), max_num=2, required=False)

    class Meta:
        collapsed = True
        icon = "bullhorn"
        label = _("Call to action")
        template = "blocks/cta_banner.html"


class GalleryImageBlock(blocks.StructBlock):
    image = ImageChooserBlock()
    caption = blocks.CharBlock(max_length=255, required=False)

    class Meta:
        icon = "image"
        label = _("Gallery image")


class GalleryBlock(ToggleableStructBlock):
    """A set of images shown as a grid or lightbox."""

    heading = blocks.CharBlock(max_length=255, required=False)
    images = blocks.ListBlock(GalleryImageBlock(), min_num=1, max_num=40)

    class Meta:
        collapsed = True
        icon = "image"
        label = _("Gallery")
        template = "blocks/gallery.html"


class EmbedMediaBlock(ToggleableStructBlock):
    """An oEmbed video or media item.

    An embed, not raw iframe HTML: pasted markup is an unescaped stored-HTML path
    into every page that renders it.
    """

    embed = EmbedBlock(help_text=_("Paste a YouTube, Vimeo or other media URL."))
    caption = blocks.CharBlock(max_length=255, required=False)

    class Meta:
        collapsed = True
        icon = "media"
        label = _("Embed")
        template = "blocks/embed.html"


class HeroSlideBlock(blocks.StructBlock):
    """One slide of the home-page hero."""

    image = ImageChooserBlock()
    heading = blocks.CharBlock(max_length=255)
    body = blocks.TextBlock(required=False)
    button = ButtonBlock(required=False)

    class Meta:
        icon = "image"
        label = _("Hero slide")


class HeroCarouselBlock(ToggleableStructBlock):
    """The lead band of the home page.

    The first slide is the page's largest contentful paint, so its image is
    rendered eagerly and preloaded while the rest lazy-load.
    """

    slides = blocks.ListBlock(HeroSlideBlock(), min_num=1, max_num=6)

    class Meta:
        collapsed = True
        icon = "image"
        label = _("Hero carousel")
        template = "blocks/hero_carousel.html"


{% if cookiecutter.newsroom == "yes" -%}
class LatestArticlesBlock(ToggleableStructBlock):
    """The newest newsroom articles, pulled automatically.

    Articles are models in a feature app, and apps/core must stay importable on
    its own, so the models are resolved by name inside get_context rather than
    imported at module scope.
    """

    heading = blocks.CharBlock(max_length=255, required=False)
    count = blocks.IntegerBlock(default=3, min_value=1, max_value=12)
    category = SnippetChooserBlock(
        "newsroom.NewsCategory",
        required=False,
        help_text=_("Leave empty to show every category."),
    )

    class Meta:
        collapsed = True
        icon = "doc-full-inverse"
        label = _("Latest articles")
        template = "blocks/latest_articles.html"

    def get_context(self, value, parent_context=None):
        from django.apps import apps

        context = super().get_context(value, parent_context)
        articles = apps.get_model("newsroom", "NewsArticle").objects.published()
        articles = articles.select_related("category", "image")
        if value["category"]:
            articles = articles.filter(category=value["category"])
        context["articles"] = articles[: value["count"]]
        # Looked up once here so each card builds its link without a query.
        request = (parent_context or {}).get("request")
        context["newsroom"] = apps.get_model("newsroom", "NewsIndexPage").for_request(request)
        return context


{% endif -%}
#: The blocks available on a generic content page.
CONTENT_BLOCKS = [
    ("section_title", SectionTitleBlock()),
    ("rich_text", RichTextContentBlock()),
    ("image_text", ImageTextBlock()),
    ("card_grid", CardGridBlock()),
    ("accordion", AccordionBlock()),
    ("cta_banner", CTABannerBlock()),
    ("gallery", GalleryBlock()),
    ("embed", EmbedMediaBlock()),
{%- if cookiecutter.newsroom == "yes" %}
    ("latest_articles", LatestArticlesBlock()),
{%- endif %}
]

#: Caps, so one page cannot become a performance problem on its own. A page that
#: needs more than this is really several pages.
CONTENT_BLOCKS_COUNTS = {
    "section_title": {"max_num": 12},
    "rich_text": {"max_num": 20},
    "image_text": {"max_num": 12},
    "card_grid": {"max_num": 6},
    "accordion": {"max_num": 4},
    "cta_banner": {"max_num": 2},
    "gallery": {"max_num": 3},
    "embed": {"max_num": 6},
{%- if cookiecutter.newsroom == "yes" %}
    "latest_articles": {"max_num": 2},
{%- endif %}
}

#: The home page: its own lead band, plus everything a content page can do.
#: Built from CONTENT_BLOCKS rather than listing block types again - the
#: reference project kept two hand-maintained lists, so the home page could not
#: use a rich-text or CTA block at all.
HOME_BLOCKS = [
    ("hero_carousel", HeroCarouselBlock()),
    *CONTENT_BLOCKS,
]

HOME_BLOCKS_COUNTS = {
    # One hero band per home page: a second one is never the design.
    "hero_carousel": {"max_num": 1},
    **CONTENT_BLOCKS_COUNTS,
}
