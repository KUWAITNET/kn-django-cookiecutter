"""Production settings.

Secrets have NO defaults here: a misconfigured deploy must fail loudly at boot
rather than silently run with a development key.
"""

from .base import *  # noqa: F403

DEBUG = False

SECRET_KEY = env("SECRET_KEY")  # noqa: F405
ALLOWED_HOSTS = env("ALLOWED_HOSTS")  # noqa: F405

# Transport security. Assumes TLS terminates upstream; the proxy MUST strip any
# client-supplied X-Forwarded-Proto, otherwise this header is spoofable.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)  # noqa: F405
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=2592000)  # noqa: F405
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(  # noqa: F405
    "SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True
)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=True)  # noqa: F405

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

CSRF_TRUSTED_ORIGINS = env.list(  # noqa: F405
    "CSRF_TRUSTED_ORIGINS", default=["https://{{ cookiecutter.domain_name }}"]
)
{% if cookiecutter.api != "none" %}
# The schema UI is available on staging and gated in production.
API_DOCS_ENABLED = env.bool("API_DOCS_ENABLED", default=False)  # noqa: F405
{% endif %}
try:
    from .local import *  # noqa: F403
except ImportError:
    pass
