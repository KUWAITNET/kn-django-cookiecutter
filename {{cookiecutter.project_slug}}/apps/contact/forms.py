"""The reference public form.

Four things every public form in a KUWAITNET project must do, in one place:

1. an **explicit** ``Meta.fields`` list. Never ``__all__``: a field added to the
   model later would become writable from the public internet without anybody
   deciding that it should be;
2. server-side validation of every field, including the ones the browser also
   checks - ``required``, ``type="email"`` and ``accept=`` are conveniences for
   people, not controls;
3. bot protection, mixed in rather than reimplemented;
4. an upload that is size-checked, extension-checked, content-sniffed and stored
   privately under a generated name.

{% if cookiecutter.countries_app != "none" -%}
The split-phone UI (a country-code select plus a national number) is here rather
than in the template because the two halves have to be recombined and validated
together. In the project this template is derived from that recombination was
copy-pasted into four forms, and the four copies had drifted into four slightly
different validators.

Which country and dial-code lists this form offers is not decided here: it comes
from ``apps.core.countries``, so swapping the project's countries backend does not
touch a form.
{%- else -%}
This project has no countries backend, so there is no country field and no
dial-code select: the phone is one international input, normalised to E.164 by
``phonenumbers`` in ``clean()`` rather than in the template. In the project this
template is derived from that normalisation was copy-pasted into four forms, and
the four copies had drifted into four slightly different validators.
{%- endif %}
"""

from pathlib import PurePosixPath

import phonenumbers
from django import forms
from django.utils.translation import gettext_lazy as _

from apps.contact.models import ContactSubmission
{%- if cookiecutter.countries_app != "none" %}
from apps.core.countries import country_form_field, phone_code_choices
{%- endif %}
{%- if cookiecutter.spam_protection != "none" %}
from apps.core.spam import SpamProtectedForm
{%- endif %}
{% if cookiecutter.countries_app != "none" %}
PHONE_INVALID_MESSAGE = _("Enter a valid phone number, for example 22345678.")
{%- else %}
#: No dial-code list on this project, so the visitor types the whole number and the
#: example has to show the country calling code they are expected to include.
PHONE_INVALID_MESSAGE = _(
    "Enter a valid phone number in international format, for example +965 2234 5678."
)
{%- endif %}

#: Field names this form declares itself. Anything else on the form was injected
#: by a mixin (the honeypot), and the template renders those generically so it
#: never has to hard-code a honeypot's name - which would defeat the point of
#: being able to rename it per project.
DECLARED_FIELDS = (
    "full_name",
    "company_name",
    "email",
{%- if cookiecutter.countries_app != "none" %}
    "country",
    "country_code",
{%- endif %}
    "mobile_no",
    "enquiry_type",
    "subject",
    "message",
    "attachment",
)


