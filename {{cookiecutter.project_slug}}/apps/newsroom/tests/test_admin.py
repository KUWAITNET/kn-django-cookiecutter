"""Editors manage articles in the Wagtail admin, with drafts, preview and history."""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

ADMIN = "wagtailsnippets_newsroom_newsarticle"


@pytest.mark.parametrize("view", ["list", "add"])
def test_the_article_admin_views_render(client, admin_user, view):
    client.force_login(admin_user)

    assert client.get(reverse(f"{ADMIN}:{view}")).status_code == 200


@pytest.mark.parametrize("view", ["edit", "history", "preview_on_edit"])
def test_an_article_can_be_edited_previewed_and_audited(
    client, admin_user, newsroom, make_article, view
):
    article = make_article("Editable", "editable")
    client.force_login(admin_user)

    assert client.get(reverse(f"{ADMIN}:{view}", args=[article.pk])).status_code == 200


def test_the_edit_form_offers_publishing(client, admin_user, make_article):
    article = make_article("Publishable", "publishable")
    client.force_login(admin_user)

    content = client.get(reverse(f"{ADMIN}:edit", args=[article.pk])).content.decode()

    assert "action-publish" in content


def test_a_staff_account_without_permission_is_refused(client, staff_user, make_article):
    article = make_article("Guarded", "guarded")
    client.force_login(staff_user)

    response = client.get(reverse(f"{ADMIN}:edit", args=[article.pk]))

    assert response.status_code in (302, 403)


def test_saving_a_draft_leaves_the_live_article_alone(make_article):
    article = make_article("Live headline", "live-headline")
    article.title = "Draft headline"
    for code in ("en", "ar"):
        if hasattr(article, f"title_{code}"):
            setattr(article, f"title_{code}", "Draft headline")
    article.save_revision()

    article.refresh_from_db()

    assert article.title == "Live headline"
    assert article.has_unpublished_changes is True
