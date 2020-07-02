import pytest

from {{ cookiecutter.project_name }}.users.models import User
from {{ cookiecutter.project_name }}.users.tests.factories import UserFactory


@pytest.fixture(autouse=True)
def media_storage(settings, tmpdir):
    settings.MEDIA_ROOT = tmpdir.strpath


@pytest.fixture
def user() -> User:
    return UserFactory()
