"""StreamField block validation.

Cross-field rules on a block are the only place an editor can be stopped from
building something the template cannot render, so they are worth pinning.
"""

import pytest
from wagtail.blocks.struct_block import StructBlockValidationError

from apps.core.blocks import (
    CONTENT_BLOCKS,
    CONTENT_BLOCKS_COUNTS,
    HOME_BLOCKS,
    HOME_BLOCKS_COUNTS,
    ButtonBlock,
    LinkBlock,
    PageOrURLBlock,
    SectionTitleBlock,
)


@pytest.mark.django_db
def test_a_link_cannot_target_both_a_page_and_a_url():
    from wagtail.models import Page

    page = Page.objects.first()
    with pytest.raises(StructBlockValidationError):
        LinkBlock().clean(
            {"label": "About", "page": page, "document": None, "url": "https://example.com"}
        )


@pytest.mark.django_db
def test_a_link_with_exactly_one_target_is_accepted():
    result = LinkBlock().clean(
        {"label": "About", "page": None, "document": None, "url": "https://example.com"}
    )
    assert result["url"] == "https://example.com"


@pytest.mark.django_db
def test_page_or_url_rejects_two_targets():
    from wagtail.models import Page

    page = Page.objects.first()
    with pytest.raises(StructBlockValidationError):
        PageOrURLBlock().clean({"page": page, "url": "/about/"})


def test_a_disabled_section_renders_nothing():
    block = SectionTitleBlock()
    value = block.to_python({"enabled": False, "heading": "Hidden", "subheading": ""})
    # Switching a section off must not require deleting the content in it.
    assert block.render(value) == ""


def test_a_button_declares_download_explicitly():
    # Inferring it from the label text was silently false on every Arabic page.
    assert "download" in ButtonBlock().child_blocks


def test_every_content_block_is_capped():
    names = {name for name, _block in CONTENT_BLOCKS}
    assert names <= set(CONTENT_BLOCKS_COUNTS)
    for name in names:
        assert CONTENT_BLOCKS_COUNTS[name]["max_num"] > 0


def test_the_home_page_can_use_every_content_block():
    # The reference project kept two hand-maintained lists, so a home page could
    # not use a rich-text or CTA block at all.
    home_names = {name for name, _block in HOME_BLOCKS}
    assert {name for name, _block in CONTENT_BLOCKS} <= home_names
    assert "hero_carousel" in home_names
    assert home_names <= set(HOME_BLOCKS_COUNTS)


def test_content_blocks_are_registered_under_stable_names():
    names = [name for name, _block in CONTENT_BLOCKS]
    # Renaming a block type orphans every existing page's stored content.
    assert "rich_text" in names
    assert len(names) == len(set(names))
