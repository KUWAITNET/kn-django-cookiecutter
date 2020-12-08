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


Docker Instructions
-------------------

To start this application in docker

1. create a `.env.dev` in the parent directory (next to Dockerfile) with these variables

    DEBUG=1
    SECRET_KEY=foo
    DJANGO_ALLOWED_HOSTS=localhost 127.0.0.1 [::1]
    SQL_ENGINE=django.db.backends.mysql
    SQL_DATABASE=hello_django
    SQL_USER=hello_django
    SQL_PASSWORD=hello_django
    SQL_HOST=db


2. Execute

    `docker-compose up --build` (add `-d` to make run in the background)

    You'll need to run this command each time you change something in the env or in the code.

    For first time run, you'd need to execute these commands too

        `docker-compose exec web python {{ cookiecutter.project_name}}/manage.py migrate`

        `docker-compose exec web python {{ cookiecutter.project_name}}/manage.py createsuperuser`

3. For logs, use this command

    `docker-compose logs -f`

4. To Finish The docker session

     `docker-compose down`

5. To reclaim space and remove dangling images
    
    `docker image prune`
   
   You can check here https://www.digitalocean.com/community/tutorials/how-to-remove-docker-images-containers-and-volumes for other options
   
6. settings file used is `docker.py` in {{ cookiecutter.project_name}}/{{ cookiecutter.project_name}}/settings/.
   You can edit it as you want 