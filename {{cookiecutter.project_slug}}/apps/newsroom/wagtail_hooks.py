"""Admin surface for the newsroom: one "Newsroom" menu with articles and categories.

A SnippetViewSet - the successor to the retired wagtail-modeladmin package -
because NewsArticle carries the draft, revision and preview mixins, and the
snippet views are what turn those into Save draft / Publish / Preview / History.
"""

from django.utils.translation import gettext_lazy as _
from wagtail.admin.ui.tables import LiveStatusTagColumn
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from apps.newsroom.models import NewsArticle, NewsCategory


class NewsArticleViewSet(SnippetViewSet):
    model = NewsArticle
    icon = "doc-full"
    menu_label = _("Articles")
    list_display = ["title", "category", "date", LiveStatusTagColumn()]
    list_filter = ["category", "live", "is_featured"]
    search_fields = ["title", "introduction"]
    ordering = ["-date"]


class NewsCategoryViewSet(SnippetViewSet):
    model = NewsCategory
    icon = "tag"
    menu_label = _("Categories")
    list_display = ["name", "slug", "sort_order"]
    ordering = ["sort_order", "name"]


class NewsroomViewSetGroup(SnippetViewSetGroup):
    items = (NewsArticleViewSet, NewsCategoryViewSet)
    menu_icon = "doc-full-inverse"
    menu_label = _("Newsroom")
    menu_name = "newsroom"
    menu_order = 290


register_snippet(NewsroomViewSetGroup)
