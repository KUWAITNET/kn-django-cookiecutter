{% if cookiecutter.stack == "wagtail" -%}
"""The operational configuration singleton and its admin form.

What is worth testing here is not the field list - it is that there is exactly one
row however many times it is asked for, that the admin page an administrator
actually opens renders, and that adding or deleting the row is refused. A
singleton that can be duplicated or removed stops being a singleton the first time
someone clicks the wrong button.
"""

import pytest
from django.contrib import admin
from django.urls import reverse

from apps.core.models import OperationalSettings

pytestmark = pytest.mark.django_db


def test_get_solo_always_returns_the_same_single_row():
    first = OperationalSettings.get_solo()
    second = OperationalSettings.get_solo()

    assert first.pk == second.pk == 1
    assert OperationalSettings.objects.count() == 1


def test_saving_can_never_create_a_second_row():
    OperationalSettings.get_solo()
    # A caller that builds the model by hand and saves it must still land on row 1.
    OperationalSettings(outbound_integrations_enabled=False).save()

    assert OperationalSettings.objects.count() == 1
    assert OperationalSettings.get_solo().outbound_integrations_enabled is False


def test_outbound_integrations_are_enabled_until_someone_turns_them_off():
    # The kill switch defaults to "on": a fresh install must not be silently
    # cut off from the services it is configured to call.
    assert OperationalSettings.get_solo().outbound_integrations_enabled is True


def test_the_alert_address_falls_back_to_the_deployed_default(settings):
    settings.DEFAULT_ADMIN_EMAIL = "ops@example.com"
    configuration = OperationalSettings.get_solo()

    assert configuration.alert_email == "ops@example.com"

    configuration.technical_alert_email = "on-call@example.com"
    assert configuration.alert_email == "on-call@example.com"


def test_the_singleton_is_registered_in_the_django_admin():
    assert admin.site.is_registered(OperationalSettings)


def test_the_admin_page_renders_for_an_administrator(client, admin_user):
    client.force_login(admin_user)

    # No object id: django-solo replaces the changelist route with the change
    # form for row 1, which is the URL the admin index links to.
    response = client.get(reverse("admin:core_operationalsettings_change"))

    assert response.status_code == 200
    # The row is created on first view, so an administrator never meets a 404.
    assert OperationalSettings.objects.count() == 1


def test_the_admin_refuses_to_add_or_delete_the_row(admin_user):
    model_admin = admin.site._registry[OperationalSettings]

    assert model_admin.has_add_permission(None) is False
    assert model_admin.has_delete_permission(None) is False
{%- else -%}
"""The site configuration singleton, its admin form and its effect on the context.

Three things are worth testing here: that there is exactly one row however many
times it is asked for, that the values an administrator sets reach the templates
under the same names the deployed settings use, and that the image fields carry
the same upload validation as every other public-facing file field. A settings
model with unvalidated image fields is a file-upload hole with a nicer form.
"""

import pytest
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.core.context_processors import site_context
from apps.core.models import SiteConfiguration
from apps.core.validators import SecureFileValidator

pytestmark = pytest.mark.django_db


def test_get_solo_always_returns_the_same_single_row():
    first = SiteConfiguration.get_solo()
    second = SiteConfiguration.get_solo()

    assert first.pk == second.pk == 1
    assert SiteConfiguration.objects.count() == 1


def test_saving_can_never_create_a_second_row():
    SiteConfiguration.get_solo()
    # A caller that builds the model by hand and saves it must still land on row 1.
    SiteConfiguration(site_name="Second").save()

    assert SiteConfiguration.objects.count() == 1
    assert SiteConfiguration.get_solo().site_name == "Second"


def test_the_context_prefers_the_configured_site_name(rf, settings):
    settings.SITE_NAME = "Deployed name"
    configuration = SiteConfiguration.get_solo()
    configuration.site_name = "Edited name"
    configuration.save()

    context = site_context(rf.get("/"))

    assert context["SITE_NAME"] == "Edited name"
    assert context["SITE_CONFIG"].pk == configuration.pk


def test_a_blank_field_falls_back_to_the_deployed_setting(rf, settings):
    settings.SITE_NAME = "Deployed name"
    configuration = SiteConfiguration.get_solo()
    configuration.site_name = ""
    configuration.save()

    context = site_context(rf.get("/"))

    # Blank means "use the deployed default", never "render nothing" - an empty
    # <title> is a worse failure than an unedited one.
    assert context["SITE_NAME"] == "Deployed name"
    assert context["DEFAULT_OG_IMAGE_URL"].startswith("http")


def test_only_the_social_profiles_that_are_filled_in_are_listed():
    configuration = SiteConfiguration.get_solo()
    configuration.facebook = "https://facebook.com/example"
    configuration.linkedin = "https://linkedin.com/company/example"
    configuration.save()

    names = [link["name"] for link in configuration.social_links]

    assert names == ["facebook", "linkedin"]
    assert all(link["url"] and link["label"] for link in configuration.social_links)


def test_the_share_image_url_is_empty_until_an_image_is_uploaded():
    assert SiteConfiguration.get_solo().share_image_url == ""


def test_the_image_fields_carry_the_shared_upload_validation(upload_file):
    for field_name in ("logo", "default_share_image"):
        field = SiteConfiguration._meta.get_field(field_name)
        validator = next(v for v in field.validators if isinstance(v, SecureFileValidator))

        assert validator.image is True

        # A .png extension over bytes that are not a PNG: the extension check and
        # the browser's own content type both pass, and content sniffing is the
        # only control that catches it.
        with pytest.raises(ValidationError):
            validator(upload_file("logo.png", b"this is plain text, not an image"))


def test_the_singleton_is_registered_in_the_django_admin():
    assert admin.site.is_registered(SiteConfiguration)


def test_the_admin_page_renders_for_an_administrator(client, admin_user):
    client.force_login(admin_user)

    # No object id: django-solo replaces the changelist route with the change
    # form for row 1, which is the URL the admin index links to.
    response = client.get(reverse("admin:core_siteconfiguration_change"))

    assert response.status_code == 200
    # The row is created on first view, so an administrator never meets a 404.
    assert SiteConfiguration.objects.count() == 1


def test_the_admin_refuses_to_add_or_delete_the_row(admin_user):
    model_admin = admin.site._registry[SiteConfiguration]

    assert model_admin.has_add_permission(None) is False
    assert model_admin.has_delete_permission(None) is False
{%- endif %}
