"""URL configuration for {{ cookiecutter.project_name }}.

No admin is at /admin/{% if cookiecutter.stack == "wagtail" %}, and the two sit on separate prefixes (see
settings.WAGTAIL_ADMIN_URL_PREFIX and settings.DJANGO_ADMIN_URL_PREFIX){% else %} (see settings.DJANGO_ADMIN_URL_PREFIX){% endif %}. That is
defence in depth against automated scanners, not a security control in its own
right: 2FA, lockout and TLS do the actual work.
"""

from django.conf import settings
{%- if cookiecutter.languages == "en_ar" %}
from django.conf.urls.i18n import i18n_patterns
{%- endif %}
from django.conf.urls.static import static
from django.contrib import admin
{%- if cookiecutter.stack != "wagtail" and cookiecutter.frontend != "api_only" %}
from django.contrib.sitemaps.views import sitemap
{%- endif %}
from django.urls import include, path
{%- if cookiecutter.stack == "wagtail" %}
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.contrib.sitemaps.views import sitemap
from wagtail.documents import urls as wagtaildocs_urls
{%- endif %}

{%- if cookiecutter.api == "headless" %}
from apps.api.wagtail_api import api_router
{%- endif %}
from apps.core import views as core_views
{%- if cookiecutter.stack != "wagtail" and cookiecutter.frontend != "api_only" %}
from apps.core.sitemaps import SITEMAPS
{%- endif %}

{%- if cookiecutter.stack == "wagtail" %}
WAGTAIL_ADMIN = settings.WAGTAIL_ADMIN_URL_PREFIX
DJANGO_ADMIN = settings.DJANGO_ADMIN_URL_PREFIX
{%- else %}
DJANGO_ADMIN = settings.DJANGO_ADMIN_URL_PREFIX
{%- endif %}

# Non-localised URLs. The sitemap deliberately sits OUTSIDE i18n_patterns: a
# sitemap whose contents depend on the request language emits one language
# non-deterministically. Ours lists every language's URLs on one canonical path.
urlpatterns = [
{%- if cookiecutter.stack == "wagtail" %}
    # The Django admin hosts the models that have no Wagtail interface
    # (e-mail log, lockout records, countries). Both admins require staff and 2FA,
    # and they sit on unrelated prefixes so one guess cannot reach both.
    path(f"{DJANGO_ADMIN}/", admin.site.urls),
    path(f"{WAGTAIL_ADMIN}/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
{%- else %}
    path(f"{DJANGO_ADMIN}/", admin.site.urls),
{%- endif %}
{%- if cookiecutter.frontend != "api_only" %}
    path("robots.txt", core_views.robots_txt, name="robots_txt"),
    # RFC 9116. Outside the i18n patterns on purpose: it is read by scanners and
    # researchers, not browsers, and must answer at exactly one address.
    path(
        ".well-known/security.txt",
        core_views.security_txt,
        name="security_txt",
    ),
{%- if cookiecutter.stack == "wagtail" %}
    path("sitemap.xml", sitemap, name="sitemap"),
{%- else %}
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
{%- endif %}
{%- endif %}
    # Health endpoint for uptime monitoring: it touches the database, so it fails
    # when the site is up but the database is not.
    path("healthz", core_views.healthz, name="healthz"),
    # Uploads containing personal data are never served from MEDIA_URL.
    path(
        "private-media/<path:relative_path>",
        core_views.serve_private_file,
        name="private_media",
    ),
{%- if cookiecutter.api != "none" %}
    path("api/", include("apps.api.urls")),
{%- endif %}
{%- if cookiecutter.api == "headless" %}
    # Namespaced away from our own versioned API so a future /api/v2/ of the
    # application cannot collide with the CMS content API.
    path("api/cms/v2/", api_router.urls),
{%- endif %}
{%- if cookiecutter.newsletter == "yes" %}
    path("newsletter/", include("apps.newsletter.urls")),
{%- endif %}
]
{% if cookiecutter.sentry == "yes" %}
if settings.SENTRY_DSN and settings.DEBUG:
    # Registered only when a DSN is configured AND debug is on, so it can never be
    # routable in production.
    urlpatterns += [path("sentry-debug/", core_views.trigger_error)]
{% endif %}
{%- if cookiecutter.frontend == "api_only" %}
{%- if cookiecutter.languages == "en_ar" %}

urlpatterns += i18n_patterns(
    path("i18n/", include("django.conf.urls.i18n")),
    prefix_default_language=True,
)
{%- endif %}
{%- else %}
{%- if cookiecutter.languages == "en_ar" %}

# Localised URLs. prefix_default_language=True keeps English on /en/ so neither
# language is privileged and hreflang alternates are symmetric.
urlpatterns += i18n_patterns(
{%- if cookiecutter.stack == "wagtail" %}
    path("search/", include("apps.search.urls")),
    path("", include(wagtail_urls)),
{%- else %}
{%- if cookiecutter.forms_suite == "yes" %}
    # On the CMS stack this lives in the page tree; here it needs a route.
    path("contact/", include("apps.contact.urls")),
{%- endif %}
    path("", include("apps.core.urls")),
{%- endif %}
    prefix_default_language=True,
)
{%- else %}

urlpatterns += [
{%- if cookiecutter.stack == "wagtail" %}
    path("search/", include("apps.search.urls")),
    path("", include(wagtail_urls)),
{%- else %}
{%- if cookiecutter.forms_suite == "yes" %}
    # On the CMS stack this lives in the page tree; here it needs a route.
    path("contact/", include("apps.contact.urls")),
{%- endif %}
    path("", include("apps.core.urls")),
{%- endif %}
]
{%- endif %}
{%- endif %}

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

    try:
        import debug_toolbar  # noqa: F401

        urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
    except ImportError:
        pass

handler400 = "apps.core.views.bad_request"
handler403 = "apps.core.views.permission_denied"
handler404 = "apps.core.views.page_not_found"
handler500 = "apps.core.views.server_error"
