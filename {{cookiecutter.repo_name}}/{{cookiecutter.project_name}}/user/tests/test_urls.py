import pytest
from django.urls import resolve, reverse

from user.models import User

pytestmark = pytest.mark.django_db


def test_detail(user: User):
    assert (
        reverse("user:detail", kwargs={"username": user.username})
        == f"/en/user/{user.username}/"
    )
    assert resolve(f"/en/user/{user.username}/").view_name == "user:detail"


def test_update():
    assert reverse("user:update") == "/en/user/update/"
    assert resolve("/en/user/update/").view_name == "user:update"


def test_redirect():
    assert reverse("user:redirect") == "/en/user/redirect/"
    assert resolve("/en/user/redirect/").view_name == "user:redirect"
