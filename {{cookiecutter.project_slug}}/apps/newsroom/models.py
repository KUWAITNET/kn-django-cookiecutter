"""Newsroom: categories, articles, and the one page that serves them.

Articles are **Django models, never Wagtail pages** - and the same goes for
events, press releases and anything else that is a dated feed. As pages, every
item becomes a node in the page tree that editors scroll past, a slug that moves
when someone drags it, and a place to nest content nobody designed. As a model
it is edited in its own admin listing (filterable, searchable), and keeps
Wagtail's drafts, revisions, preview and scheduled publishing through the
snippet mixins.

The one page is ``NewsIndexPage``: it sits in the tree (so it is in the menus,
carries the newsroom's copy and SEO fields, and owns its address) and serves the
listing and every article through ``RoutablePageMixin``.
"""

from django.contrib.contenttypes.fields import GenericRelation
from django.core.paginator import Paginator
from django.db import models
from django.http import Http404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel, MultiFieldPanel, PublishingPanel
from wagtail.contrib.routable_page.models import RoutablePageMixin, path
from wagtail.fields import StreamField
from wagtail.models import DraftStateMixin, PreviewableMixin, RevisionMixin, Site
from wagtail.search import index
from wagtail.search.queryset import SearchableQuerySetMixin

from apps.core.blocks import CONTENT_BLOCKS, CONTENT_BLOCKS_COUNTS
from apps.core.models import BasePage


class NewsCategory(models.Model):
    """A kind of article - news, press release, perspective. Drives the filter."""

    name = models.CharField(_("name"), max_length=80)
    slug = models.SlugField(
        _("slug"),
        max_length=80,
        unique=True,
        help_text=_("Used in the newsroom filter URL, e.g. ?category=press-releases."),
    )
    sort_order = models.PositiveSmallIntegerField(_("display order"), default=0)

    panels = [FieldPanel("name"), FieldPanel("slug"), FieldPanel("sort_order")]

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = _("news category")
        verbose_name_plural = _("news categories")

    def __str__(self):
        return self.name


class NewsArticleQuerySet(SearchableQuerySetMixin, models.QuerySet):
    def published(self):
        """Live articles, newest first - what every public listing shows.

        ``live`` is Wagtail's publishing flag (DraftStateMixin), so a draft, an
        unpublished article and one scheduled for later are all excluded here and
        nowhere else.
        """
        return self.filter(live=True).order_by("-date", "-first_published_at")


class NewsArticle(DraftStateMixin, RevisionMixin, PreviewableMixin, index.Indexed, models.Model):
    title = models.CharField(_("title"), max_length=255)
    slug = models.SlugField(
        _("slug"),
        max_length=255,
        unique=True,
        help_text=_("The article's address under the newsroom. Changing it breaks old links."),
    )
    category = models.ForeignKey(
        NewsCategory,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="articles",
        verbose_name=_("category"),
    )
    date = models.DateField(_("date"), default=timezone.localdate, db_index=True)
    introduction = models.TextField(
        _("introduction"),
        blank=True,
        help_text=_("The standfirst. Shown on cards, under the headline and in search results."),
    )
    image = models.ForeignKey(
        "core.CustomImage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("image"),
        help_text=_("Lead image, also used when the article is shared. 1200x630px or larger."),
    )
    is_featured = models.BooleanField(
        _("feature on the newsroom"),
        default=False,
        help_text=_("The newest featured article leads the newsroom listing."),
    )
    body = StreamField(
        CONTENT_BLOCKS,
        block_counts=CONTENT_BLOCKS_COUNTS,
        blank=True,
        collapsed=True,
        verbose_name=_("body"),
    )
    search_description = models.TextField(
        _("search description"),
        blank=True,
        help_text=_("Meta description for search engines. Defaults to the introduction."),
    )

    # Lets Wagtail delete an article's revisions with it, and gives the admin
    # its history view.
    _revisions = GenericRelation("wagtailcore.Revision", related_query_name="newsarticle")

    objects = NewsArticleQuerySet.as_manager()

    panels = [
        FieldPanel("title"),
        FieldPanel("slug"),
        MultiFieldPanel(
            [FieldPanel("category"), FieldPanel("date"), FieldPanel("is_featured")],
            heading=_("Article"),
        ),
        FieldPanel("introduction"),
        FieldPanel("image"),
        FieldPanel("body"),
        FieldPanel("search_description"),
        PublishingPanel(),
    ]

    search_fields = [
        index.SearchField("title", boost=2),
        index.AutocompleteField("title"),
        index.SearchField("introduction"),
        index.SearchField("body"),
        index.FilterField("live"),
        index.FilterField("date"),
    ]

    class Meta:
        ordering = ["-date"]
        verbose_name = _("article")
        verbose_name_plural = _("articles")
        # The listing's WHERE and ORDER BY, so the newsroom stays one index scan
        # however many articles accumulate.
        indexes = [models.Index(fields=["live", "-date"], name="newsroom_live_date_idx")]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return self.get_url()

    def get_url(self, request=None):
        """The article's address under the newsroom page, or "" with no newsroom.

        Resolved through the page, never hard-coded, so moving or renaming the
        newsroom moves every article with it. One query per call: a template that
        lists articles builds links with the routablepageurl tag against a newsroom
        it looked up once, never with this.
        """
        newsroom = NewsIndexPage.for_request(request)
        base = newsroom.get_url(request=request) if newsroom is not None else ""
        if not base:
            return ""
        return base + newsroom.reverse_subpage("article", kwargs={"slug": self.slug})

    @property
    def url(self):
        return self.get_url()

    def get_preview_template(self, request, mode_name):
        return "newsroom/article_detail.html"

    def get_preview_context(self, request, mode_name):
        context = super().get_preview_context(request, mode_name)
        context["article"] = self
        context["page"] = NewsIndexPage.for_request(request)
        context["seo"] = article_seo(request, self)
        return context


