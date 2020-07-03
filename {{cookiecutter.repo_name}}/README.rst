===============================
{{ cookiecutter.project_name }}
===============================

.. image:: https://badge.fury.io/py/{{ cookiecutter.repo_name }}.png
    :target: http://badge.fury.io/py/{{ cookiecutter.repo_name }}

.. image:: https://pypip.in/d/{{ cookiecutter.repo_name }}/badge.png
    :target: https://crate.io/packages/{{ cookiecutter.repo_name }}?version=latest


{{ cookiecutter.description }}

* Free software: BSD license

Requirements
------------

* Django 2.2+
* Python 3.6+

Installation
----------------------------

#. Clone the git repository.
#. Please check `Settings`_ section for configurations

#. Install all third party packages by running::

    $ pip install -r requirements.txt

#. Apply migrations::

    $ python manage.py migrate


Settings
========

This project relies extensively on environment settings.

For configuration purposes, the following table maps environment variables to their Django setting and project settings:


======================================= =========================== ============================================== ======================================================================
Environment Variable                    Django Setting              Development Default                            Production Default
======================================= =========================== ============================================== ======================================================================
DJANGO_READ_DOT_ENV_FILE                READ_DOT_ENV_FILE           False                                          False
======================================= =========================== ============================================== ======================================================================


======================================= =========================== ============================================== ======================================================================
Environment Variable                    Django Setting              Development Default                            Production Default
======================================= =========================== ============================================== ======================================================================
DATABASE_URL                            DATABASES                   raises error                                   raises error
DJANGO_ADMIN_URL                        n/a                         'admin/'                                       raises error
DJANGO_DEBUG                            DEBUG                       True                                           False
DJANGO_SECRET_KEY                       SECRET_KEY                  auto-generated                                 raises error
DJANGO_SECURE_BROWSER_XSS_FILTER        SECURE_BROWSER_XSS_FILTER   n/a                                            True
DJANGO_SECURE_SSL_REDIRECT              SECURE_SSL_REDIRECT         n/a                                            True
DJANGO_SECURE_CONTENT_TYPE_NOSNIFF      SECURE_CONTENT_TYPE_NOSNIFF n/a                                            True
DJANGO_SECURE_FRAME_DENY                SECURE_FRAME_DENY           n/a                                            True
DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS   HSTS_INCLUDE_SUBDOMAINS     n/a                                            True
DJANGO_SESSION_COOKIE_HTTPONLY          SESSION_COOKIE_HTTPONLY     n/a                                            True
DJANGO_SESSION_COOKIE_SECURE            SESSION_COOKIE_SECURE       n/a                                            False
DJANGO_DEFAULT_FROM_EMAIL               DEFAULT_FROM_EMAIL          n/a                                            "your_project_name <noreply@your_domain_name>"
DJANGO_SERVER_EMAIL                     SERVER_EMAIL                n/a                                            "your_project_name <noreply@your_domain_name>"
DJANGO_EMAIL_SUBJECT_PREFIX             EMAIL_SUBJECT_PREFIX        n/a                                            "[your_project_name] "
DJANGO_ALLOWED_HOSTS                    ALLOWED_HOSTS               ['*']                                          ['your_domain_name']
======================================= =========================== ============================================== ======================================================================

The following table lists settings and their defaults for third-party applications, which may or may not be part of your project:

======================================= =========================== ============================================== ======================================================================
Environment Variable                    Django Setting              Development Default                            Production Default
======================================= =========================== ============================================== ======================================================================
DJANGO_AWS_ACCESS_KEY_ID                AWS_ACCESS_KEY_ID           n/a                                            raises error
DJANGO_AWS_SECRET_ACCESS_KEY            AWS_SECRET_ACCESS_KEY       n/a                                            raises error
DJANGO_AWS_STORAGE_BUCKET_NAME          AWS_STORAGE_BUCKET_NAME     n/a                                            raises error
DJANGO_AWS_S3_REGION_NAME               AWS_S3_REGION_NAME          n/a                                            None
DJANGO_AWS_S3_CUSTOM_DOMAIN             AWS_S3_CUSTOM_DOMAIN        n/a                                            None
SENTRY_DSN                              SENTRY_DSN                  n/a                                            raises error
======================================= =========================== ============================================== ======================================================================
