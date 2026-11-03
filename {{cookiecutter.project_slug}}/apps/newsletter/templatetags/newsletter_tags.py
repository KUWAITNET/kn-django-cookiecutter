"""Template tags for embedding the signup form in a page this app does not own."""

from django import template

from apps.newsletter.forms import SubscribeForm

register = template.Library()


@register.inclusion_tag("newsletter/subscribe_form.html", takes_context=True)
def newsletter_signup_form(context):
    """Render the signup form anywhere - the footer, a landing page, a sidebar.

    The form is built here rather than written out in the host template so it
    always carries the fields the subscribe view checks. A hand-rolled copy in a
    footer fails the app's own spam check, which is exactly the kind of bug that
    only shows up once the site is live.
    """
    request = context.get("request")
    return {
        "form": SubscribeForm(request=request),
        "request": request,
        # inclusion_tag builds an isolated context, so the partial's CSRF token
        # tag has nothing to read unless it is passed through.
        "csrf_token": context.get("csrf_token"),
    }
