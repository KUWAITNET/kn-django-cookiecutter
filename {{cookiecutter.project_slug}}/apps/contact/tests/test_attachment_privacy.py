"""An attachment on a public form is personal data, and must not be public.

In the project this template is derived from, applicant CVs sat under a
world-readable ``MEDIA_ROOT`` with the filenames their owners had given them, so
anyone who guessed a name could read one. These tests are what stops that
shipping again.
"""

import pytest
from django.conf import settings
from django.contrib.auth.models import Permission

from apps.contact.forms import ContactForm


@pytest.fixture
def submission_with_attachment(form_data, upload_file, pdf_bytes):
    form = ContactForm(
        data=form_data,
        files={"attachment": upload_file("private-cv.pdf", pdf_bytes, "application/pdf")},
    )
    assert form.is_valid(), form.errors
    return form.save()


@pytest.mark.django_db
def test_the_attachment_is_written_outside_media_root(submission_with_attachment):
    path = submission_with_attachment.attachment.path

    assert path.startswith(str(settings.PRIVATE_MEDIA_ROOT))
    assert not path.startswith(str(settings.MEDIA_ROOT))


@pytest.mark.django_db
def test_the_attachment_has_no_public_url(submission_with_attachment):
    # Private storage refuses rather than returning something, so a template that
    # renders the attachment's url attribute fails loudly in development instead
    # of quietly publishing the file in production.
    with pytest.raises(ValueError):
        _ = submission_with_attachment.attachment.url


@pytest.mark.django_db
def test_an_anonymous_visitor_cannot_download_the_attachment(
    client, submission_with_attachment
):
    response = client.get(submission_with_attachment.attachment_download_url)

    assert response.status_code in (302, 403)
    assert response.status_code != 200


@pytest.mark.django_db
def test_a_staff_account_without_the_permission_cannot_download_it(
    client, staff_user, submission_with_attachment
):
    # is_staff is not authorisation. The permission is granted to the group that
    # legitimately reads submissions, and to nobody else.
    client.force_login(staff_user)

    response = client.get(submission_with_attachment.attachment_download_url)

    assert response.status_code in (302, 403)


@pytest.mark.django_db
def test_a_permitted_account_can_download_it(client, staff_user, submission_with_attachment):
    staff_user.user_permissions.add(
        Permission.objects.get(
            codename="access_private_media", content_type__app_label="core"
        )
    )
    client.force_login(staff_user)

    response = client.get(submission_with_attachment.attachment_download_url)

    assert response.status_code == 200
    assert response["Cache-Control"] == "private, no-store"
    assert response["X-Content-Type-Options"] == "nosniff"


@pytest.mark.django_db
def test_the_download_url_is_not_guessable_from_the_uploaded_name(submission_with_attachment):
    assert submission_with_attachment.attachment_original_name == "private-cv.pdf"
    assert "private-cv" not in submission_with_attachment.attachment_download_url
