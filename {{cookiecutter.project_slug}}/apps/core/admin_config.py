"""App config that mounts ``django.contrib.admin`` with this project's admin site.

``INSTALLED_APPS`` lists this class instead of ``django.contrib.admin`` so the
Unfold-based site{% if cookiecutter.use_2fa == "yes" %} (with two-factor enforcement){% endif %} is the one every admin view is
served from - including ``admin.site.urls``, which is what ``urls.py`` mounts.
"""

from django.contrib.admin.apps import AdminConfig


class KuwaitnetAdminConfig(AdminConfig):
    default_site = "apps.core.admin_site.KuwaitnetAdminSite"
    # Never a candidate for automatic app-config discovery: this class is
    # referenced by its full dotted path from INSTALLED_APPS.
    default = False
