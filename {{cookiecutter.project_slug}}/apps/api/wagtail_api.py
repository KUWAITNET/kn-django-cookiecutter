{%- if cookiecutter.api == "headless" -%}
"""CMS content API - read-only page, image and document delivery (api-standard.md A13).

This is **not** an application API. It is a read-only delivery surface for a
headless front-end. Anything that writes, anything that authenticates a user,
anything with business rules, form submissions, per-user data and search with
business filters are DRF endpoints under ``/api/v1/``. A project that starts
posting form data here has taken a wrong turn.

It is enabled only because this project was generated headless. On a
conventionally-rendered site it stays off: a public, unauthenticated read API
over the whole content tree is attack surface nobody asked for.

**The field allowlist is the whole security model.** A page type exposes only
what its ``api_fields`` declares, and the viewsets below declare their own
``body_fields`` / ``meta_fields`` / ``listing_default_fields`` explicitly rather
than extending the library defaults. There is no "expose the whole model":
``?fields=*`` returns the declared allowlist and nothing else, which is what
makes it safe to keep an internal note, a moderation comment or an editor's
e-mail address on the same model. A field added to a page model later is
invisible here until somebody adds it to ``api_fields`` on purpose.

Only live, public pages are served. Drafts and password- or group-restricted
pages must not be reachable through this API, and a test asserts it.
"""

from rest_framework.permissions import AllowAny
from wagtail.api.v2.router import WagtailAPIRouter
from wagtail.api.v2.views import PagesAPIViewSet
from wagtail.documents.api.v2.views import DocumentsAPIViewSet
from wagtail.images.api.v2.views import ImagesAPIViewSet

from apps.api.throttling import PublicReadRateThrottle


class ContentAPIViewSetMixin:
    """Permission, throttling and schema policy shared by all three endpoints.

    ``AllowAny`` is the deliberate, explicit opt-out from the project-wide
    deny-by-default: these endpoints serve the published website's own content to
    its front-end, and that content is public by definition. The queryset is
    still restricted to live, public pages, so a draft or a password-restricted
    page is unreachable here whoever asks. A project whose content is *not*
    public deletes this line, and the global ``IsAuthenticated`` takes over.

    A public endpoint is a free resource, so it always carries a throttle. These
    are DRF viewsets, so the API-wide throttling applies only when it is
    attached - leaving them on the global defaults and hoping is not the same
    thing.

    ``schema = None`` keeps them out of our OpenAPI document on purpose: the CMS
    API has its own documented, versioned contract, and folding it into the
    application schema would publish a second, differently-shaped API under our
    own version number.
    """

    permission_classes = [AllowAny]
    throttle_classes = [PublicReadRateThrottle]
    schema = None


class ContentPagesAPIViewSet(ContentAPIViewSetMixin, PagesAPIViewSet):
    """Live public pages only. Fields are an explicit allowlist."""

    body_fields = ["id", "type", "detail_url", "title"]
    meta_fields = [
        "type",
        "detail_url",
        "html_url",
        "slug",
        "show_in_menus",
        "seo_title",
        "search_description",
        "first_published_at",
    ]
    listing_default_fields = [
        "id",
        "type",
        "detail_url",
        "html_url",
        "title",
        "slug",
        "first_published_at",
    ]
    nested_default_fields = ["id", "type", "detail_url", "title"]


class ContentImagesAPIViewSet(ContentAPIViewSetMixin, ImagesAPIViewSet):
    """Renditions and metadata. Never the uploader, never internal collection notes."""

    body_fields = ["id", "title", "width", "height"]
    meta_fields = ["type", "detail_url", "download_url"]
    listing_default_fields = ["id", "type", "detail_url", "title"]
    nested_default_fields = ["id", "type", "detail_url", "title"]


class ContentDocumentsAPIViewSet(ContentAPIViewSetMixin, DocumentsAPIViewSet):
    """Document metadata and download URLs, on the same allowlist discipline."""

    body_fields = ["id", "title"]
    meta_fields = ["type", "detail_url", "download_url"]
    listing_default_fields = ["id", "type", "detail_url", "title"]
    nested_default_fields = ["id", "type", "detail_url", "title"]


api_router = WagtailAPIRouter("wagtailapi")
api_router.register_endpoint("pages", ContentPagesAPIViewSet)
api_router.register_endpoint("images", ContentImagesAPIViewSet)
api_router.register_endpoint("documents", ContentDocumentsAPIViewSet)
{% endif -%}