class ContactForm({% if cookiecutter.spam_protection != "none" %}SpamProtectedForm, {% endif %}forms.ModelForm):
    """Public contact form.

    Copy this class for the next form. What matters is the shape, not the fields.
    """
{% if cookiecutter.countries_app != "none" %}
    # Not model fields: `phone` is one column, and the visitor fills in two
    # inputs. clean() recombines them and stores E.164 in cleaned_data["phone"].
    #
    # A real ChoiceField rather than a template loop over countries, so a dial
    # code the visitor invented is rejected server-side instead of being
    # concatenated into an unparseable number. Choices are filled in __init__
    # from apps.core.countries, which is the only module that knows where dial
    # codes come from on this project.
    country_code = forms.ChoiceField(
        label=_("Country code"),
        required=False,
        choices=[],
    )
    mobile_no = forms.CharField(
        label=_("Phone number"),
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "tel-national"}),
    )
{%- else %}
    # Not a model field: `phone` is one column and this is the raw input clean()
    # normalises into E.164. With no countries backend there is no dial-code list
    # to offer, so this is one international input rather than a split pair, and
    # phonenumbers has to find the country from the "+" prefix the visitor types.
    mobile_no = forms.CharField(
        label=_("Phone"),
        required=False,
        max_length=32,
        widget=forms.TextInput(
            attrs={
                "inputmode": "tel",
                "autocomplete": "tel",
                "placeholder": "+965 2234 5678",
            }
        ),
    )
{%- endif %}

    enquiry_type = forms.ChoiceField(
        label=_("Type of enquiry"),
        choices=[("", _("Select a type"))] + ContactSubmission.EnquiryType.choices,
        error_messages={
            "required": _("Please choose the type of enquiry."),
            "invalid_choice": _("Choose one of the listed enquiry types."),
        },
    )

    class Meta:
        model = ContactSubmission
        # Explicit, and reviewed whenever the model changes. `phone`,
        # `attachment_original_name` and `submitted_at` are set by this form or by
        # the database, never by the visitor.
        fields = [
            "full_name",
            "company_name",
            "email",
{%- if cookiecutter.countries_app != "none" %}
            "country",
{%- endif %}
            "enquiry_type",
            "subject",
            "message",
            "attachment",
        ]
        widgets = {
            "message": forms.Textarea(attrs={"rows": 6}),
        }
        error_messages = {
            "full_name": {"required": _("Please enter your name.")},
            "email": {
                "required": _("Please enter your e-mail address."),
                "invalid": _("Enter a valid e-mail address."),
            },
            "subject": {"required": _("Please enter a subject.")},
            "message": {"required": _("Please enter your message.")},
        }

    def __init__(self, *args, request=None, **kwargs):
{%- if cookiecutter.spam_protection != "none" %}
        # The mixin needs the request so Turnstile is verified with the client IP.
        super().__init__(*args, request=request, **kwargs)
{%- else %}
        super().__init__(*args, **kwargs)
        self.request = request
{%- endif %}
{%- if cookiecutter.countries_app != "none" %}
        # One definition of "a country a visitor may pick", for both selects, and
        # it lives in apps.core.countries. Copy-pasting the filter instead is what
        # produced two disagreeing country lists in the project this template is
        # derived from. Built per form instance rather than at import, so a
        # deactivation or an exclusion takes effect on the next submission.
        #
        # ModelForm has already generated a `country` field from the model; this
        # replaces it in place, keeping its position in the field order.
        self.fields["country"] = country_form_field()
        self.fields["country_code"].choices = [("", _("Code"))] + phone_code_choices()
{%- endif %}

    @property
    def protection_fields(self):
        """Fields a mixin added, for the template to render generically.

        The honeypot's name is meant to be changed per project, so no template
        may name it.
        """
        return [self[name] for name in self.fields if name not in DECLARED_FIELDS]

    def clean_mobile_no(self):
        value = (self.cleaned_data.get("mobile_no") or "").strip()
{%- if cookiecutter.countries_app != "none" %}
        # Spaces, dashes and brackets are how people write phone numbers; strip
        # them rather than rejecting a correct number typed in a normal way. The
        # dial code arrives from its own field, so nothing but digits is wanted.
        digits = "".join(character for character in value if character.isdigit())
        if value and not digits:
            raise forms.ValidationError(PHONE_INVALID_MESSAGE, code="invalid")
        return digits
{%- else %}
        # Spaces, dashes and brackets are how people write phone numbers; strip
        # them rather than rejecting a correct number typed in a normal way. The
        # leading "+" survives: it is the only thing that tells phonenumbers which
        # country this number belongs to when there is no dial-code field.
        kept = "".join(character for character in value if character.isdigit() or character == "+")
        if value and not kept.lstrip("+"):
            raise forms.ValidationError(PHONE_INVALID_MESSAGE, code="invalid")
        return kept
{%- endif %}

    def clean(self):
        cleaned_data = super().clean()
        number = cleaned_data.get("mobile_no") or ""
{%- if cookiecutter.countries_app != "none" %}
        code = (cleaned_data.get("country_code") or "").strip()
{%- endif %}

        if not number:
{%- if cookiecutter.countries_app != "none" %}
            # Phone is optional. A country code alone is not a phone number.
{%- else %}
            # Phone is optional.
{%- endif %}
            cleaned_data["phone"] = ""
            return cleaned_data
{%- if cookiecutter.countries_app != "none" %}

        if not code:
            self.add_error("country_code", _("Please choose the country code."))
            return cleaned_data
{%- endif %}

        try:
{%- if cookiecutter.countries_app != "none" %}
            # Region None forces the string to carry its own +CC, which is why the
            # select's values are "+965"-shaped rather than "965".
            parsed = phonenumbers.parse(f"{code}{number}", None)
{%- else %}
            # Region None forces the string to carry its own +CC. With no country
            # field there is nothing to guess a region from, so a number typed
            # without the "+" prefix is refused rather than assumed to be local.
            parsed = phonenumbers.parse(number, None)
{%- endif %}
        except phonenumbers.phonenumberutil.NumberParseException:
            self.add_error("mobile_no", PHONE_INVALID_MESSAGE)
            return cleaned_data

        if not phonenumbers.is_valid_number(parsed):
            # Parsing only proves the string looks like a number; this proves the
            # number could exist in that country's plan.
            self.add_error("mobile_no", PHONE_INVALID_MESSAGE)
            return cleaned_data

        # A key with no matching form field, so ModelForm._post_clean will not try
        # to write it; save() below does that explicitly.
        cleaned_data["phone"] = phonenumbers.format_number(
            parsed, phonenumbers.PhoneNumberFormat.E164
        )
        return cleaned_data

    def save(self, commit=True):
        submission = super().save(commit=False)
        submission.phone = self.cleaned_data.get("phone") or ""

        attachment = self.cleaned_data.get("attachment")
        if attachment is not None and getattr(attachment, "name", None):
            # Display only: the file is stored under a generated UUID name (see
            # apps.core.validators). The basename is taken because the
            # browser-supplied name is attacker-controlled and may carry a path.
            submission.attachment_original_name = PurePosixPath(str(attachment.name)).name[:255]

        if commit:
            submission.save()
        return submission
