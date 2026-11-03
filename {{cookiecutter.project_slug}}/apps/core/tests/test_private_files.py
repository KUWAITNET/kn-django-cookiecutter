"""Private files: every field classified, the permission gate, and signed links.

The media storage standard, section 9. The gate's allow and deny paths need a
model with a private field, so they are tested where one exists
(apps/contact/tests/test_attachment_privacy.py); everything that needs no model
is here.
"""

import time
from unittest import mock

import pytest
from django.apps import apps
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.db import models
from django.urls import reverse

from apps.core import checks
from apps.core.private_files import is_private_field, private_file_fields
from apps.core.storage import sign_file_name

#: Every field on the private storage, as "app.model.field". A new private field
#: is added here on purpose, together with its PRIVATE_FILE_PERMISSIONS entry.
{%- if cookiecutter.forms_suite == "yes" %}
EXPECTED_PRIVATE_FIELDS = {
    "contact.contactsubmission.attachment",
}
{%- else %}
EXPECTED_PRIVATE_FIELDS = set()
{%- endif %}

#: Project file fields that are public on purpose: meant for everyone, like
#: product, service and branding images. Anything holding personal data does not
#: belong here - when unsure, it is private.
{%- if cookiecutter.stack == "wagtail" %}
PUBLIC_FILE_FIELDS = {
    # Wagtail images cannot be private: renditions are linked with permanent
    # URLs and the library has no per-image permission. A private photo is a
    # plain ImageField on the private storage instead (standard, section 3.1).
    "core.customimage.file",
    "core.customrendition.file",
}
{%- else %}
PUBLIC_FILE_FIELDS = {
    # The site's own branding, shown on every page and in every share card.
    "core.siteconfiguration.default_share_image",
    "core.siteconfiguration.logo",
}
{%- endif %}


def _label(model, field):
    return f"{model._meta.label_lower}.{field.name}"


# --- Every file field is classified -------------------------------------------


def test_every_private_field_is_listed():
    assert {_label(model, field) for model, field in private_file_fields()} == (
        EXPECTED_PRIVATE_FIELDS
    )


def test_every_project_file_field_is_private_or_deliberately_public():
    # A new field that forgets storage= fails here instead of shipping public. A
    # test that only listed the private fields could not catch it: the forgotten
    # field would simply not be on the list.
    unclassified = {
        _label(model, field)
        for model in apps.get_models()
        if model.__module__.startswith("apps.")
        for field in model._meta.fields
        if isinstance(field, models.FileField) and not is_private_field(field)
    } - PUBLIC_FILE_FIELDS
    assert unclassified == set(), (
        "Put these on storage=private_media_storage, or add them to PUBLIC_FILE_FIELDS "
        "with a reason."
    )


def test_every_model_with_a_private_field_has_a_permission():
    assert checks.check_private_files_have_a_permission(None) == []
{%- if cookiecutter.forms_suite == "yes" %}


def test_a_model_without_a_permission_is_an_error(settings):
    settings.PRIVATE_FILE_PERMISSIONS = {}
    errors = checks.check_private_files_have_a_permission(None)
    assert [error.id for error in errors] == ["core.E008"]
{%- endif %}


# --- The permission gate ------------------------------------------------------


@pytest.mark.django_db
def test_the_gate_sends_anonymous_users_to_log_in(client):
    response = client.get(reverse("private_file", args=["auth.user", "1", "password"]))
    assert response.status_code == 302
    assert "next=" in response["Location"]


@pytest.mark.django_db
def test_the_gate_404s_an_unknown_model(client, staff_user):
    client.force_login(staff_user)
    response = client.get(reverse("private_file", args=["nope.nothing", "1", "file"]))
    assert response.status_code == 404


