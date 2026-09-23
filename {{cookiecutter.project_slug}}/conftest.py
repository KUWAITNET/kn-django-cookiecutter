"""Project-wide pytest fixtures."""

import io

import pytest


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """Create the test database, then seed it once for the whole session.

    Requesting ``django_db_setup`` while overriding it is the pytest-django idiom
    for "do the standard setup, then more": by the time this body runs, migrations
    have been applied. ``django_db_blocker.unblock()`` is required because a
    session fixture sits outside any ``django_db``-marked test, where database
    access is blocked.

    Seeding once - rather than per test - keeps the suite fast while still
    exercising the real{% if cookiecutter.stack == "wagtail" %} page tree,{% endif %} groups and settings. Tests then run inside the
    usual per-test transaction, so nothing they do survives into the next one.
    """
    from django.core.management import call_command

    with django_db_blocker.unblock():
{%- if cookiecutter.stack == "wagtail" and cookiecutter.languages == "en_ar" %}
        # Copies each row's base column into the default-language column wherever
        # the latter is NULL - including the rows the migrations created, which
        # the seed would otherwise trip over.
        call_command("update_translation_fields", verbosity=0)
{%- endif %}
        call_command("seed_content", verbosity=0)


@pytest.fixture
def client():
    """A fresh, unauthenticated test client."""
    from django.test import Client

    return Client()


@pytest.fixture
def admin_user(django_user_model, db):
    """A superuser with a known password, so login flows can be exercised."""
    return django_user_model.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="admin-password-for-tests",  # noqa: S106
    )


@pytest.fixture
def staff_user(django_user_model, db):
    """A staff account with no permissions - the starting point for access tests."""
    return django_user_model.objects.create_user(
        username="staff",
        email="staff@example.com",
        password="staff-password-for-tests",  # noqa: S106
        is_staff=True,
    )


@pytest.fixture
def png_bytes():
    """A real, minimal PNG. Uploads are validated by content, so fakes fail."""
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (12, 12), color=(20, 80, 160)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def upload_file():
    """Build a ``SimpleUploadedFile`` from explicit bytes and an explicit name.

    Name and content are separate arguments on purpose: the point of most upload
    tests is that the two disagree.
    """
    from django.core.files.uploadedfile import SimpleUploadedFile

    def _build(name, content, content_type="application/octet-stream"):
        return SimpleUploadedFile(name, content, content_type=content_type)

    return _build

{% if cookiecutter.languages == "en_ar" %}
@pytest.fixture(autouse=True)
def _restore_active_language():
    """Undo the language a request left active on this thread.

    LocaleMiddleware activates the request's language and nothing resets it, so a
    single test that fetches an Arabic URL leaves every later test in the process
    running in Arabic - which then fails on English labels it never touched. The
    symptom appears in an unrelated test file, which is why this belongs here and
    not in a private copy per app.
    """
    from django.utils import translation

    with translation.override(translation.get_language()):
        yield
{% endif %}