"""Public newsletter endpoints.

These are the only unauthenticated endpoints in the app, and subscribing sends
an e-mail, so it carries every control a public POST that consumes an external
resource has to carry: server-side validation, bot protection and a rate limit.
"""

from django.conf import settings
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.utils.translation import get_language
{% if cookiecutter.rate_limiting == "yes" %}from django.utils.translation import gettext as _
{% endif %}from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
{% if cookiecutter.rate_limiting == "yes" %}from django_ratelimit.decorators import ratelimit
{% endif %}{% if cookiecutter.multisite == "multi" %}from wagtail.models import Site
{% endif %}
from apps.newsletter import services
from apps.newsletter.forms import SubscribeForm
{% if cookiecutter.rate_limiting == "yes" %}
_RATE_PERIODS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def _newsletter_rate(group, request):
    """Read the budget at call time so an environment can tune it without a deploy."""
    return settings.RATELIMIT_NEWSLETTER


def _retry_after(rate: str) -> int:
    """Seconds in the rate's window, for the ``Retry-After`` header."""
    _count, _sep, period = rate.partition("/")
    quantity, unit = period[:-1], period[-1:]
    multiplier = int(quantity) if quantity.isdigit() else 1
    return multiplier * _RATE_PERIODS.get(unit, 3600)


def _rate_limited(request, is_ajax):
    """A 429 with Retry-After, not a bare 403: the caller must know it may retry."""
    message = _("Too many subscription attempts. Please try again later.")
    if is_ajax:
        response = JsonResponse({"ok": False, "errors": {"__all__": [message]}}, status=429)
    else:
        response = render(
            request,
            "newsletter/subscribe.html",
            {"form": SubscribeForm(request=request), "rate_limited": message},
            status=429,
        )
    response["Retry-After"] = str(_retry_after(settings.RATELIMIT_NEWSLETTER))
    return response

{% else %}
{% endif %}
@require_http_methods(["GET", "POST"])
{% if cookiecutter.rate_limiting == "yes" %}@ratelimit(key="ip", rate=_newsletter_rate, method="POST", block=False)
{% endif %}def subscribe(request):
    """Sign up an address and mail it a confirmation link.

    Nothing is ever sent to an address that has not used that link, and an
    address that already confirmed is not mailed again - so the endpoint cannot
    be pointed at somebody else's inbox to bother them.
    """
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    status = 200

    if request.method == "POST":
{%- if cookiecutter.rate_limiting == "yes" %}
        if getattr(request, "limited", False):
            return _rate_limited(request, is_ajax)
{%- endif %}
        form = SubscribeForm(request.POST, request=request)
        if form.is_valid():
            subscriber, _created = services.subscribe(
                form.cleaned_data["email"],
                language=get_language() or settings.LANGUAGE_CODE,
{%- if cookiecutter.multisite == "multi" %}
                site=Site.find_for_request(request),
{%- endif %}
            )
            if not subscriber.is_confirmed:
                services.send_confirmation(subscriber)
            if is_ajax:
                return JsonResponse({"ok": True})
            return render(request, "newsletter/subscribed.html", {"subscriber": subscriber})
        if is_ajax:
            return JsonResponse({"ok": False, "errors": form.errors}, status=400)
        status = 400
    else:
        form = SubscribeForm(request=request)

    return render(request, "newsletter/subscribe.html", {"form": form}, status=status)


def confirm(request, token):
    """Activate a subscription from the link in the confirmation e-mail."""
    subscriber = services.confirm(token)
    if subscriber is None:
        raise Http404
    return render(request, "newsletter/confirmed.html", {"subscriber": subscriber})


# CSRF exempt on purpose, and only here: RFC 8058 one-click unsubscribe is a
# POST from the recipient's mail provider, which has no session and no token.
# The URL itself is the credential - an unguessable UUID that does exactly what
# the GET version of this view does - so there is nothing for a forged request
# to gain.
@csrf_exempt
@require_http_methods(["GET", "POST"])
def unsubscribe(request, token):
    """Stop mailing the subscriber behind ``token``, in one click and with no login."""
    subscriber = services.unsubscribe(token)
    if subscriber is None:
        raise Http404
    return render(request, "newsletter/unsubscribed.html", {"subscriber": subscriber})
