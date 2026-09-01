"""Server-side upload validation.

Six controls, applied to every upload field the public can reach. They exist
together because each one alone is trivially bypassed:

1. a per-field size limit (default ``settings.UPLOAD_MAX_SIZE_MB``);
2. a per-field extension **allowlist** - never a denylist, because a denylist is
   a guess about what is dangerous and the guess is always incomplete;
3. content sniffing with libmagic: the real bytes must match the extension. The
   browser-supplied ``content_type`` and the filename are attacker-controlled and
   prove nothing;
4. images are bounded by ``settings.UPLOAD_IMAGE_MAX_PIXELS`` (decompression
   bombs) and re-encoded server-side, which drops EXIF and any payload smuggled
   into a metadata segment. SVG is never an accepted image: it is executable
   markup that runs in the site's own origin when a browser navigates to it;
5. the stored filename is generated (UUID + the validated extension), so nothing
   an attacker chose ever reaches the filesystem and stored files cannot be
   enumerated by guessing a person's name;
6. anything holding personal data is written to ``PRIVATE_MEDIA_ROOT``
   (``private=True`` below) and served only through the permission-checked view.

The reference project this template is derived from had none of these: every
public ``FileField`` was declared bare, and the only "restriction" was an HTML
``accept=`` attribute, which is a file-picker filter and not validation at all.
"""

import uuid
from pathlib import PurePosixPath

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import models
from django.utils.deconstruct import deconstructible
from django.utils.translation import gettext_lazy as _

#: Raster images we accept on public fields. SVG is absent by design (see above).
IMAGE_EXTENSIONS = ("jpg", "jpeg", "png", "gif", "webp", "avif")

#: Office/PDF documents. No archives and no executables: "zip" carries anything.
DOCUMENT_EXTENSIONS = (
    "pdf",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "ppt",
    "pptx",
    "odt",
    "rtf",
    "txt",
    "csv",
)

#: A CV or certificate attachment - the narrowest set that is still usable.
ATTACHMENT_EXTENSIONS = ("pdf", "doc", "docx", "jpg", "jpeg", "png")

#: Extension -> the MIME types libmagic may legitimately report for it.
#:
#: OOXML files (docx/xlsx/pptx) are ZIP containers: older libmagic builds report
#: ``application/zip`` for them, newer ones the specific type, so both are listed.
#: CSV and RTF are plain text to libmagic more often than not.
EXTENSION_CONTENT_TYPES = {
    "avif": {"image/avif"},
    "csv": {"text/csv", "text/plain", "application/csv"},
    "doc": {"application/msword", "application/x-ole-storage", "application/vnd.ms-office"},
    "docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
    },
    "gif": {"image/gif"},
    "jpeg": {"image/jpeg"},
    "jpg": {"image/jpeg"},
    "odt": {"application/vnd.oasis.opendocument.text", "application/zip"},
    "pdf": {"application/pdf"},
    "png": {"image/png"},
    "ppt": {
        "application/vnd.ms-powerpoint",
        "application/x-ole-storage",
        "application/vnd.ms-office",
    },
    "pptx": {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/zip",
    },
    "rtf": {"application/rtf", "text/rtf", "text/plain"},
    "txt": {"text/plain"},
    "webp": {"image/webp"},
    "xls": {"application/vnd.ms-excel", "application/x-ole-storage", "application/vnd.ms-office"},
    "xlsx": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/zip",
    },
}

#: Pillow format name -> extension, for the image check.
PILLOW_FORMAT_EXTENSIONS = {
    "JPEG": "jpg",
    "PNG": "png",
    "GIF": "gif",
    "WEBP": "webp",
    "AVIF": "avif",
}

#: How much of the file libmagic needs. 2 KB covers every signature we care about.
SNIFF_BYTES = 2048

GENERIC_REJECTION = _("This file could not be accepted. Please upload a different file.")


def file_extension(filename) -> str:
    """The lower-cased extension of ``filename``, without the dot."""
    return PurePosixPath(str(filename or "")).suffix.lstrip(".").lower()


def _sniff_content_type(chunk: bytes) -> str:
    """The MIME type libmagic reads out of ``chunk``.

    python-magic is imported here rather than at module scope so that a missing
    libmagic breaks uploads with a clear message instead of breaking the whole
    project at import time. It deliberately fails closed: silently skipping the
    check would turn a missing system package into a missing security control.
    """
    try:
        import magic
    except ImportError as exc:  # python-magic raises ImportError when libmagic is absent
        raise ImproperlyConfigured(
            "Upload content sniffing needs python-magic and the libmagic system "
            "library (Debian/Ubuntu: libmagic1, macOS: brew install libmagic). "
            "Uploads are refused until it is installed."
        ) from exc
    return magic.from_buffer(chunk, mime=True)


def content_sniffing_available() -> bool:
    """Whether libmagic can be reached. Used by the deployment system checks."""
    try:
        _sniff_content_type(b"plain text")
    except ImproperlyConfigured:
        return False
    return True


