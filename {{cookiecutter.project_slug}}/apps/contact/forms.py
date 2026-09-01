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

The split-phone UI (a country-code select plus a national number) is here rather
than in the template because the two halves have to be recombined and validated
together. In the project this template is derived from that recombination was
copy-pasted into four forms, and the four copies had drifted into four slightly
different validators.
"""

from pathlib import PurePosixPath

import phonenumbers
from django import forms
from django.utils.translation import gettext_lazy as _

{% if cookiecutter.countries_app == "yes" -%}
from apps.cities.models import Country
{% endif -%}
from apps.contact.models import ContactSubmission
{%- if cookiecutter.spam_protection != "none" %}
from apps.core.spam import SpamProtectedForm
{%- endif %}

PHONE_INVALID_MESSAGE = _("Enter a valid phone number, for example 22345678.")

#: Field names this form declares itself. Anything else on the form was injected
#: by a mixin (the honeypot), and the template renders those generically so it
#: never has to hard-code a honeypot's name - which would defeat the point of
#: being able to rename it per project.
DECLARED_FIELDS = (
    "full_name",
    "company_name",
    "email",
{%- if cookiecutter.countries_app == "yes" %}
    "country",
{%- endif %}
    "country_code",
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

    # Not model fields: `phone` is one column, and the visitor fills in two
    # inputs. clean() recombines them and stores E.164 in cleaned_data["phone"].
{%- if cookiecutter.countries_app == "yes" %}
    # A real ChoiceField rather than a template loop over countries, so a dial
    # code the visitor invented is rejected server-side instead of being
    # concatenated into an unparseable number. Choices are filled in __init__.
    country_code = forms.ChoiceField(
        label=_("Country code"),
        required=False,
        choices=[],
    )
{%- else %}
    # No countries app in this project, so the dial code is typed rather than
    # chosen. clean() still requires the result to parse as a real number.
    country_code = forms.CharField(
        label=_("Country code"),
        required=False,
        max_length=6,
        widget=forms.TextInput(attrs={"placeholder": "+965", "inputmode": "tel"}),
    )
{%- endif %}
    mobile_no = forms.CharField(
        label=_("Phone number"),
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "tel-national"}),
    )

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
{%- if cookiecutter.countries_app == "yes" %}
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
{%- if cookiecutter.countries_app == "yes" %}
        # One definition of "a country a visitor may pick", for both selects.
        # Copy-pasting this filter is what produced two disagreeing country lists
        # in the project this template is derived from.
        self.fields["country"].queryset = Country.objects.selectable()
        self.fields["country"].empty_label = _("Select a country")
        self.fields["country"].error_messages.update(
            {
                "required": _("Please select your country."),
                "invalid_choice": _("Select a country from the list."),
            }
        )
        self.phone_countries = list(Country.objects.with_phone_code())
        self.fields["country_code"].choices = [("", _("Code"))] + [
            (country.phone_code, f"{country.localized_name} ({country.phone_code})")
            for country in self.phone_countries
        ]
{%- else %}
        self.phone_countries = []
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
        # Spaces, dashes and brackets are how people write phone numbers; strip
        # them rather than rejecting a correct number typed in a normal way.
        digits = "".join(character for character in value if character.isdigit())
        if value and not digits:
            raise forms.ValidationError(PHONE_INVALID_MESSAGE, code="invalid")
        return digits

    def clean(self):
        cleaned_data = super().clean()
        number = cleaned_data.get("mobile_no") or ""
        code = (cleaned_data.get("country_code") or "").strip()

        if not number:
            # Phone is optional. A country code alone is not a phone number.
            cleaned_data["phone"] = ""
            return cleaned_data

        if not code:
            self.add_error("country_code", _("Please choose the country code."))
            return cleaned_data

        try:
            # Region None forces the string to carry its own +CC, which is why the
            # select's values are "+965"-shaped rather than "965".
            parsed = phonenumbers.parse(f"{code}{number}", None)
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
