"""Reusable read-only admin panels.

Submission records are shown, never edited: every field on a submissions viewset
is ``read_only=True``, because an edited submission is no longer evidence of what
someone actually sent. Plain ``FieldPanel(read_only=True)`` renders a bare
``str()`` of the value, which is unreadable for files, rich text, relations and
multi-choice JSON - hence these.
"""

from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from laces.components import Component
from wagtail.admin.panels import FieldPanel
from wagtail.admin.panels.base import Panel
from wagtail.rich_text import expand_db_html


def render_listing_table(headings, rows):
    """Render related rows using the admin's own listing styles.

    ``class="listing small"`` inside a ``.w-overflow-auto`` wrapper is what
    Wagtail's own submissions listing uses, so these small tables match the rest
    of the admin - row dividers, header styling, horizontal scroll on narrow
    screens - without a line of custom CSS.
    """
    head = format_html_join(
        "", '<th style="font-weight:bold">{}</th>', ((heading,) for heading in headings)
    )
    body = format_html_join(
        "",
        "<tr>{}</tr>",
        ((format_html_join("", "<td>{}</td>", ((cell,) for cell in row)),) for row in rows),
    )
    return format_html(
        '<div class="w-overflow-auto">'
        '<table class="listing small" style="margin-bottom:0">'
        "<thead><tr>{}</tr></thead>"
        "<tbody>{}</tbody>"
        "</table>"
        "</div>",
        head,
        body,
    )


class ReadOnlyFileLinkPanel(FieldPanel):
    """Renders a ``FileField`` as a download link instead of a storage path."""

    def format_value_for_display(self, value):
        if not value:
            return "-"
        try:
            filename = value.name.rsplit("/", 1)[-1]
            return format_html(
                '<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>',
                value.url,
                filename,
            )
        except ValueError:
            # Private storage refuses url(); show the stored name only.
            return value.name.rsplit("/", 1)[-1]


class ReadOnlyPageLinkPanel(FieldPanel):
    """Renders a foreign key to a page as a link to that page."""

    def format_value_for_display(self, value):
        if not value:
            return "-"
        try:
            url = value.full_url
        except AttributeError:
            return str(value)
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>', url, str(value)
        )


class ReadOnlyChoiceListPanel(FieldPanel):
    """Renders a JSON list of choice codes as their labels.

    For multi-selects stored in a ``JSONField``, which cannot take ``choices=``
    itself.
    """

    def __init__(self, *args, choices, **kwargs):
        super().__init__(*args, **kwargs)
        self.choices = choices

    def clone_kwargs(self):
        # Any panel taking an extra __init__ kwarg must do this: panels are cloned
        # when bound to a model, and a missing kwarg raises at bind time.
        kwargs = super().clone_kwargs()
        kwargs["choices"] = self.choices
        return kwargs

    def format_value_for_display(self, value):
        if not value:
            return "-"
        labels = dict(self.choices)
        return ", ".join(str(labels.get(code, code)) for code in value)


class ReadOnlyRichTextPanel(FieldPanel):
    """Renders a rich-text field's stored HTML as HTML.

    Read-only ``FieldPanel`` otherwise shows the raw database value as literal
    source. ``expand_db_html`` resolves the editor's internal link and embed
    placeholders exactly as the ``richtext`` filter does.
    """

    def format_value_for_display(self, value):
        if not value:
            return "-"
        return mark_safe(expand_db_html(value))  # noqa: S308  # nosec B308 B703


class ReadOnlyM2MPanel(FieldPanel):
    """Renders a many-to-many manager as a comma-separated list."""

    def format_value_for_display(self, value):
        if hasattr(value, "all"):
            return ", ".join(str(obj) for obj in value.all()) or "-"
        return str(value) if value else "-"


class ReadOnlyComponentPanel(Panel):
    """Displays a read-only ``laces`` component in an edit form.

    The escape hatch for values that are not model fields - a reverse foreign-key
    set, a computed summary. ``FieldPanel`` cannot show those: ``get_field()``
    returns a ``ManyToOneRel``, which has no ``verbose_name``/``formfield``, so
    ``FieldPanel(read_only=True)`` raises while deriving its heading.
    """

    def __init__(self, component_class, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.component_class = component_class

    def clone_kwargs(self):
        kwargs = super().clone_kwargs()
        kwargs["component_class"] = self.component_class
        return kwargs

    class BoundPanel(Panel.BoundPanel):
        template_name = "wagtailadmin/panels/read_only_output.html"
        read_only = True

        def id_for_label(self):
            return self.prefix

        def get_context_data(self, parent_context=None):
            context = super().get_context_data(parent_context)
            context["id_for_label"] = self.id_for_label()
            context["help_text"] = self.help_text
            context["display_value"] = self.panel.component_class(self.instance).render_html()
            return context


def related_rows_component(relation, headings, row_fn):
    """Build a component that renders ``instance.<relation>`` as a listing table.

    Three near-identical hand-written classes for this existed in the reference
    project; one factory replaces them::

        panels = [
            ReadOnlyComponentPanel(
                related_rows_component(
                    "management_contacts",
                    ("Name", "E-mail"),
                    lambda row: (row.name, row.email or "-"),
                ),
                heading="Management contacts",
            ),
        ]
    """

    class RelatedRowsComponent(Component):
        def __init__(self, instance):
            self.rows = list(getattr(instance, relation).all())

        def render_html(self, parent_context=None):
            if not self.rows:
                return "-"
            return render_listing_table(headings, (row_fn(row) for row in self.rows))

    return RelatedRowsComponent
