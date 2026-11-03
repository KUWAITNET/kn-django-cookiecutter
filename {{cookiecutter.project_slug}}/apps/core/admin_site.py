{% if cookiecutter.use_2fa == "yes" -%}
"""The project's Django admin site.

django-unfold is the KUWAITNET standard skin wherever ``django.contrib.admin`` is
mounted, on both stacks, so every admin view inherits ``UnfoldAdminSite``.
"""

from django.conf import settings
from django.contrib.admin.sites import AdminSite
from django_otp.admin import OTPAdminSite
from unfold.sites import UnfoldAdminSite

{% if cookiecutter.stack == "wagtail" -%}
#: Which setting turns the requirement off. The CMS admin and the Django admin
#: are governed by one switch, so a project cannot end up half-protected.
OTP_REQUIRED_SETTING = "WAGTAIL_2FA_REQUIRED"
{%- else -%}
OTP_REQUIRED_SETTING = "OTP_ADMIN_REQUIRED"
{%- endif %}


class KuwaitnetAdminSite(OTPAdminSite, UnfoldAdminSite):
    """Unfold-skinned admin that additionally requires a verified OTP device.

    ``OTPAdminSite`` comes first in the MRO so its ``has_permission`` wins, while
    Unfold still supplies the templates and ``each_context``.

    Why this matters: ``is_staff`` alone is not enough. A stolen or reused
    password gives an attacker a staff *session*, and every admin view - user
    management, content, the e-mail log, uploaded files - is reachable from it.
    Requiring ``request.user.is_verified()`` here closes that off for the whole
    site in one place, rather than per view, where one missed decorator is a hole.

    ``login_template`` is deliberately not overridden: django-otp's template
    extends ``admin/login.html``, which Unfold provides, so the OTP token field
    appears on the branded login page.
    """

    def has_permission(self, request):
        # Active and staff, before anything OTP-specific.
        if not AdminSite.has_permission(self, request):
            return False
        if not getattr(settings, OTP_REQUIRED_SETTING, True):
            # Only ever false in the test settings; production keeps the default.
            return True
        return super().has_permission(request)
{%- else -%}
"""The project's Django admin site.

django-unfold is the KUWAITNET standard skin wherever ``django.contrib.admin`` is
mounted, on both stacks, so every admin view inherits ``UnfoldAdminSite``.
"""

from unfold.sites import UnfoldAdminSite


class KuwaitnetAdminSite(UnfoldAdminSite):
    """Unfold-skinned admin site.

    This project was generated without two-factor authentication, which is a
    documented exception under the KUWAITNET security baseline - record it in
    docs/decisions.md. Adding it later means installing django-otp and mixing
    ``django_otp.admin.OTPAdminSite`` in ahead of ``UnfoldAdminSite``.
    """
{%- endif %}
