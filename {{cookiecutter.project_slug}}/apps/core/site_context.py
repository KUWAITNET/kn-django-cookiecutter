"""Request-scoped "which site is being edited" context.

Chooser widgets are singletons, built once when their owning block or StreamField
is defined, and ``Widget.render()`` never receives the page being edited - so a
chooser has no ordinary way to know which site the current page belongs to.
``apps.core.wagtail_hooks`` stashes it here from the ``before_edit_page`` /
``before_create_page`` hooks, early in the same request that renders the admin
form; chooser widgets read it back later in that same request.

A ``ContextVar`` rather than a module global: it is per task, so nothing leaks
between concurrent requests or tabs, and nothing survives the request.
"""

import contextvars

current_editing_site = contextvars.ContextVar("current_editing_site", default=None)
