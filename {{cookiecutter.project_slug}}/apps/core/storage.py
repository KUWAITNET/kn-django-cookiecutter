"""Two storages, never one: public media, and private files that never have a permanent URL.

Files holding personal data - CVs, ID copies, contracts, anything a visitor
attached to a form, photos of customers or members - go to the ``private``
storage alias. Public media has permanent, cacheable URLs; a predictable name
there is a public document, which in our reference project is exactly how
applicant CVs became enumerable.

A private file reaches a user one of two ways (the media storage standard,
section 5): a link on a page points at the permission gate
(``apps.core.views.private_file``, through the ``file_link`` filter), and an
``<img src>`` or an API response carries ``.url``, which is signed and expires.
{%- if cookiecutter.media_storage == "filesystem" %} On disk that signature is
built here, by ``SignedFileSystemStorage``.{% else %} In the bucket that is a
presigned URL from the object store itself.{% endif %}
"""

from django.conf import settings
{%- if cookiecutter.static_storage == "cloud" %}
from django.contrib.staticfiles.storage import ManifestFilesMixin
{%- endif %}
from django.core import signing
from django.core.files.storage import FileSystemStorage, storages
from django.urls import reverse
from django.utils.deconstruct import deconstructible
from django.utils.functional import cached_property
{%- if cookiecutter.media_storage == "s3" %}
from storages.backends.s3 import S3Storage
{%- elif cookiecutter.media_storage == "gcs" %}
from storages.backends.gcloud import GoogleCloudStorage
{%- elif cookiecutter.media_storage == "azure" %}
from storages.backends.azure_storage import AzureStorage
{%- endif %}

#: Namespaces the signed-file token, so it is worthless to any other
#: ``signing.loads()`` in the project and theirs are worthless here.
SIGNED_FILE_SALT = "apps.core.storage.private-file"


def sign_file_name(name):
    """A token carrying the stored name and the time it was signed."""
    return signing.dumps(name, salt=SIGNED_FILE_SALT)


def unsign_file_name(token):
    """The stored name a token carries, or ``None`` for a forged or expired one."""
    try:
        return signing.loads(
            token, salt=SIGNED_FILE_SALT, max_age=settings.PRIVATE_URL_EXPIRY_SECONDS
        )
    except signing.BadSignature:
        # SignatureExpired is a subclass: an old token and a forged one look the
        # same to the caller, which is the point.
        return None


@deconstructible
class SignedFileSystemStorage(FileSystemStorage):
    """Private files on disk, under ``PRIVATE_MEDIA_ROOT``, with expiring URLs.

    A filesystem has no presigning, so ``url()`` builds the same thing with
    Django's ``signing``: ``/files/signed/<token>/``, where the token carries the
    file name and a timestamp and cannot be forged without ``SECRET_KEY``. The
    view behind it needs no login, exactly like a presigned S3 URL, and refuses
    the token after ``PRIVATE_URL_EXPIRY_SECONDS``.

    The location is resolved lazily from settings rather than passed to
    ``__init__``, so no absolute deployment path is ever baked into a migration.
    """

    @cached_property
    def base_location(self):
        return self._value_or_setting(self._location, settings.PRIVATE_MEDIA_ROOT)

    def url(self, name):
        return reverse("private_file_signed", args=[sign_file_name(name)])
{%- if cookiecutter.media_storage == "s3" %}


@deconstructible
class PrivateMediaStorage(S3Storage):
    """The private bucket: public access blocked, no CDN, SigV4 presigned URLs.

    Everything bucket-side comes from ``STORAGES['private']['OPTIONS']`` in
    ``settings/base.py``. What this class adds is ``Cache-Control: private,
    no-store`` on every presigned download, so the browser does not keep a copy
    of somebody's ID scan after the link has expired.
    """

    def url(self, name, parameters=None, expire=None, http_method=None):
        parameters = {"ResponseCacheControl": "private, no-store", **(parameters or {})}
        return super().url(name, parameters=parameters, expire=expire, http_method=http_method)
{%- elif cookiecutter.media_storage == "gcs" %}


@deconstructible
class PrivateMediaStorage(GoogleCloudStorage):
    """The private bucket: no public IAM grant, no CDN, signed URLs that expire.

    Everything bucket-side comes from ``STORAGES['private']['OPTIONS']`` in
    ``settings/base.py``. A class of its own so the private storage is named
    the same way on every backend, and has one place to grow behaviour.
    """
{%- elif cookiecutter.media_storage == "azure" %}


@deconstructible
class PrivateMediaStorage(AzureStorage):
    """The private container: no anonymous access, no CDN, SAS URLs that expire.

    Everything container-side comes from ``STORAGES['private']['OPTIONS']`` in
    ``settings/base.py``. A class of its own so the private storage is named
    the same way on every backend, and has one place to grow behaviour.
    """
{%- endif %}
{%- if cookiecutter.static_storage == "cloud" %}


class StaticCloudStorage(
    ManifestFilesMixin,
{%- if cookiecutter.media_storage == "s3" %}
    S3Storage,
{%- elif cookiecutter.media_storage == "gcs" %}
    GoogleCloudStorage,
{%- else %}
    AzureStorage,
{%- endif %}
):
    """Collected static files in the bucket, under content-hashed filenames.

    ``ManifestFilesMixin`` is what makes a long cache lifetime safe: every file
    carries a hash of its own content in its name, so a browser holding last
    week's CSS asks for a URL that no longer exists rather than rendering a stale
    page. It also rewrites the references inside CSS to the hashed names, which
    an "upload the directory" step does not.

    The manifest is read lazily. The mixin reads it in ``__init__``, and against a
    bucket that is a network round trip every time the storage object is built -
    including ``manage.py check`` and ``runserver`` on a machine with no bucket
    credentials, which would abort with an SDK error instead of doing their job.
    Nothing needs the manifest before a URL is built, so it is fetched then.
    """

    def __init__(self, *args, **kwargs):
        # Set before super(), which is what would otherwise do the read.
        self._manifest_pending = True
        super().__init__(*args, **kwargs)

    def read_manifest(self):
        if self._manifest_pending:
            return None
        return super().read_manifest()

    def stored_name(self, name):
        # The one place the manifest is consulted in order to build a URL.
        if self._manifest_pending:
            self._manifest_pending = False
            self.hashed_files, self.manifest_hash = self.load_manifest()
        return super().stored_name(name)

    def post_process(self, *args, **kwargs):
        # collectstatic rebuilds the manifest from scratch, so there is nothing
        # worth reading first - and reading it would be undone a line later.
        self._manifest_pending = False
        yield from super().post_process(*args, **kwargs)
{%- endif %}


def private_media_storage():
    """The configured private storage.

    Fields opt in with ``storage=private_media_storage`` - this callable, never a
    storage instance. Django records the function path in the migration, not a
    bucket name or a deployment path, so the migration is the same on every
    environment and changing the bucket never needs a new one. It is also how
    ``apps.core.private_files`` finds every private field by introspection.
    """
    return storages["private"]
