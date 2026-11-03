"""An attachment on a public form is personal data, and must not be public.

In the project this template is derived from, applicant CVs sat under a
world-readable ``MEDIA_ROOT`` with the filenames their owners had given them, so
anyone who guessed a name could read one. These tests are what stops that
shipping again: the attachment is on the private storage, a link to it goes
through the permission gate, and ``migrate_private_files`` moves older uploads
across (the media storage standard, sections 5, 8 and 9).
"""

import pytest
from django.conf import settings
from django.contrib.auth.models import Permission
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.core.management import CommandError, call_command
from django.urls import reverse

from apps.contact.forms import ContactForm
from apps.contact.models import ContactSubmission
from apps.core import views
from apps.core.private_files import file_link, is_private_field

pytestmark = pytest.mark.django_db


@pytest.fixture
def submission_with_attachment(form_data, upload_file, pdf_bytes):
    form = ContactForm(
        data=form_data,
        files={"attachment": upload_file("private-cv.pdf", pdf_bytes, "application/pdf")},
    )
    assert form.is_valid(), form.errors
    return form.save()


def _grant_view(user):
    user.user_permissions.add(
        Permission.objects.get(codename="view_contactsubmission", content_type__app_label="contact")
    )
    return user


# --- Where the file lives -----------------------------------------------------


def test_the_attachment_is_on_the_private_storage():
    assert is_private_field(ContactSubmission._meta.get_field("attachment"))


def test_the_attachment_is_written_outside_media_root(submission_with_attachment):
    path = submission_with_attachment.attachment.path

    assert path.startswith(str(settings.PRIVATE_MEDIA_ROOT))
    assert not path.startswith(str(settings.MEDIA_ROOT))


# --- Links go through the gate ------------------------------------------------


def test_the_link_is_the_permission_gate(submission_with_attachment):
    expected = reverse(
        "private_file",
        args=["contact.contactsubmission", str(submission_with_attachment.pk), "attachment"],
    )
    assert file_link(submission_with_attachment.attachment) == expected
    assert submission_with_attachment.attachment_download_url == expected


def test_the_link_is_not_guessable_from_the_uploaded_name(submission_with_attachment):
    assert submission_with_attachment.attachment_original_name == "private-cv.pdf"
    assert "private-cv" not in submission_with_attachment.attachment_download_url


def test_with_the_gate_switched_off_the_link_is_the_signed_url(
    settings, submission_with_attachment
):
    settings.PRIVATE_FILE_LINKS_ENABLED = False
    attachment = submission_with_attachment.attachment
    assert file_link(attachment) == attachment.url


# --- Who may open it ----------------------------------------------------------


def test_an_anonymous_visitor_is_sent_to_log_in(client, submission_with_attachment):
    response = client.get(submission_with_attachment.attachment_download_url)

    assert response.status_code == 302
    assert "next=" in response["Location"]


def test_a_staff_account_without_the_permission_cannot_open_it(
    client, staff_user, submission_with_attachment
):
    # is_staff is not authorisation. The view permission is granted to the group
    # that legitimately reads submissions, and to nobody else.
    client.force_login(staff_user)

    response = client.get(submission_with_attachment.attachment_download_url)

    assert response.status_code == 403


def test_a_permitted_account_gets_the_file(client, staff_user, submission_with_attachment):
    client.force_login(_grant_view(staff_user))

    response = client.get(submission_with_attachment.attachment_download_url)

    assert response.status_code == 200
    assert response["Content-Disposition"].startswith("attachment")
    assert response["Cache-Control"] == "private, no-store"
    assert response["X-Content-Type-Options"] == "nosniff"


def test_an_owner_rule_lets_people_open_only_their_own_file(
    client, settings, django_user_model, submission_with_attachment
):
    # The model permission is the minimum. Where a non-staff user may open their
    # own file, the map entry is a callable instead - without it, the permission
    # would open everybody's.
    settings.PRIVATE_FILE_PERMISSIONS = {
        "contact.contactsubmission": lambda request, obj: obj.email == request.user.email,
    }
    owner = django_user_model.objects.create_user(
        username="owner", email=submission_with_attachment.email, password="owner-pw-for-tests"
    )
    stranger = django_user_model.objects.create_user(
        username="stranger", email="someone@example.net", password="stranger-pw-for-tests"
    )
    url = submission_with_attachment.attachment_download_url

    client.force_login(owner)
    assert client.get(url).status_code == 200
    client.force_login(stranger)
    assert client.get(url).status_code == 403


def test_a_missing_file_is_a_404(client, staff_user, submission_with_attachment):
    storages["private"].delete(submission_with_attachment.attachment.name)
    client.force_login(_grant_view(staff_user))

    response = client.get(submission_with_attachment.attachment_download_url)

    assert response.status_code == 404


def test_in_a_bucket_the_gate_redirects_to_a_fresh_presigned_url(
    client, monkeypatch, staff_user, submission_with_attachment
):
    class Bucket:
        def exists(self, name):
            return True

        def url(self, name):
            return f"https://private-bucket.s3.amazonaws.com/{name}?X-Amz-Signature=abc"

    monkeypatch.setattr(views, "private_media_storage", Bucket)
    client.force_login(_grant_view(staff_user))

    response = client.get(submission_with_attachment.attachment_download_url)

    assert response.status_code == 302
    assert "X-Amz-Signature=" in response["Location"]
    assert response["Cache-Control"] == "private, no-store"


# --- Moving older uploads across ----------------------------------------------


@pytest.fixture
def legacy_attachment(submission_with_attachment):
    """An attachment uploaded before the field was private: it sits in default."""
    name = submission_with_attachment.attachment.name
    private, public = storages["private"], storages["default"]
    with private.open(name, "rb") as handle:
        public.save(name, ContentFile(handle.read()))
    private.delete(name)
    yield name
    for storage in (private, public):
        storage.delete(name)


def test_a_dry_run_copies_nothing(legacy_attachment, capsys):
    call_command("migrate_private_files", "--dry-run")

    assert not storages["private"].exists(legacy_attachment)
    assert "would copy 1" in capsys.readouterr().out


def test_files_are_copied_under_the_same_name_and_a_rerun_is_harmless(legacy_attachment, capsys):
    call_command("migrate_private_files")
    call_command("migrate_private_files")

    assert storages["private"].exists(legacy_attachment)
    # Copy before delete: the public copy stays until --delete-source.
    assert storages["default"].exists(legacy_attachment)
    assert "already private 1" in capsys.readouterr().out


def test_delete_source_removes_the_public_copy_once_it_is_private(legacy_attachment):
    call_command("migrate_private_files", "--delete-source")

    assert storages["private"].exists(legacy_attachment)
    assert not storages["default"].exists(legacy_attachment)


def test_a_missing_source_file_fails_the_run(legacy_attachment):
    storages["default"].delete(legacy_attachment)

    with pytest.raises(CommandError, match="failed 1"):
        call_command("migrate_private_files")


def test_it_refuses_when_both_storages_are_the_same_place(settings, legacy_attachment):
    settings.STORAGES = {**settings.STORAGES, "private": settings.STORAGES["default"]}

    with pytest.raises(CommandError, match="same place"):
        call_command("migrate_private_files", "--delete-source")
