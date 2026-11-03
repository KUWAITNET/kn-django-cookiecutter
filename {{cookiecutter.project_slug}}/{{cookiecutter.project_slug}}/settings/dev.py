"""Development settings."""

from .base import *  # noqa: F403

DEBUG = True

SECRET_KEY = env("SECRET_KEY", default="django-insecure-dev-key-not-for-production")  # noqa: F405

ALLOWED_HOSTS = ["*"]

# django-debug-toolbar is a dev dependency; tolerate its absence.
try:
    import debug_toolbar  # noqa: F401

    INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
    MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")  # noqa: F405
    INTERNAL_IPS = ["127.0.0.1"]
except ImportError:
    pass

# EMAIL_BACKEND stays post_office's (set in base.py); only the transport it wraps
# changes, to a local SMTP catcher such as Mailpit on port 1025.
POST_OFFICE["BACKENDS"]["default"] = env(  # noqa: F405
    "DEV_EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)

{% if cookiecutter.rate_limiting == "yes" %}
# Lockouts are a nuisance in development; keep them on but generous.
AXES_FAILURE_LIMIT = env.int("AXES_FAILURE_LIMIT", default=20)  # noqa: F405
{% endif %}
try:
    from .local import *  # noqa: F403
except ImportError:
    pass
