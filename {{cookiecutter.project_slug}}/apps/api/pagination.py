"""Pagination defaults for the whole API (api-standard.md A7)."""

from rest_framework.pagination import PageNumberPagination


class DefaultPagination(PageNumberPagination):
    """Company default: 20 rows a page, hard ceiling of 100.

    Wired in as ``REST_FRAMEWORK["DEFAULT_PAGINATION_CLASS"]``, so every list
    endpoint is paginated without opting in. An unpaginated list is an unbounded
    response, and an unbounded response is a denial-of-service primitive the
    client did not have to work for.

    ``max_page_size`` is the unrestricted-resource-consumption control (OWASP
    API4): ``?page_size=100000`` is clamped to 100 server-side rather than
    honoured or rejected, so a client that asks for too much still gets a usable
    answer and the database still does bounded work.

    The response envelope is identical on every list endpoint, and clients may
    rely on it::

        {
          "count": 143,
          "next": "https://host/api/v1/notes/?page=3&page_size=20",
          "previous": "https://host/api/v1/notes/?page=1&page_size=20",
          "results": [ ... ]
        }

    ``next`` and ``previous`` are absolute URLs, or ``null`` on the first/last
    page. Changing the page size, the default ordering or the pagination style
    is a breaking change and needs a new API version.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
