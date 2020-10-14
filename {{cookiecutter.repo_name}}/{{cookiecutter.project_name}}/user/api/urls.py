import pytest
from django.urls import resolve, reverse

from user.models import User

pytestmark = pytest.mark.django_db


def test_user_detail(user: User):
    assert (
        reverse("user_api:user-detail", kwargs={"username": user.username})
        == f"/en/api/v1/users/{user.username}/"
    )
    assert resolve(f"/en/api/v1/users/{user.username}/").view_name == "user_api:user-detail"


def test_user_list():
    assert reverse("user_api:user-list") == "/en/api/v1/users/"
    assert resolve("/en/api/v1/users/").view_name == "user_api:user-list"


def test_user_me():
    assert reverse("user_api:user-me") == "/en/api/v1/users/me/"
    assert resolve("/en/api/v1/users/me/").view_name == "user_api:user-me"