def _read_head(value) -> bytes:
    """First ``SNIFF_BYTES`` of an uploaded file, leaving the pointer at the start."""
    value.seek(0)
    chunk = value.read(SNIFF_BYTES)
    value.seek(0)
    return chunk


# --- The individual controls -------------------------------------------------


def validate_file_size(value, max_mb: int | None = None) -> None:
    """Reject a file larger than ``max_mb`` (default ``settings.UPLOAD_MAX_SIZE_MB``)."""
    limit_mb = settings.UPLOAD_MAX_SIZE_MB if max_mb is None else max_mb
    limit_bytes = limit_mb * 1024 * 1024
    size = getattr(value, "size", None)
    if size is not None and size > limit_bytes:
        raise ValidationError(
            _("This file is %(size).1f MB. The maximum is %(limit)d MB."),
            code="file_too_large",
            params={"size": size / (1024 * 1024), "limit": limit_mb},
        )


def validate_extension(value, allowed=None) -> None:
    """Reject anything whose extension is not in the allowlist."""
    allowed = tuple(allowed or DOCUMENT_EXTENSIONS)
    extension = file_extension(getattr(value, "name", value))
    if extension not in allowed:
        raise ValidationError(
            _("Only these file types are accepted: %(allowed)s."),
            code="invalid_extension",
            params={"allowed": ", ".join(sorted(allowed))},
        )


def validate_content_type(value, allowed=None) -> None:
    """Reject a file whose real content does not match its extension.

    Renaming ``payload.html`` to ``cv.pdf`` gets past an extension check and past
    the browser's ``accept=`` filter; it does not get past this.
    """
    allowed = tuple(allowed or DOCUMENT_EXTENSIONS)
    extension = file_extension(getattr(value, "name", value))
    if extension not in allowed:
        # validate_extension owns that message; do not sniff an unknown type.
        return
    detected = _sniff_content_type(_read_head(value))
    expected = EXTENSION_CONTENT_TYPES.get(extension)
    if expected is None:
        raise ImproperlyConfigured(
            f"No content-type signature is configured for '.{extension}'. Add one to "
            "apps.core.validators.EXTENSION_CONTENT_TYPES before allowing it."
        )
    if detected not in expected:
        raise ValidationError(
            _("The contents of this file do not match its .%(extension)s extension."),
            code="content_type_mismatch",
            params={"extension": extension},
        )


def validate_image(value, max_pixels: int | None = None) -> None:
    """Reject anything that is not a bounded, decodable raster image.

    Pillow reads the header only, so the pixel count is checked *before* the
    image is decoded - which is the whole point when the file is a decompression
    bomb that expands to gigabytes.
    """
    from PIL import Image, UnidentifiedImageError

    limit = settings.UPLOAD_IMAGE_MAX_PIXELS if max_pixels is None else max_pixels
    extension = file_extension(getattr(value, "name", value))
    if extension in {"svg", "svgz"}:
        # Stated explicitly even though the allowlist already excludes it: an SVG
        # is a script container that executes in this site's origin.
        raise ValidationError(_("SVG files are not accepted."), code="svg_not_accepted")

    value.seek(0)
    try:
        with Image.open(value) as image:
            width, height = image.size
            image_format = image.format
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationError(
            _("This file is not a readable image."), code="invalid_image"
        ) from exc
    finally:
        value.seek(0)

    if width * height > limit:
        raise ValidationError(
            _("This image is too large (%(pixels)s pixels). The maximum is %(limit)s."),
            code="image_too_many_pixels",
            params={"pixels": f"{width * height:,}", "limit": f"{limit:,}"},
        )
    if PILLOW_FORMAT_EXTENSIONS.get(image_format or "") is None:
        raise ValidationError(_("This image format is not accepted."), code="invalid_image_format")


#: extension -> (Pillow format, stored extension, MIME type) used when re-encoding.
#: Anything not listed is normalised to JPEG - including AVIF, whose write support
#: depends on the Pillow build.
REENCODE_FORMATS = {
    "png": ("PNG", "png", "image/png"),
    "gif": ("GIF", "gif", "image/gif"),
    "webp": ("WEBP", "webp", "image/webp"),
}


def reencode_image(value, quality: int = 85):
    """Return ``value`` re-encoded from its decoded pixels.

    Everything that is not pixel data - EXIF (including GPS coordinates), colour
    profiles, comment segments, payloads appended after the image data - is
    dropped, because only the pixels survive the round trip. An animated GIF or
    WebP keeps its first frame only; that is the price of the guarantee.
    """
    import io

    from django.core.files.uploadedfile import InMemoryUploadedFile
    from PIL import Image

    extension = file_extension(getattr(value, "name", ""))
    pil_format, stored_extension, mime_type = REENCODE_FORMATS.get(
        extension, ("JPEG", "jpg", "image/jpeg")
    )

    value.seek(0)
    with Image.open(value) as image:
        image.load()
        if pil_format == "JPEG" and image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        buffer = io.BytesIO()
        image.save(buffer, format=pil_format, quality=quality, optimize=True)

    buffer.seek(0)
    return InMemoryUploadedFile(
        buffer,
        field_name=getattr(value, "field_name", None),
        name=f"{PurePosixPath(str(value.name)).stem}.{stored_extension}",
        content_type=mime_type,
        size=buffer.getbuffer().nbytes,
        charset=None,
    )


