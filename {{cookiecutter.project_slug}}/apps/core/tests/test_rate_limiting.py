"""Rate limiting and login lockout.

The three layers do different jobs and must not be stacked on one view: DRF
throttles cover ``/api/``, django-ratelimit covers public non-DRF POSTs, and
django-axes covers authentication (a lockout is not a rate cap).
"""

{% if cookiecutter.frontend != "api_only" -%}
from unittest import mock

{% endif -%}
import pytest
from django.conf import settings
{%- if cookiecutter.frontend != "api_only" %}
from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory
from django_ratelimit.decorators import ratelimit
from django_ratelimit.exceptions import Ratelimited
{%- endif %}


def test_axes_backend_is_checked_before_the_model_backend():
    # A lockout that runs after the credential check is not a lockout.
    assert settings.AUTHENTICATION_BACKENDS[0] == "axes.backends.AxesStandaloneBackend"


def test_lockout_is_recorded_per_username_and_ip():
    # Locking on the username alone lets anyone lock a known account out.
    assert settings.AXES_LOCKOUT_PARAMETERS == [["username", "ip_address"]]
    assert settings.AXES_FAILURE_LIMIT >= 1


@pytest.mark.parametrize(
    "name",
    ["AXES_FAILURE_LIMIT", "AXES_COOLOFF_TIME", "AXES_LOCKOUT_PARAMETERS", "AXES_RESET_ON_SUCCESS"],
)
def test_every_lockout_setting_is_configured(name):
    # Reviewable in one place rather than discovered during an incident.
    assert hasattr(settings, name)
{%- if cookiecutter.frontend != "api_only" %}


def test_budgets_are_tightest_where_a_request_costs_an_external_resource():
    # Each of these settings exists so the value is reviewable in one place
    # rather than scattered across decorators.
    assert settings.RATELIMIT_FORM_SUBMIT
    assert settings.RATELIMIT_NEWSLETTER
    assert settings.RATELIMIT_SEARCH


@pytest.fixture
def _clear_rate_limit_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.usefixtures("_clear_rate_limit_cache")
def test_a_public_post_view_is_capped(settings):
    settings.RATELIMIT_ENABLE = True

    @ratelimit(key="ip", rate="2/m", method="POST", block=True)
    def submit(request):
        return HttpResponse("ok")

    factory = RequestFactory()
    for _ in range(2):
        assert submit(factory.post("/submit/")).status_code == 200

    with pytest.raises(Ratelimited):
        submit(factory.post("/submit/"))


@pytest.mark.usefixtures("_clear_rate_limit_cache")
def test_reads_are_not_capped_by_a_post_only_rule(settings):
    settings.RATELIMIT_ENABLE = True

    @ratelimit(key="ip", rate="1/m", method="POST", block=True)
    def submit(request):
        return HttpResponse("ok")

    factory = RequestFactory()
    for _ in range(5):
        assert submit(factory.get("/submit/")).status_code == 200
{%- endif %}


def test_rate_limiting_fails_closed():
    """A cache outage must cost availability, not the rate limit.

    django-ratelimit defaults to this, but the setting is asserted rather than
    assumed: with FAIL_OPEN a Redis outage silently removes the limit from every
    endpoint that most needed it, and nothing in the logs mentions it.
    """
    assert getattr(settings, "RATELIMIT_FAIL_OPEN", False) is False
{%- if cookiecutter.frontend != "api_only" %}


def test_unreadable_cache_blocks_rather_than_allows(rf, settings):
    """The behaviour behind the setting, not just the setting.

    A cache whose reads return None is what django-ratelimit sees when the
    backend is unreachable. The request must be refused.
    """

    # The test settings disable rate limiting, as the other tests here do too.
    settings.RATELIMIT_ENABLE = True

    class DeadCache:
        def get(self, *args, **kwargs):
            return None

        def set(self, *args, **kwargs):
            return None

        def incr(self, *args, **kwargs):
            raise ValueError("cache unavailable")

        def add(self, *args, **kwargs):
            return False

    @ratelimit(key="ip", rate="1/h", block=True)
    def view(request):
        return HttpResponse("should not be reached")

    request = rf.post("/")
    with mock.patch("django_ratelimit.core.caches", {"default": DeadCache()}):
        with pytest.raises(Ratelimited):
            view(request)
{%- endif %}
