"""Storage configuration.

None of this needs cloud credentials or a network, and that is deliberate: a test
that reaches a real bucket is an integration test and belongs elsewhere. What is
asserted here is the part that goes wrong silently - that the backend the project
selected is the one actually wired into ``STORAGES``, that personal data has a
storage of its own, and that nothing anywhere can hand out a link to it.

The configuration is read from ``settings.base`` rather than from the live
``settings`` object, because the test settings deliberately point the media
aliases back at local directories so the suite can run offline. ``base`` is what
the project ships.
"""

{%- if cookiecutter.media_storage != "filesystem" %}
import copy

{% endif %}
import pytest
from django.urls import reverse

{% if cookiecutter.media_storage != "filesystem" %}from apps.core import checks
{% endif %}
from apps.core.storage import PrivateMediaStorage, private_media_storage
from {{ cookiecutter.project_slug }}.settings import base

{%- if cookiecutter.media_storage == "s3" %}

#: What settings/base.py must have wired up for media_storage="s3".
EXPECTED_MEDIA_BACKEND = "storages.backends.s3.S3Storage"
{%- elif cookiecutter.media_storage == "gcs" %}

#: What settings/base.py must have wired up for media_storage="gcs".
EXPECTED_MEDIA_BACKEND = "storages.backends.gcloud.GoogleCloudStorage"
{%- elif cookiecutter.media_storage == "azure" %}

#: What settings/base.py must have wired up for media_storage="azure".
EXPECTED_MEDIA_BACKEND = "storages.backends.azure_storage.AzureStorage"
{%- else %}

#: What settings/base.py must have wired up for media_storage="filesystem".
EXPECTED_MEDIA_BACKEND = "django.core.files.storage.FileSystemStorage"
{%- endif %}
{%- if cookiecutter.static_storage == "cloud" %}

EXPECTED_STATIC_BACKEND = "apps.core.storage.StaticCloudStorage"
{%- else %}

EXPECTED_STATIC_BACKEND = "whitenoise.storage.CompressedManifestStaticFilesStorage"
{%- endif %}


# --- The selected backend is the one that is configured ----------------------


def test_media_uses_the_selected_backend():
    assert base.STORAGES["default"]["BACKEND"] == EXPECTED_MEDIA_BACKEND


def test_static_uses_the_selected_backend():
    assert base.STORAGES["staticfiles"]["BACKEND"] == EXPECTED_STATIC_BACKEND


def test_personal_data_has_a_storage_of_its_own():
    # One storage for both would mean a single misconfigured prefix publishes
    # every CV the site has ever received.
    assert base.STORAGES["private_media"]["BACKEND"] == "apps.core.storage.PrivateMediaStorage"
    assert base.STORAGES["private_media"] != base.STORAGES["default"]


# --- The private storage has no public URL ------------------------------------


def test_private_storage_refuses_to_build_a_url():
    # Instantiated directly rather than through the alias: this is the class the
    # project ships, whatever the test settings point the alias at.
    with pytest.raises(ValueError, match="no public URL"):
        PrivateMediaStorage().url("submissions/cv.pdf")


def test_the_configured_private_storage_refuses_too():
    # The class above is what the project ships; this is what it actually resolves
    # to at runtime. A template that renders the file's url attribute must fail
    # loudly rather than emit a path that happens to resolve.
    with pytest.raises(ValueError, match="no public URL"):
        private_media_storage().url("submissions/cv.pdf")


# --- The permission-checked view ---------------------------------------------


@pytest.mark.django_db
def test_anonymous_access_to_private_media_is_denied(client):
    # No file is created on purpose: the permission check must come first, so an
    # anonymous caller cannot even learn whether a given key exists.
    response = client.get(reverse("private_media", args=["submissions/cv.pdf"]))
    assert response.status_code == 403
{%- if cookiecutter.media_storage != "filesystem" %}


# --- The bucket is not world-readable -----------------------------------------


def test_no_media_storage_sends_a_public_acl():
    for alias in ("default", "private_media"):
        assert base.STORAGES[alias]["OPTIONS"].get("default_acl") is None


def test_private_media_urls_are_signed_and_expire():
    options = base.STORAGES["private_media"]["OPTIONS"]
{%- if cookiecutter.media_storage == "azure" %}
    # Azure has no per-object ACL: an unsigned blob URL only resolves when the
    # whole container is open to the world, so a SAS lifetime is what makes the
    # container's privacy usable.
    assert options["expiration_secs"] == base.PRIVATE_MEDIA_URL_EXPIRE_SECONDS
{%- elif cookiecutter.media_storage == "s3" %}
    assert options["querystring_auth"] is True
    assert options["querystring_expire"] == base.PRIVATE_MEDIA_URL_EXPIRE_SECONDS
{%- else %}
    assert options["querystring_auth"] is True
    assert options["expiration"].total_seconds() == base.PRIVATE_MEDIA_URL_EXPIRE_SECONDS
{%- endif %}


def test_private_media_never_sits_behind_a_cdn():
    # An edge cache is a copy of the file living outside every permission check.
    assert base.STORAGES["private_media"]["OPTIONS"].get("custom_domain") is None


def test_streaming_is_the_default_not_signed_urls():
    # A signed URL, once issued, is valid for its whole lifetime to anyone holding
    # it - after logout, after the permission is revoked, after it is forwarded.
    assert base.PRIVATE_MEDIA_SIGNED_URLS is False


# --- The deployment checks ----------------------------------------------------


def test_the_shipped_configuration_passes_the_public_bucket_check():
    assert checks.check_media_bucket_is_not_world_readable(None) == []


def test_a_public_acl_is_reported_as_an_error(settings):
    storages_setting = copy.deepcopy(base.STORAGES)
    storages_setting["default"].setdefault("OPTIONS", {})["default_acl"] = "public-read"
    settings.STORAGES = storages_setting

    errors = checks.check_media_bucket_is_not_world_readable(None)

    # An ERROR, not a warning: manage.py check exits non-zero and the deploy stops.
    assert [error.id for error in errors] == ["core.E001"]
    assert all(error.is_serious() for error in errors)


def test_missing_credentials_warn_under_production_settings(monkeypatch, settings):
    monkeypatch.setenv(
        "DJANGO_SETTINGS_MODULE", "{{ cookiecutter.project_slug }}.settings.production"
    )
{%- if cookiecutter.media_storage == "s3" %}
    settings.AWS_STORAGE_BUCKET_NAME = ""
{%- elif cookiecutter.media_storage == "gcs" %}
    settings.GS_BUCKET_NAME = ""
{%- else %}
    settings.AZURE_CONTAINER = ""
{%- endif %}

    warnings = checks.check_cloud_media_credentials(None)

    assert [warning.id for warning in warnings] == ["core.W006"]


def test_the_credentials_check_is_quiet_outside_production():
    # It would fire on every developer machine otherwise, and a check that always
    # fires is a check nobody reads.
    assert checks.check_cloud_media_credentials(None) == []
{%- endif %}
{%- if cookiecutter.asset_pipeline == "compressor" %}


# --- Asset pipeline -----------------------------------------------------------


def test_the_compressor_finder_is_installed():
    # Without it, collectstatic never picks up the compressed output and the
    # deploy ships a manifest pointing at files that are not there.
    assert "compressor.finders.CompressorFinder" in base.STATICFILES_FINDERS
    assert "compressor" in base.INSTALLED_APPS
{%- endif %}