class NewsIndexPage(RoutablePageMixin, BasePage):
    """The newsroom: the listing at its own URL, and every article beneath it."""

    parent_page_types = ["home.HomePage"]
{%- if cookiecutter.multisite != "multi" %}
    max_count = 1
{%- endif %}
    # Articles are models, not child pages. Nothing is ever created under here.
    subpage_types = []

    per_page = 12

    class Meta:
        verbose_name = _("Newsroom page")

    @classmethod
    def for_request(cls, request=None):
        """The live newsroom of the request's site, or the first one without a request.

        Every article link goes through here, so an article is always addressed
        under the newsroom of the site it is being shown on.
        """
        pages = cls.objects.live()
        site = Site.find_for_request(request) if request is not None else None
        if site is not None:
            pages = pages.descendant_of(site.root_page, inclusive=True)
        return pages.first()

    @path("", name="list")
    def article_list(self, request):
        articles = NewsArticle.objects.published().select_related("category", "image")
        categories = NewsCategory.objects.filter(articles__live=True).distinct()

        current_category = categories.filter(slug=request.GET.get("category") or "").first()
        if current_category is not None:
            articles = articles.filter(category=current_category)

        # The featured piece leads the unfiltered listing and is left out of the
        # grid on every page, so it is never shown twice and pagination stays
        # stable between page 1 and page 2.
        featured = None
        if current_category is None:
            featured = articles.filter(is_featured=True).first()
            if featured is not None:
                articles = articles.exclude(pk=featured.pk)

        page_obj = Paginator(articles, self.per_page).get_page(request.GET.get("page"))
        if page_obj.number != 1:
            featured = None

        return self.render(
            request,
            context_overrides={
                "articles": page_obj,
                "featured": featured,
                "categories": categories,
                "current_category": current_category,
            },
            template="newsroom/news_index_page.html",
        )

    @path("<slug:slug>/", name="article")
    def article_detail(self, request, slug):
        article = (
            NewsArticle.objects.published()
            .select_related("category", "image")
            .filter(slug=slug)
            .first()
        )
        if article is None:
            raise Http404
        return self.render(
            request,
            context_overrides={"article": article, "seo": article_seo(request, article)},
            template="newsroom/article_detail.html",
        )

    def get_sitemap_urls(self, request=None):
        """The listing, then every published article, for sitemap.xml."""
        urls = super().get_sitemap_urls(request)
        base = self.get_full_url(request=request)
        if not base:
            return urls
        for article in NewsArticle.objects.published():
            urls.append(
                {
                    "location": base
                    + self.reverse_subpage("article", kwargs={"slug": article.slug}),
                    "lastmod": article.last_published_at,
                }
            )
        return urls


def article_seo(request, article):
    """The ``seo`` dict the shared head partial reads, for one article."""
    seo = {
        "base_title": article.title,
        "description": article.search_description or article.introduction,
        "og_type": "article",
    }
    if article.image:
        rendition = article.image.get_rendition("fill-1200x630")
        seo.update(
            {
                "image_url": request.build_absolute_uri(rendition.url),
                "image_width": rendition.width,
                "image_height": rendition.height,
            }
        )
    return seo
