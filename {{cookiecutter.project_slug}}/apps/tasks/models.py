{%- if cookiecutter.task_queue == "huey" and cookiecutter.huey_backend == "postgres" -%}
"""This app has no models, and the empty module is load-bearing.

Django only sends ``post_migrate`` for apps whose ``models`` module exists - it
skips any app config whose ``models_module`` is None. apps/tasks/apps.py uses that
signal to create huey's queue tables, so deleting this file would not remove dead
code, it would stop the queue tables from ever being created and the worker would
fail on its first dequeue.
"""
{%- else -%}
"""This app has no models: the queue's own state lives {% if cookiecutter.task_queue == "huey" %}in its storage backend{% else %}on the broker{% endif %}.

The module exists because Django's app loading expects it, and because an app that
grows its first model should not have to be restructured to hold it.
"""
{%- endif %}
