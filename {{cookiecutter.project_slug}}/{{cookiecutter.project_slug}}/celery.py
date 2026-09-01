"""The Celery application.

Imported from ``{{ cookiecutter.project_slug }}/__init__.py`` so that ``app`` exists
before any module tries to declare a task, and so ``celery -A {{ cookiecutter.project_slug }}``
finds it.

Configuration is not repeated here: ``config_from_object`` reads the Django settings
module with the ``CELERY_`` prefix, so ``CELERY_TASK_ACKS_LATE`` in settings becomes
``task_acks_late`` here and there is exactly one place to look.
"""

import os

from celery import Celery

# The worker is started by a process manager, not by manage.py, so it has no
# default settings module of its own. Production is the right default for a process
# that only ever runs on a server; a developer overrides it in the environment.
os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", "{{ cookiecutter.project_slug }}.settings.production"
)

app = Celery("{{ cookiecutter.project_slug }}")
app.config_from_object("django.conf:settings", namespace="CELERY")

# Imports tasks.py from every installed app. Task modules are therefore discovered
# by convention: a task that lives anywhere else is invisible to the worker, which
# is the single most common reason a task "never runs".
app.autodiscover_tasks()