# --- The reusable validator --------------------------------------------------


@deconstructible
class SecureFileValidator:
    """Size + extension + content-type (+ image bounds), in one callable.

    Usable on its own (``validators=[SecureFileValidator(extensions=(...))]``) or
    through ``SecureFileField`` / ``SecureImageField`` below, which is the
    preferred form because it also fixes ``upload_to``.
    """

    def __init__(self, extensions=None, max_mb: int | None = None, image: bool = False):
        self.extensions = tuple(extensions or (IMAGE_EXTENSIONS if image else DOCUMENT_EXTENSIONS))
        self.max_mb = max_mb
        self.image = image

    def __call__(self, value):
        # Order matters: size first, so an enormous file is rejected before
        # anything reads it.
        validate_file_size(value, max_mb=self.max_mb)
        validate_extension(value, allowed=self.extensions)
        validate_content_type(value, allowed=self.extensions)
        if self.image:
            validate_image(value)

    def __eq__(self, other):
        return (
            isinstance(other, SecureFileValidator)
            and self.extensions == other.extensions
            and self.max_mb == other.max_mb
            and self.image == other.image
        )

    def __hash__(self):
        return hash((self.extensions, self.max_mb, self.image))


# --- Generated storage names -------------------------------------------------


def generate_upload_filename(instance, filename) -> str:
    """``upload_to`` callable: ``<app_label>/<model>/<uuid4>.<ext>``.

    The name the browser sent is never used on disk. Keep it in a separate column
    if it has to be shown back to the user.
    """
    extension = file_extension(filename)
    stored = f"{uuid.uuid4().hex}.{extension}" if extension else uuid.uuid4().hex
    meta = getattr(instance, "_meta", None)
    prefix = f"{meta.app_label}/{meta.model_name}" if meta is not None else "uploads"
    return f"{prefix}/{stored}"


@deconstructible
class UploadTo:
    """``upload_to`` callable with an explicit prefix, e.g. ``UploadTo("cv")``."""

    def __init__(self, prefix: str):
        self.prefix = prefix.strip("/")

    def __call__(self, instance, filename) -> str:
        extension = file_extension(filename)
        stored = f"{uuid.uuid4().hex}.{extension}" if extension else uuid.uuid4().hex
        return f"{self.prefix}/{stored}"

    def __eq__(self, other):
        return isinstance(other, UploadTo) and self.prefix == other.prefix

    def __hash__(self):
        return hash(self.prefix)


# --- Model fields ------------------------------------------------------------


class SecureFileField(models.FileField):
    """``FileField`` with all six controls wired in.

    ``private=True`` additionally routes the file to ``PRIVATE_MEDIA_ROOT``, which
    is the correct default for anything a visitor uploads about themselves.
    """

    default_extensions = DOCUMENT_EXTENSIONS
    is_image_field = False

    def __init__(self, *args, extensions=None, max_mb=None, private=False, **kwargs):
        self.extensions = tuple(extensions or self.default_extensions)
        self.max_mb = max_mb
        self.private = private

        kwargs.setdefault("upload_to", generate_upload_filename)
        if private and "storage" not in kwargs:
            from apps.core.storage import private_media_storage

            kwargs["storage"] = private_media_storage

        validators = list(kwargs.pop("validators", []))
        validators.append(
            SecureFileValidator(
                extensions=self.extensions, max_mb=self.max_mb, image=self.is_image_field
            )
        )
        kwargs["validators"] = validators
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs["extensions"] = list(self.extensions)
        if self.max_mb is not None:
            kwargs["max_mb"] = self.max_mb
        if self.private:
            kwargs["private"] = True
            # Re-derived from ``private`` on load; keeping it out of the migration
            # keeps the deployment path out of version control.
            kwargs.pop("storage", None)
        # The validator is rebuilt from extensions/max_mb, so it must not also be
        # serialised - otherwise every migration carries a duplicate.
        remaining = [
            v for v in kwargs.get("validators", []) if not isinstance(v, SecureFileValidator)
        ]
        if remaining:
            kwargs["validators"] = remaining
        else:
            kwargs.pop("validators", None)
        return name, path, args, kwargs


class SecureImageField(SecureFileField):
    """``SecureFileField`` for raster images: bounded, re-encoded, never SVG."""

    default_extensions = IMAGE_EXTENSIONS
    is_image_field = True

    def pre_save(self, model_instance, add):
        file = getattr(model_instance, self.attname)
        if file and not file._committed:
            # Re-encode before anything reaches the filesystem: the bytes stored
            # must be ones Pillow produced, never ones the visitor supplied.
            # Already-committed files have been through this on the request that
            # stored them.
            reencoded = reencode_image(file.file)
            file.file = reencoded
            file.name = reencoded.name
        return super().pre_save(model_instance, add)
