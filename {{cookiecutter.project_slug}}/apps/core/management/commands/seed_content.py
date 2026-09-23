"""Seed the minimum content a fresh database needs to be usable.

**Idempotent, and it never deletes content.** Re-running creates what is missing
and leaves everything else exactly as it is - including anything an editor has
changed since the last run. The seeder in the project this template came from
described itself as idempotent while actually rebuilding the page tree on every
run, and it was a documented deploy step; do not reintroduce that.

The rule, applied everywhere below: editor-owned data is created with
``get_or_create`` and never updated. Only infrastructure rows the editor does not
own are force-synced.

Run with ``python manage.py seed_content``. The test suite runs it once per
session (see ``conftest.py``), so keep it fast and keep it small.
"""

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction
{%- if cookiecutter.stack == "wagtail" %}
{%- if cookiecutter.languages == "en_ar" %}
from django.db.models import F
{%- endif %}
from django.utils import translation
from wagtail.models import Page, Site
{%- endif %}
{%- if cookiecutter.languages == "en_ar" %}


def t(en, ar):
    """An (English, Arabic) pair.

    A function rather than a bare tuple purely for readability at the call site:
    ``t("About us", "من نحن")`` says what it is.
    """
    return (en, ar)


def _set_trans(obj, field, value):
    """Write a translated field's base column and every per-language column.

    Setting only the base column leaves ``field_en``/``field_ar`` NULL, and the
    page then renders blank in one language or fails validation outright.
    """
    values = (
        value if isinstance(value, tuple) else (value,) * len(settings.MODELTRANSLATION_LANGUAGES)
    )
    for code, text in zip(settings.MODELTRANSLATION_LANGUAGES, values, strict=False):
        setattr(obj, f"{field}_{code}", text)
    setattr(obj, field, values[0])
{%- else %}


def t(value):
    """A single-language value.

    Kept as a function so seed content reads the same whichever language set the
    project was generated with.
    """
    return value


def _set_trans(obj, field, value):
    setattr(obj, field, value)
{%- endif %}


class Command(BaseCommand):
    help = "Create the baseline content, groups and settings. Safe to run repeatedly."

    @transaction.atomic
    def handle(self, *args, **options):
        self.verbosity = options.get("verbosity", 1)
        self._editor_group()
{%- if cookiecutter.stack == "wagtail" %}
        translation.activate(settings.LANGUAGE_CODE)
{%- if cookiecutter.languages == "en_ar" %}
        self._backfill_translation_fields()
{%- endif %}
        home = self._home_page()
        if home is not None:
            self._default_site(home)
{%- if cookiecutter.newsroom == "yes" %}
            self._newsroom_page(home)
{%- endif %}
{%- endif %}
        self._report(f"Seed complete for {settings.SITE_NAME}.")

    # --- output ---------------------------------------------------------------

    def _report(self, message, created=False):
        if self.verbosity < 1:
            return
        style = self.style.SUCCESS if created else self.style.NOTICE
        self.stdout.write(style(f"  {message}"))

    # --- shared ---------------------------------------------------------------

    def _editor_group(self):
        """A group to hang editor permissions off.

        Created empty on purpose: which permissions an editor needs is a
        per-project decision, and silently granting a set here would make the
        access review meaningless.
        """
        group, created = Group.objects.get_or_create(name="Content editors")
        self._report(
            f"Group 'Content editors' {'created' if created else 'already present'}.", created
        )
        return group
{%- if cookiecutter.stack == "wagtail" %}
{%- if cookiecutter.languages == "en_ar" %}

    def _backfill_translation_fields(self):
        """Fill in the per-language columns on rows the migrations created.

        Wagtail's own initial migration creates the tree root with only the base
        ``title``/``slug`` columns set, and modeltranslation patches ``save()`` to
        validate the per-language ones. treebeard re-saves the *parent* on every
        ``add_child()``, so the first page added under root makes root save itself
        and fail on ``title_en IS NULL``.

        Queryset ``update()`` bypasses ``save()``, which is the only way to write
        these columns without tripping the validation being fixed.
        """
        default = settings.LANGUAGE_CODE
        Page.objects.filter(depth=1).update(
            **{"title": "Root", "slug": "root"},
            **{f"title_{code}": "Root" for code, _ in settings.LANGUAGES},
            **{f"slug_{code}": "root" for code, _ in settings.LANGUAGES},
        )
        for code, _label in settings.LANGUAGES:
            Page.objects.filter(**{f"title_{code}__isnull": True}).update(
                **{f"title_{code}": F("title")}
            )
            Page.objects.filter(**{f"slug_{code}__isnull": True}).update(
                **{f"slug_{code}": F("slug")}
            )
        self._report(f"Translation columns backfilled (default language: {default}).")
{%- endif %}

    def _home_page(self):
        """Create the home page if the site has none yet.

        An existing ``HomePage`` is returned untouched - its content belongs to
        the editors. The only thing ever removed is Wagtail's own scaffold
        "Welcome to your new site" page, and only while it is still childless and
        still a plain ``Page``: it squats on the ``home`` slug that the real home
        page needs.
        """
        try:
            from apps.home.models import HomePage
        except ImportError:
            self._report("apps.home.models.HomePage not found - skipping the page tree.")
            return None

        root = Page.objects.get(depth=1)
        existing = HomePage.objects.first()
        if existing is not None:
            self._report(f"Home page already present: {existing.title}.")
            return existing

        home_page_ids = HomePage.objects.values("id")
        placeholder = root.get_children().filter(slug="home").exclude(id__in=home_page_ids).first()
        if placeholder is not None and not placeholder.get_children().exists():
            Site.objects.filter(root_page=placeholder).delete()
            placeholder.delete()
            # Re-fetch: the delete changed the tree and our in-memory root still
            # holds the old numchild, which treebeard would use to build a
            # colliding path for the next child.
            root = Page.objects.get(depth=1)

        home = HomePage()
        _set_trans(home, "title", t("Home"{% if cookiecutter.languages == "en_ar" %}, "الرئيسية"{% endif %}))
        _set_trans(home, "slug", t("home"{% if cookiecutter.languages == "en_ar" %}, "home"{% endif %}))
        root.add_child(instance=home)
        home.save()
        self._report("Home page created.", created=True)
        return home

    def _default_site(self, home):
        """Point the default site at the home page.

        Infrastructure, not content, so this one *is* force-synced: a site record
        aimed at a deleted page breaks every URL on the install.
        """
        site = Site.objects.filter(is_default_site=True).first()
        if site is None:
            site = Site(hostname="localhost", port=80, is_default_site=True)
        site.root_page = home
        site.site_name = settings.SITE_NAME
        site.save()
        self._report(f"Default site '{site.hostname}' points at the home page.")
{%- if cookiecutter.newsroom == "yes" %}

    def _newsroom_page(self, home):
        """Create the newsroom page under the home page if there is none.

        Articles are models served by this page, so without it they have no
        address at all. An existing newsroom is left exactly as the editors made it.
        """
        from apps.newsroom.models import NewsIndexPage

        if NewsIndexPage.objects.exists():
            return
        newsroom = NewsIndexPage()
        _set_trans(newsroom, "title", t("News"{% if cookiecutter.languages == "en_ar" %}, "الأخبار"{% endif %}))
        _set_trans(newsroom, "slug", t("news"{% if cookiecutter.languages == "en_ar" %}, "news"{% endif %}))
        home.add_child(instance=newsroom)
        newsroom.save_revision().publish()
        self._report("Newsroom page created.", created=True)
{%- endif %}
{%- endif %}
