import os
import shutil

cwd = os.getcwd()
project_root = os.path.join(cwd, "{{cookiecutter.project_name}}")
templates = os.path.join(project_root, "templates")

if "{{cookiecutter.cms_package}}" == "django-cms":
    shutil.rmtree(os.path.join(project_root, "home"))
    shutil.rmtree(os.path.join(project_root, "search"))

    os.remove(os.path.join(templates, "wagtail_base.html"))
    os.remove(os.path.join(templates, "none_base.html"))

    shutil.move(os.path.join(templates, "cms_base.html"), 
                os.path.join(templates, "base.html"))

if "{{cookiecutter.cms_package}}" == "wagtail":
    os.remove(os.path.join(templates, "menu.html"))
    os.remove(os.path.join(templates, "single_page.html"))
    os.remove(os.path.join(templates, "cms_base.html"))
    os.remove(os.path.join(templates, "none_base.html"))

    shutil.move(os.path.join(templates, "wagtail_base.html"), 
                            os.path.join(templates, "base.html"))

if "{{cookiecutter.cms_package}}" == "None":
    shutil.rmtree(os.path.join(project_root, "home"))
    shutil.rmtree(os.path.join(project_root, "search"))

    os.remove(os.path.join(templates, "menu.html"))
    os.remove(os.path.join(templates, "single_page.html"))
    os.remove(os.path.join(templates, "cms_base.html"))
    os.remove(os.path.join(templates, "wagtail_base.html"))

    shutil.move(os.path.join(templates, "none_base.html"), 
                            os.path.join(templates, "base.html"))