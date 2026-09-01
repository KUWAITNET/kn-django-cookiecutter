"""StreamField blocks for the editor-configurable menus (up to three levels).

The menu is configuration, not code. Everything the client wants in the header or
the footer is edited in Wagtail's Settings section, so restructuring the
navigation never needs a deployment - which is the whole reason these are
settings rather than a page-tree walk.

Three levels are modelled by subclassing rather than recursion: a StreamBlock
cannot refer to itself, and an explicitly bounded depth is also a design
constraint (a fourth level is unusable on a phone).
"""

from django.utils.translation import gettext_lazy as _
from wagtail import blocks


class MenuLinkBlock(blocks.StructBlock):
    """One menu entry: a label plus a destination.

    Unlike a general-purpose link block this deliberately allows a page AND a
    ``url`` together, because for a menu the url field doubles as an in-page
    anchor: "About" plus "#leadership" points at a section of the destination
    page. ``nav_href`` in ``navigation_tags`` resolves the pair.
    """

    label = blocks.CharBlock(required=True, max_length=80, label=_("Label"))
    page = blocks.PageChooserBlock(
        required=False,
        label=_("Page"),
        help_text=_("Preferred: a chosen page keeps working when its slug changes."),
    )
    url = blocks.CharBlock(
        required=False,
        max_length=255,
        label=_("URL or anchor"),
        help_text=_(
            "External URL, absolute path, or an anchor starting with #. An anchor is "
            "appended to the page above; anything else is used only when no page is set."
        ),
    )

    class Meta:
        icon = "link"
        label = _("Link")


class SubMenuItemBlock(MenuLinkBlock):
    """Second level: an entry inside a dropdown, optionally with its own column."""

    children = blocks.ListBlock(
        MenuLinkBlock(),
        required=False,
        collapsed=True,
        label=_("Sub-links"),
    )

    class Meta:
        icon = "link"
        label = _("Dropdown item")


class MenuItemBlock(MenuLinkBlock):
    """Top level: a header entry whose children render as a dropdown."""

    children = blocks.ListBlock(
        SubMenuItemBlock(),
        required=False,
        collapsed=True,
        label=_("Dropdown items"),
    )

    class Meta:
        icon = "list-ul"
        label = _("Menu item")


class MenuStreamBlock(blocks.StreamBlock):
    """The menu itself: an ordered list of top-level items."""

    item = MenuItemBlock()

    class Meta:
        icon = "list-ul"
        collapsed = True
        label = _("Menu")
