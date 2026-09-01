"""Built-in copy for every notification, per recipient type and per language.

This is the file to open when someone asks "what does that e-mail say?". It also
backs the admin's per-field "Reset to default", so the copy an editor can restore
is always the copy the project shipped with - there is no second hard-coded
string anywhere.

Keys are plain strings rather than ``NotificationTrigger``/``RecipientType``
members on purpose: ``models`` imports this module, so importing the enums back
would be a circular import (the reference implementation worked around it with a
mid-module import that reads like a mistake). ``test_defaults`` asserts the two
stay in step.

Bodies are HTML fragments, rendered as Django templates against a per-send
context and dropped into the branded shell from ``apps.core.emails``. A trigger's
context usually carries more keys than the copy below uses - that is the point:
an editor can add a placeholder from the admin with no code change.
"""

from django.conf import settings

DEFAULTS: dict[tuple[str, str], dict[str, dict[str, str]]] = {
    ("contact_submission", "admin"): {
        "en": {
{%- raw %}
            "subject": "New enquiry from {{ name }}",
            "body": (
                "<p>A new enquiry has been submitted on {{ site_name }}.</p>\n"
                "<p><strong>Name:</strong> {{ name }}<br/>\n"
                "<strong>E-mail:</strong> {{ email }}"
                "{% if phone %}<br/>\n<strong>Phone:</strong> {{ phone }}{% endif %}"
                "{% if country %}<br/>\n<strong>Country:</strong> {{ country }}{% endif %}"
                "</p>\n"
                "{% if subject %}<p><strong>Subject:</strong> {{ subject }}</p>\n{% endif %}"
                "<p>{{ message|linebreaksbr }}</p>\n"
                "{% if admin_url %}"
                '<p><a href="{{ admin_url }}">Open this submission in the admin</a></p>'
                "{% endif %}"
            ),
{%- endraw %}
        },
{%- if cookiecutter.languages == "en_ar" %}
        "ar": {
{%- raw %}
            "subject": "استفسار جديد من {{ name }}",
            "body": (
                "<p>تم إرسال استفسار جديد عبر {{ site_name }}.</p>\n"
                "<p><strong>الاسم:</strong> {{ name }}<br/>\n"
                "<strong>البريد الإلكتروني:</strong> {{ email }}"
                "{% if phone %}<br/>\n<strong>الهاتف:</strong> {{ phone }}{% endif %}"
                "{% if country %}<br/>\n<strong>الدولة:</strong> {{ country }}{% endif %}"
                "</p>\n"
                "{% if subject %}<p><strong>الموضوع:</strong> {{ subject }}</p>\n{% endif %}"
                "<p>{{ message|linebreaksbr }}</p>\n"
                "{% if admin_url %}"
                '<p><a href="{{ admin_url }}">عرض الطلب في لوحة التحكم</a></p>'
                "{% endif %}"
            ),
{%- endraw %}
        },
{%- endif %}
    },
{%- if cookiecutter.newsletter == "yes" %}
    ("newsletter_subscription", "user"): {
        "en": {
{%- raw %}
            "subject": "Confirm your newsletter subscription",
            "body": (
                "<p>Hello,</p>\n"
                "<p>{{ email }} was used to subscribe to the {{ site_name }} "
                "newsletter.</p>\n"
                '<p><a href="{{ confirm_url }}">Confirm the subscription</a></p>\n'
                "<p>If this was not you, ignore this message. Nothing will be sent "
                "unless the link above is used.</p>"
            ),
{%- endraw %}
        },
{%- if cookiecutter.languages == "en_ar" %}
        "ar": {
{%- raw %}
            "subject": "تأكيد الاشتراك في النشرة البريدية",
            "body": (
                "<p>مرحباً،</p>\n"
                "<p>تم استخدام {{ email }} للاشتراك في النشرة البريدية لـ "
                "{{ site_name }}.</p>\n"
                '<p><a href="{{ confirm_url }}">تأكيد الاشتراك</a></p>\n'
                "<p>إذا لم تكن أنت من قام بذلك، تجاهل هذه الرسالة. لن نرسل لك شيئاً "
                "ما لم يُستخدم الرابط أعلاه.</p>"
            ),
{%- endraw %}
        },
{%- endif %}
    },
{%- endif %}
}


def get_default(trigger: str, recipient_type: str, language: str, field: str) -> str:
    """The built-in value of ``field`` for one template in ``language``.

    Falls back to ``LANGUAGE_CODE`` when a language has no copy of its own, and
    to an empty string for an unknown key - a missing default must never be the
    reason a send raises.
    """
    per_language = DEFAULTS.get((str(trigger), str(recipient_type)), {})
    entry = per_language.get(language) or per_language.get(settings.LANGUAGE_CODE) or {}
    return entry.get(field, "")
