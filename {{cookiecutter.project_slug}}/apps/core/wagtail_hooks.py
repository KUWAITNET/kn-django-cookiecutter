"""Front-end and admin hooks.

``insert_global_admin_css`` fires on every admin page, including login and error
pages, so it is the right place for global restyling - no template override.
"""

from django.utils.html import format_html
from wagtail import hooks
from wagtail.admin.staticfiles import versioned_static
{%- if cookiecutter.multisite == "multi" %}

from apps.core.site_context import current_editing_site
{%- endif %}


@hooks.register("before_serve_page")
def stash_served_page(page, request, args, kwargs):
    """Make the page being served visible outside the view.

    Context processors receive only the request, so without this the shared head
    partial has no way to build ``hreflang`` alternates or a language switcher
    that follows translated slugs. This is the one seam Wagtail offers that runs
    before ``serve()`` on every page request.
    """
    request.wagtail_page = page
{%- if cookiecutter.multisite == "multi" %}


@hooks.register("before_edit_page")
def stash_editing_site_on_edit(request, page):
    """Record the page's site so site-filtered choosers can read it back.

    See apps.core.site_context for why this indirection exists.
    """
    current_editing_site.set(page.get_site())


@hooks.register("before_create_page")
def stash_editing_site_on_create(request, parent_page, page_class):
    current_editing_site.set(parent_page.get_site())
{%- endif %}


@hooks.register("insert_global_admin_css")
def admin_branding_css():
    # versioned_static, not static: admin assets are cache-busted the way the rest
    # of the admin's own assets are.
    return format_html(
        '<link rel="stylesheet" href="{}">', versioned_static("css/admin-branding.css")
    )


@hooks.register("construct_main_menu")
def hide_unused_main_menu_items(request, menu_items):
    """Remove menu entries this project does not use.

    Clients read the sidebar as the list of things they are meant to do, so an
    entry that leads nowhere useful is a support ticket waiting to happen.
    """
    hidden = {"help"}
    menu_items[:] = [item for item in menu_items if item.name not in hidden]


@hooks.register("construct_settings_menu")
def hide_styleguide_settings_item(request, menu_items):
    menu_items[:] = [item for item in menu_items if item.name != "styleguide"]
