"""Where the administration interfaces answer, and where they must not.

The prefix is defence in depth, so the property worth testing is not "it is not
the default" but{% if cookiecutter.stack == "wagtail" %} "the two prefixes are independent": mounting the Django admin at
``<wagtail prefix>/django/`` means one lucky guess reaches both login forms.{% else %} that nothing answers on the path every scanner tries first.{% endif %}
"""

import pytest
from django.conf import settings
{%- if cookiecutter.stack == "wagtail" %}
from django.urls import reverse
{%- endif %}

pytestmark = pytest.mark.django_db

{% if cookiecutter.stack == "wagtail" %}
def test_the_wagtail_admin_answers_on_its_own_prefix(client, admin_user):
    client.force_login(admin_user)

    response = client.get(f"/{settings.WAGTAIL_ADMIN_URL_PREFIX}/")

    assert response.status_code == 200


def test_the_django_admin_is_not_reachable_under_the_wagtail_prefix(client, admin_user):
    client.force_login(admin_user)

    # follow=True because a bilingual install redirects an unprefixed path to the
    # active language before it can 404.
    response = client.get(f"/{settings.WAGTAIL_ADMIN_URL_PREFIX}/django/", follow=True)

    assert response.status_code == 404


def test_login_url_points_at_the_wagtail_login_form():
    """A literal LOGIN_URL outlives a prefix change and 404s every redirect."""
    assert settings.LOGIN_URL == reverse("wagtailadmin_login")

{% endif %}
def test_the_django_admin_answers_on_its_own_prefix(client, admin_user):
    client.force_login(admin_user)

    response = client.get(f"/{settings.DJANGO_ADMIN_URL_PREFIX}/")

    assert response.status_code == 200


@pytest.mark.parametrize("path", ["/admin/", "/admin/django/"])
def test_the_default_admin_paths_are_not_routed(client, admin_user, path):
    client.force_login(admin_user)

    assert client.get(path, follow=True).status_code == 404
