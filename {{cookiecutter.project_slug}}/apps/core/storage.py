"""Storage for uploads that must never be reachable from ``MEDIA_URL``.

Files holding personal data - CVs, ID copies, vendor certificates, anything a
visitor attached to a form - go here. ``MEDIA_ROOT`` is served straight off the
web server with no access control, so a predictable filename there is a public
document; in our reference project that is exactly how applicant CVs became
enumerable. Files stored here are reachable only through
``apps.core.views.serve_private_file``, which checks a permission first.
"""

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible
from django.utils.functional import cached_property


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
        raise ValueError(
            "Private media has no public URL. Link to it with "
            "reverse('private_media', args=[name]) so the permission check runs."
        )


#: Import this and pass it as ``storage=`` on any confidential upload field.
private_media_storage = PrivateMediaStorage()
