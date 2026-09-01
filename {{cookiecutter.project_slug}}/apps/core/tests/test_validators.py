"""Upload validation.

These are the tests that would have caught the reference project's worst gap: it
accepted any file, of any size, with any content, under the visitor's own
filename.
"""

import io

import pytest
from django.core.exceptions import ValidationError

from apps.core.validators import (
    DOCUMENT_EXTENSIONS,
    IMAGE_EXTENSIONS,
    SecureFileValidator,
    file_extension,
    generate_upload_filename,
    reencode_image,
    validate_content_type,
    validate_extension,
    validate_file_size,
    validate_image,
)

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def _png(size=(10, 10)):
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, color=(1, 2, 3)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_oversized_file_is_rejected(upload_file):
    upload = upload_file("report.pdf", b"x" * (2 * 1024 * 1024))
    with pytest.raises(ValidationError) as excinfo:
        validate_file_size(upload, max_mb=1)
    assert excinfo.value.code == "file_too_large"


def test_file_within_the_limit_is_accepted(upload_file):
    validate_file_size(upload_file("report.pdf", b"x" * 1024), max_mb=1)


def test_disallowed_extension_is_rejected(upload_file):
    # A denylist would have to guess every dangerous extension; the allowlist
    # only has to know what the field is for.
    with pytest.raises(ValidationError) as excinfo:
        validate_extension(upload_file("payload.exe", b"MZ"), allowed=DOCUMENT_EXTENSIONS)
    assert excinfo.value.code == "invalid_extension"


def test_svg_is_never_an_accepted_image(upload_file):
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    with pytest.raises(ValidationError):
        validate_extension(upload_file("logo.svg", svg), allowed=IMAGE_EXTENSIONS)
    with pytest.raises(ValidationError) as excinfo:
        validate_image(upload_file("logo.svg", svg))
    assert excinfo.value.code == "svg_not_accepted"


def test_content_not_matching_extension_is_rejected(upload_file):
    """A renamed file passes the extension check and must not pass this one."""
    disguised = upload_file(
        "cv.pdf", b"<html><script>alert(1)</script></html>", content_type="application/pdf"
    )
    with pytest.raises(ValidationError) as excinfo:
        validate_content_type(disguised, allowed=DOCUMENT_EXTENSIONS)
    assert excinfo.value.code == "content_type_mismatch"


def test_real_pdf_passes_content_sniffing(upload_file):
    validate_content_type(upload_file("report.pdf", PDF_BYTES), allowed=DOCUMENT_EXTENSIONS)


def test_image_beyond_the_pixel_bound_is_rejected(upload_file):
    with pytest.raises(ValidationError) as excinfo:
        validate_image(upload_file("photo.png", _png((100, 100))), max_pixels=100)
    assert excinfo.value.code == "image_too_many_pixels"


def test_valid_upload_passes_every_control(upload_file):
    validator = SecureFileValidator(extensions=IMAGE_EXTENSIONS, max_mb=5, image=True)
    validator(upload_file("photo.png", _png(), content_type="image/png"))


def test_valid_document_passes_every_control(upload_file):
    validator = SecureFileValidator(extensions=("pdf",), max_mb=5)
    validator(upload_file("report.pdf", PDF_BYTES, content_type="application/pdf"))


def test_stored_filename_is_generated_not_supplied():
    class FakeMeta:
        app_label = "contact"
        model_name = "enquiry"

    class FakeInstance:
        _meta = FakeMeta()

    stored = generate_upload_filename(FakeInstance(), "../../Fatima Al-Sabah CV.PDF")
    assert stored.startswith("contact/enquiry/")
    assert stored.endswith(".pdf")
    # Nothing the uploader chose survives: no original name, no traversal.
    assert "Fatima" not in stored
    assert ".." not in stored
    assert file_extension(stored) == "pdf"


def test_two_uploads_of_the_same_name_get_different_stored_names():
    class FakeInstance:
        _meta = None

    first = generate_upload_filename(FakeInstance(), "cv.pdf")
    second = generate_upload_filename(FakeInstance(), "cv.pdf")
    assert first != second


def test_reencoding_drops_exif(upload_file):
    from PIL import Image

    buffer = io.BytesIO()
    image = Image.new("RGB", (10, 10), color=(9, 9, 9))
    exif = image.getexif()
    exif[271] = "SecretCameraMaker"
    image.save(buffer, format="JPEG", exif=exif)
    original = buffer.getvalue()
    assert b"SecretCameraMaker" in original

    cleaned = reencode_image(upload_file("photo.jpg", original, content_type="image/jpeg"))
    assert b"SecretCameraMaker" not in cleaned.read()
