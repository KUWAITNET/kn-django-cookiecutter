import pytest

from user.models import User

pytestmark = pytest.mark.django_db


def test_user_get_absolute_url(user: User):
    assert user.get_absolute_url() == f"/en/user/{user.username}/"
