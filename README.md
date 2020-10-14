Django with Cookiecutter
============================

A `Cookiecutter`_ template for `django`_ to deliver your website with a strong Django backend.

Features
--------

* Select CMS package from django-cms or wagtail
* django compressor included
* Amazon S3 for static files

Installation and usage
----------------------

First, get cookiecutter

    $ pip install cookiecutter

Now run it against this repo

    $ cookiecutter https://github.com/KuwaitNET/kn-django-cookiecutter

You'll be prompted for some questions.
After project generation, you'll find a README.rst in which you'll find all information to sync your database with fake migrations. Before your first commit remember to change (if required) the ``LICENSE`` file.
