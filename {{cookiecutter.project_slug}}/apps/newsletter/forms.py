"""The public signup form and the admin composer."""

from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

{% if cookiecutter.spam_protection != "none" %}from apps.core.spam import SpamProtectionMixin
{% endif %}from apps.newsletter.models import AUDIENCE_ALL
from apps.newsletter.services import check_template_source

# Campaign copy is Django template source in a plain monospace textarea,
# deliberately not a rich-text editor: template source is code, and a rich-text
# editor's round-trip mangles it.
BODY_WIDGET_ATTRS = {
    "rows": 14,
    "spellcheck": "false",
    "style": "font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;",
}


def audience_choices():
    return [(AUDIENCE_ALL, _("Everyone"))] + [
        (code, label) for code, label in settings.LANGUAGES
    ]


class SubscribeForm({% if cookiecutter.spam_protection != "none" %}SpamProtectionMixin, {% endif %}forms.Form):
    """Public newsletter signup.

    A plain ``Form``, not a ``ModelForm``: resubmitting an address must
    reactivate the existing subscriber rather than fail a uniqueness check, and
    that decision belongs in ``services.subscribe``.
    """

    email = forms.EmailField(
        label=_("E-mail"),
        max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Set after super() so it survives a mixin that declares its own
        # request kwarg and defaults it to None.
        if request is not None:
            self.request = request

    def clean_email(self):
        # Normalised so the same person cannot end up on the list twice with a
        # different capitalisation.
        return self.cleaned_data["email"].strip().lower()


class CampaignForm(forms.Form):
    """Compose one campaign: a subject and a body per configured language.

    Fields are built from ``settings.LANGUAGES`` rather than declared, so adding
    a language to the project adds a pair of fields here and nothing else.
    """

    audience = forms.ChoiceField(
        label=_("Send to"),
        choices=audience_choices,
        initial=AUDIENCE_ALL,
        widget=forms.Select(attrs={"data-newsletter-audience": ""}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for code, label in settings.LANGUAGES:
            self.fields[f"subject_{code}"] = forms.CharField(
                label=_("Subject (%(language)s)") % {"language": label},
                max_length=255,
                required=False,
            )
            self.fields[f"body_{code}"] = forms.CharField(
                label=_("Message (%(language)s)") % {"language": label},
                required=False,
                widget=forms.Textarea(attrs=BODY_WIDGET_ATTRS),
            )

    def clean(self):
        cleaned = super().clean()
        content = {}
        for code, _label in settings.LANGUAGES:
            subject = (cleaned.get(f"subject_{code}") or "").strip()
            body = (cleaned.get(f"body_{code}") or "").strip()
            if not subject and not body:
                continue
            if not subject:
                self.add_error(f"subject_{code}", _("Add a subject for this language."))
            if not body:
                self.add_error(f"body_{code}", _("Add a message for this language."))
            for field_name, source in ((f"subject_{code}", subject), (f"body_{code}", body)):
                error = check_template_source(source)
                if error is not None:
                    self.add_error(field_name, error)
            if subject and body:
                content[code] = {"subject": subject, "body": body}

        if not content and not self.errors:
            # Attached to a field: a form-wide error would render nowhere in
            # either admin's field-by-field layout.
            self.add_error(
                f"subject_{settings.LANGUAGE_CODE}",
                _("Compose the newsletter in at least one language."),
            )
        cleaned["content"] = content
        return cleaned
