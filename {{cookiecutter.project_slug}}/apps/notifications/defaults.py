"""Built-in copy for every notification, per trigger and per language.

This is the file to open when someone asks "what does that e-mail say?". It is
also the source of the admin's per-field "Reset to default" action, so the copy
an editor can restore is always the copy the project shipped with - there is no
second hard-coded string anywhere.

Keys are plain strings rather than ``NotificationTrigger`` members on purpose:
``models`` imports this module, so importing the enum back would be a circular
import (the reference implementation worked around it with a mid-module import
that reads like a mistake). ``test_defaults`` asserts the two stay in step.

Bodies are Django template source, rendered as **plain text** against a
per-send context. A trigger's context may carry more keys than the copy below
uses - that is the point: an editor can add a placeholder from the admin
without a code change.
"""

from django.conf import settings

DEFAULTS: dict[str, dict[str, dict[str, str]]] = {
    "contact_enquiry_admin": {
        "en": {
{%- raw %}
            "subject": "New enquiry from {{ name }}",
            "body": (
                "A new enquiry has been submitted on {{ site_name }}.\n"
                "\n"
                "Name: {{ name }}\n"
                "E-mail: {{ email }}\n"
                "{% if phone %}Phone: {{ phone }}\n{% endif %}"
                "\n"
                "Message:\n"
                "{{ message }}\n"
                "{% if admin_url %}\nOpen it in the admin: {{ admin_url }}\n{% endif %}"
            ),
{%- endraw %}
        },
{%- if cookiecutter.languages == "en_ar" %}
        "ar": {
{%- raw %}
            "subject": "استفسار جديد من {{ name }}",
            "body": (
                "تم إرسال استفسار جديد عبر {{ site_name }}.\n"
                "\n"
                "الاسم: {{ name }}\n"
                "البريد الإلكتروني: {{ email }}\n"
                "{% if phone %}الهاتف: {{ phone }}\n{% endif %}"
                "\n"
                "الرسالة:\n"
                "{{ message }}\n"
                "{% if admin_url %}\nعرض الاستفسار في لوحة التحكم: {{ admin_url }}\n{% endif %}"
            ),
{%- endraw %}
        },
{%- endif %}
    },
    "contact_enquiry_user": {
        "en": {
{%- raw %}
            "subject": "We have received your enquiry",
            "body": (
                "Hello {{ name }},\n"
                "\n"
                "Thank you for contacting {{ site_name }}. We have received your message "
                "and will reply as soon as we can.\n"
                "\n"
                "This is what you sent us:\n"
                "\n"
                "{{ message }}\n"
                "\n"
                "Kind regards,\n"
                "{{ site_name }}\n"
            ),
{%- endraw %}
        },
{%- if cookiecutter.languages == "en_ar" %}
        "ar": {
{%- raw %}
            "subject": "لقد استلمنا استفسارك",
            "body": (
                "مرحباً {{ name }}،\n"
                "\n"
                "شكراً لتواصلك مع {{ site_name }}. لقد استلمنا رسالتك وسنرد عليك في أقرب وقت.\n"
                "\n"
                "نص رسالتك:\n"
                "\n"
                "{{ message }}\n"
                "\n"
                "مع أطيب التحيات،\n"
                "{{ site_name }}\n"
            ),
{%- endraw %}
        },
{%- endif %}
    },
{%- if cookiecutter.newsletter == "yes" %}
    "newsletter_subscribed": {
        "en": {
{%- raw %}
            "subject": "Confirm your newsletter subscription",
            "body": (
                "Hello,\n"
                "\n"
                "{{ email }} was used to subscribe to the {{ site_name }} newsletter.\n"
                "\n"
                "Confirm the subscription:\n"
                "{{ confirm_url }}\n"
                "\n"
                "If this was not you, ignore this message. Nothing will be sent unless "
                "the link above is used.\n"
            ),
{%- endraw %}
        },
{%- if cookiecutter.languages == "en_ar" %}
        "ar": {
{%- raw %}
            "subject": "تأكيد الاشتراك في النشرة البريدية",
            "body": (
                "مرحباً،\n"
                "\n"
                "تم استخدام {{ email }} للاشتراك في النشرة البريدية لـ {{ site_name }}.\n"
                "\n"
                "لتأكيد الاشتراك:\n"
                "{{ confirm_url }}\n"
                "\n"
                "إذا لم تكن أنت من قام بذلك، تجاهل هذه الرسالة. لن نرسل لك شيئاً ما لم "
                "يُستخدم الرابط أعلاه.\n"
            ),
{%- endraw %}
        },
{%- endif %}
    },
{%- endif %}
}


def get_default(trigger: str, language: str, field: str) -> str:
    """The built-in value of ``field`` for ``trigger`` in ``language``.

    Falls back to ``LANGUAGE_CODE`` when a language has no copy of its own, and
    to an empty string for an unknown trigger - a missing default must never be
    the reason a send raises.
    """
    per_language = DEFAULTS.get(str(trigger), {})
    entry = per_language.get(language) or per_language.get(settings.LANGUAGE_CODE) or {}
    return entry.get(field, "")
