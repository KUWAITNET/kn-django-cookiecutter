import logging

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

from .base import *  # noqa: F403
from .base import env

# SECURITY
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-proxy-ssl-header
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-ssl-redirect
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
# https://docs.djangoproject.com/en/dev/ref/settings/#session-cookie-secure
SESSION_COOKIE_SECURE = True
# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-cookie-secure
CSRF_COOKIE_SECURE = True
# https://docs.djangoproject.com/en/dev/topics/security/#ssl-https
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-hsts-seconds
# TODO: set this to 60 seconds first and then to 518400 once you prove the former works
SECURE_HSTS_SECONDS = 60
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-hsts-include-subdomains
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True,
)
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-hsts-preload
SECURE_HSTS_PRELOAD = env.bool("DJANGO_SECURE_HSTS_PRELOAD", default=True)
# https://docs.djangoproject.com/en/dev/ref/middleware/#x-content-type-options-nosniff
SECURE_CONTENT_TYPE_NOSNIFF = env.bool(
    "DJANGO_SECURE_CONTENT_TYPE_NOSNIFF", default=True,
)

SENTRY_LOG_LEVEL = env.int("DJANGO_SENTRY_LOG_LEVEL", logging.ERROR)
sentry_logging = LoggingIntegration(
    level=SENTRY_LOG_LEVEL,  # Capture info and above as breadcrumbs
    event_level=logging.ERROR,  # Send errors as events
)
sentry_sdk.init(
    dsn=SENTRY_DSN,
    integrations=[sentry_logging, DjangoIntegration()],
    send_default_pii=True,
)

ENABLE_APM = env.bool("ENABLE_APM", default=True)
if ENABLE_APM:
    ELASTIC_APM_IP = env.str("ELASTIC_APM_IP", default="")
    INSTALLED_APPS.append("elasticapm.contrib.django")  # noqa: F405
    MIDDLEWARE.insert(0, "elasticapm.contrib.django.middleware.TracingMiddleware")  # noqa: F405
    ELASTIC_APM = {
        "SERVICE_NAME": PROJECT_NAME,  # noqa: F405
        "SERVER_URL": ELASTIC_APM_IP,
        "DJANGO_TRANSACTION_NAME_FROM_ROUTE": True,
    }

{% if cookiecutter.s3 == "y" or cookiecutter.s3 == "Y" %}

# Honor the "X-Forwarded-Proto" header for request.is_secure()
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

USE_S3 = env.bool("USE_S3", default=True)
if USE_S3:
    # Static files location
    AWS_ACCESS_KEY_ID = env.str("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = env.str("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = env.str("AWS_STORAGE_BUCKET_NAME")
    AWS_AUTO_CREATE_BUCKET = True
    AWS_QUERYSTRING_AUTH = False
    AWS_IS_GZIPPED = True

    S3_URL = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/"

    # Static on S3
    STATICFILES_LOCATION = "static"
    STATICFILES_STORAGE = "utils.storages.StaticRootS3Boto3Storage"
    STATIC_URL = f"{S3_URL}{STATICFILES_LOCATION}/"

    COMPRESS_STORAGE = STATICFILES_STORAGE
    COMPRESS_URL = STATIC_URL

    # Media on S3
    MEDIAFILES_LOCATION = "media"
    MEDIA_URL = f"{S3_URL}{MEDIAFILES_LOCATION}/"
    DEFAULT_FILE_STORAGE = "utils.storages.MediaRootS3Boto3Storage"

    AWS_QUERYSTRING_AUTH = False
    _AWS_EXPIRY = 60 * 60 * 24 * 7
    AWS_S3_OBJECT_PARAMETERS = {
        "CacheControl": f"max-age={_AWS_EXPIRY}, s-maxage={_AWS_EXPIRY}, must-revalidate"  # noqa: COM812
    }
{% endif %}
