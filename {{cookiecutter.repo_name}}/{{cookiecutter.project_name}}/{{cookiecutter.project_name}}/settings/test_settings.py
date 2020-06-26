from .base import *

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

ALLOWED_HOSTS = ['*']

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

SECRET_KEY = 'test'

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
        'LOCATION': ''
    },
    'redis': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}
