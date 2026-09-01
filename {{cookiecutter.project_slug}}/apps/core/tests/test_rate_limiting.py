"""Rate limiting and login lockout.

The three layers do different jobs and must not be stacked on one view: DRF
throttles cover ``/api/``, django-ratelimit covers public non-DRF POSTs, and
django-axes covers authentication (a lockout is not a rate cap).
"""

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