@pytest.mark.django_db
def test_the_gate_404s_a_field_that_is_not_private(client, staff_user):
    # Otherwise the gate could be pointed at any field and read public-storage
    # paths, or worse, at a column that is not a file at all.
    client.force_login(staff_user)
    response = client.get(
        reverse("private_file", args=["auth.user", str(staff_user.pk), "username"])
    )
    assert response.status_code == 404


# --- Signed links on disk -----------------------------------------------------


@pytest.fixture
def signed_storage(settings, tmp_path):
    """The real disk storage, swapped in: the test settings use a plain one."""
    settings.STORAGES = {
        **settings.STORAGES,
        "private": {
            "BACKEND": "apps.core.storage.SignedFileSystemStorage",
            "OPTIONS": {"location": str(tmp_path)},
        },
    }
    return storages["private"]


def _token(url):
    return url.rstrip("/").rsplit("/", 1)[-1]


def test_the_url_is_a_signed_link(signed_storage):
    url = signed_storage.url("members/civil-id.pdf")
    assert url.startswith("/files/signed/")
    assert "civil-id" not in url


@pytest.mark.django_db
def test_a_fresh_link_opens_without_a_login(client, signed_storage):
    name = signed_storage.save("members/civil-id.pdf", ContentFile(b"%PDF-1.4 confidential"))

    response = client.get(signed_storage.url(name))

    assert response.status_code == 200
    assert b"confidential" in b"".join(response.streaming_content)
    assert response["Content-Disposition"].startswith("attachment")
    assert response["Cache-Control"] == "private, no-store"
    assert response["X-Content-Type-Options"] == "nosniff"


@pytest.mark.django_db
def test_an_image_opens_inline_so_img_src_works(client, signed_storage):
    name = signed_storage.save("members/photo.png", ContentFile(b"\x89PNG\r\n\x1a\n"))
    response = client.get(signed_storage.url(name))
    assert response["Content-Disposition"].startswith("inline")


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["uploads/page.html", "uploads/logo.svg"])
def test_a_document_that_can_carry_script_is_always_a_download(client, signed_storage, name):
    # Rendered inline, it would run on this site's own origin.
    saved = signed_storage.save(name, ContentFile(b"<script>alert(1)</script>"))
    response = client.get(signed_storage.url(saved))
    assert response["Content-Disposition"].startswith("attachment")


@pytest.mark.django_db
def test_a_tampered_link_is_a_404(client, signed_storage):
    name = signed_storage.save("members/civil-id.pdf", ContentFile(b"%PDF-1.4"))
    token = _token(signed_storage.url(name))
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    response = client.get(reverse("private_file_signed", args=[tampered]))
    assert response.status_code == 404


@pytest.mark.django_db
def test_an_expired_link_is_a_404(client, settings, signed_storage):
    name = signed_storage.save("members/civil-id.pdf", ContentFile(b"%PDF-1.4"))
    url = signed_storage.url(name)
    later = time.time() + settings.PRIVATE_URL_EXPIRY_SECONDS + 1
    with mock.patch("django.core.signing.time.time", return_value=later):
        response = client.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_a_signed_traversal_is_still_refused(client, signed_storage):
    response = client.get(reverse("private_file_signed", args=[sign_file_name("../../etc/passwd")]))
    assert response.status_code == 404


@pytest.mark.django_db
def test_nginx_sends_the_bytes_when_the_accel_prefix_is_set(client, settings, signed_storage):
    settings.PRIVATE_FILES_ACCEL_PREFIX = "/protected-private/"
    name = signed_storage.save("members/civil-id.pdf", ContentFile(b"%PDF-1.4 confidential"))

    response = client.get(signed_storage.url(name))

    assert response.status_code == 200
    assert response.content == b""
    assert response["X-Accel-Redirect"] == f"/protected-private/{name}"
    # nginx keeps these from the upstream response; the internal location only
    # adds Cache-Control and nosniff.
    assert response["Content-Type"] == "application/pdf"
    assert response["Content-Disposition"].startswith("attachment")
