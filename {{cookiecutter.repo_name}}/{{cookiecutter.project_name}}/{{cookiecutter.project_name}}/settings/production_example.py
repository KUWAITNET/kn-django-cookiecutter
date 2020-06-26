from .base import *

ALLOWED_HOSTS = [
    '{{ cookiecutter.domain_name }}',
]

DATABASES = {
    'default': {
        'CONN_MAX_AGE': 0,
        'ENGINE': 'django.db.backends.',  # Add 'postgresql_psycopg2', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': '',                       # Or path to database file if using sqlite3.
        'USER': '',
        'PASSWORD': '',
        'HOST': '',                       # Empty for localhost through domain sockets or '127.0.0.1' for localhost through TCP.
        'PORT': '',                       # Set to empty string for default.
    }
}

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = ''
EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''
EMAIL_USE_TLS = False
EMAIL_PORT = 25
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER


{% if cookiecutter.s3 == "y" or cookiecutter.s3 == "Y" %}

# Honor the 'X-Forwarded-Proto' header for request.is_secure()
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Static files location
AWS_ACCESS_KEY_ID = environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = environ.get('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = environ.get('AWS_STORAGE_BUCKET_NAME')
AWS_AUTO_CREATE_BUCKET = True
AWS_QUERYSTRING_AUTH = False
AWS_IS_GZIPPED = True

S3_URL = 'https://%s.s3.amazonaws.com/' % AWS_STORAGE_BUCKET_NAME

# Static on S3
STATICFILES_LOCATION = 'static'
STATICFILES_STORAGE = '{{ cookiecutter.project_name }}.utils.storages.StaticRootS3Boto3Storage'
STATIC_URL = "%s%s/" % (S3_URL, STATICFILES_LOCATION)

COMPRESS_STORAGE = STATICFILES_STORAGE
COMPRESS_URL = STATIC_URL

# Media on S3
MEDIAFILES_LOCATION = 'media'
MEDIA_URL = "%s%s/" % (S3_URL, MEDIAFILES_LOCATION)
DEFAULT_FILE_STORAGE = '{{ cookiecutter.project_name }}.utils.storages.MediaRootS3Boto3Storage'

AWS_QUERYSTRING_AUTH = False
AWS_HEADERS = {
    'Cache-Control': 'max-age=86400',
}
{% endif %}

