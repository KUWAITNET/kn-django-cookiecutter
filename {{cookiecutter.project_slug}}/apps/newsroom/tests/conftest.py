"""Newsroom fixtures: articles are built here, the newsroom page by seed_content."""

import datetime

import pytest
from django.conf import settings


def _translated(obj, field, value):
    """Set a field and, on a bilingual project, every per-language column.

    Setting only the base column leaves the other language NULL, and the article
    then renders blank - or fails validation - in that language.
    """
    setattr(obj, field, value)
    for code, _label in settings.LANGUAGES:
        column = f"{field}_{code.replace('-', '_')}"
        if hasattr(obj, column):
            setattr(obj, column, value)


@pytest.fixture
def make_article(db):
    from apps.newsroom.models import NewsArticle

    def _make(title, slug, *, publish=True, category=None, days_ago=0, **fields):
        introduction = fields.pop("introduction", f"About {title}.")
        article = NewsArticle(
            slug=slug,
            category=category,
            date=datetime.date.today() - datetime.timedelta(days=days_ago),
            # DraftStateMixin defaults live=True for rows created in code; the
            # admin's "Save draft" is what sets it False, so a draft says so here.
            live=publish,
            **fields,
        )
        _translated(article, "title", title)
        _translated(article, "introduction", introduction)
        article.save()
        if publish:
            article.save_revision().publish()
            article.refresh_from_db()
        return article

    return _make


@pytest.fixture
def make_category(db):
    from apps.newsroom.models import NewsCategory

    def _make(name, slug):
        category = NewsCategory(slug=slug)
        _translated(category, "name", name)
        category.save()
        return category

    return _make


@pytest.fixture
def newsroom(db):
    from apps.newsroom.models import NewsIndexPage

    page = NewsIndexPage.objects.live().first()
    assert page is not None, "seed_content must create the newsroom page (see conftest.py)"
    return page
