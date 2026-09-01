#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys


def main():
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE", "{{ cookiecutter.project_slug }}.settings.dev"
    )
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Could not import Django. Is it installed and is the virtual environment "
            "active? Run 'make setup'."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
