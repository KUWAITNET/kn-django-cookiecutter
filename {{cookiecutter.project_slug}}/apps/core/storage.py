"""Storage for uploads that must never be reachable from a public URL.

Files holding personal data - CVs, ID copies, vendor certificates, anything a
visitor attached to a form - go here. Public media is served with no access
control, so a predictable name there is a public document; in our reference
project that is exactly how applicant CVs became enumerable. Files stored here
are reachable only through ``apps.core.views.serve_private_file``, which checks a
permission first.

The split is the same whichever backend the project selected: a public storage
for editorial media, and this one for personal data. Only what sits underneath
changes.
"""

from django.conf import settings
{%- if cookiecutter.static_storage == "cloud" %}
from django.contrib.staticfiles.storage import ManifestFilesMixin
{%- endif %}
from django.core.files.storage import FileSystemStorage, storages
from django.utils.deconstruct import deconstructible
from django.utils.functional import cached_property
{%- if cookiecutter.media_storage == "s3" %}
from storages.backends.s3 import S3Storage
{%- elif cookiecutter.media_storage == "gcs" %}
from storages.backends.gcloud import GoogleCloudStorage
{%- elif cookiecutter.media_storage == "azure" %}
from storages.backends.azure_storage import AzureStorage
{%- endif %}

NO_PUBLIC_URL = (
    "Private media has no public URL. Link to it with "
    "reverse('private_media', args=[name]) so the permission check runs."
)
{%- if cookiecutter.media_storage == "filesystem" %}


@deconstructible
class PrivateMediaStorage(FileSystemStorage):
    """Filesystem storage rooted at ``PRIVATE_MEDIA_ROOT``, with no public URL.

    ``base_location``/``base_url`` are resolved lazily from settings rather than
    passed to ``__init__`` so that no absolute deployment path is ever baked into
    a migration.
    """

    @cached_property
    def base_location(self):
        return self._value_or_setting(self._location, settings.PRIVATE_MEDIA_ROOT)

    @cached_property
    def base_url(self):
        # No public URL by construction: url() below is the only accessor and it
        # refuses, so a template that renders the file's url attribute fails
        # loudly in development instead of leaking the path in production.
        return None

    def url(self, name):
        raise ValueError(NO_PUBLIC_URL)
{%- else %}


@deconstructible
class PrivateFileSystemStorage(FileSystemStorage):
    """The private store on local disk, refusing to build a URL just the same.

    Used by the test settings. The suite runs with no cloud credentials and no
    network - a test that needs a real bucket is an integration test - but it
    still has to exercise the behaviour that matters, which is that nothing in
    the project can hand out a link to a private file.
    """

    @cached_property
    def base_url(self):
        return None

    def url(self, name):
        raise ValueError(NO_PUBLIC_URL)


@deconstructible
class PrivateMediaStorage(
{%- if cookiecutter.media_storage == "s3" %}
    S3Storage
{%- elif cookiecutter.media_storage == "gcs" %}
    GoogleCloudStorage
{%- else %}
    AzureStorage
{%- endif %}
):
    """Object storage for personal data: private prefix, signed URLs, no ACL.

    Everything bucket-side comes from ``STORAGES['private_media']['OPTIONS']`` in
    ``settings/base.py``: no public ACL, its own prefix (or its own bucket), and
    no CDN in front, because an edge cache is a copy of the file sitting outside
    every permission check. What this class adds is the refusal to hand out a URL
    at all.

    ``PRIVATE_MEDIA_SIGNED_URLS`` is the documented opt-in. Left off, every
    download is streamed through the permission-checked view, so the check runs
    on every byte and no shareable URL exists anywhere. Turned on, the view
    redirects to a short-lived signed URL instead: cheaper for large files, but
    that URL stays valid for its whole lifetime to anyone holding it - including
    after the user logs out, loses the permission, or forwards the link.
    """

    def url(self, name, *args, **kwargs):
        if not settings.PRIVATE_MEDIA_SIGNED_URLS:
            raise ValueError(NO_PUBLIC_URL)
        return super().url(name, *args, **kwargs)
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

    A callable rather than a module-level instance: ``FileField`` resolves it
    once at model-import time, after settings are loaded, so the storage follows
    ``STORAGES['private_media']`` and the test settings can repoint it without a
    single model changing. Django records the reference to this function in the
    migration, so no bucket name and no deployment path is baked in either.
    """
    return storages["private_media"]
