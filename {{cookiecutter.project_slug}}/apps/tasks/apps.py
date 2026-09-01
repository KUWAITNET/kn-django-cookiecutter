"""Application configuration for the background-task app."""

from django.apps import AppConfig
{%- if cookiecutter.task_queue == "huey" and cookiecutter.huey_backend == "postgres" %}
from django.db.models.signals import post_migrate


def create_queue_tables(sender, **kwargs):
    """Create huey's own tables as part of 'manage.py migrate'.

    They are not Django models, so no migration describes them. Huey would create
    them on import instead, but that would open a database connection while the
    settings module is being read - and then 'manage.py check' could not run without
    a database, which is exactly what CI does.

    The DDL comes from huey and is executed on DJANGO's connection rather than one
    of huey's own. That matters twice over: the tables land in whatever database
    this migrate is actually running against (a test database included), and the
    tables are created even when the queue is in immediate mode, where huey's own
    storage is an in-memory object with no schema at all.
    """
    from django.conf import settings
    from django.db import connections
    from huey.storage import PostgresStorage

    # Never connects: create_tables=False, and nothing here touches storage.conn.
    # It is constructed only to ask huey what its schema is.
    connection_settings = settings.HUEY.get("connection", {})
    storage = PostgresStorage(
        name=settings.HUEY.get("name", "huey"),
        table_prefix=connection_settings.get("table_prefix", "huey"),
        create_tables=False,
    )

    with connections[kwargs.get("using", "default")].cursor() as cursor:
        for statement in storage.ddl:
            cursor.execute(statement)
{%- endif %}


class TasksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tasks"
    label = "tasks"
    verbose_name = "Background tasks"

    def ready(self):
        # Importing the module is what registers the system checks.
        from apps.tasks import checks  # noqa: F401
{%- if cookiecutter.task_queue == "huey" and cookiecutter.huey_backend == "postgres" %}

        post_migrate.connect(create_queue_tables, sender=self)
{%- endif %}
