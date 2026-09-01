{%- if cookiecutter.task_queue == "celery" %}
# Importing the Celery application here is what makes shared_task bind to it. Without
# this import a task declared with @shared_task is registered against whichever app
# happens to exist first, and in a Django process that is usually none at all.
from .celery import app as celery_app

__all__ = ("celery_app",)
{%- endif %}
