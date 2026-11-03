"""Storage configuration.

None of this needs cloud credentials or a network, and that is deliberate: a test
that reaches a real bucket is an integration test and belongs elsewhere. What is
asserted here is the part that goes wrong silently - that the backend the project
selected is the one actually wired into ``STORAGES``, that personal data has a
storage of its own, and that every link to it is signed and expires.

The configuration is read from ``settings.base`` rather than from the live
``settings`` object, because the test settings deliberately point the media
aliases back at local directories so the suite can run offline. ``base`` is what
the project ships.
"""

{% if cookiecutter.media_storage != "filesystem" -%}
import copy

{% endif -%}
{% if cookiecutter.media_storage == "filesystem" -%}
from pathlib import Path

{% endif -%}
from apps.core import checks
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
{%- if cookiecutter.media_storage == "filesystem" %}

EXPECTED_PRIVATE_BACKEND = "apps.core.storage.SignedFileSystemStorage"
{%- else %}

EXPECTED_PRIVATE_BACKEND = "apps.core.storage.PrivateMediaStorage"
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
    assert base.STORAGES["private"]["BACKEND"] == EXPECTED_PRIVATE_BACKEND
    assert base.STORAGES["private"] != base.STORAGES["default"]


# --- Signed links, and their defaults -----------------------------------------


def test_signed_links_live_an_hour_by_default():
    assert base.PRIVATE_URL_EXPIRY_SECONDS == 3600


def test_page_links_go_through_the_gate_by_default():
    assert base.PRIVATE_FILE_LINKS_ENABLED is True


def test_django_streams_private_files_until_nginx_is_configured():
    # The X-Accel prefix only works once nginx has the matching internal
    # location, so it is off until a server says otherwise.
    assert base.PRIVATE_FILES_ACCEL_PREFIX == ""


def test_an_expiry_over_an_hour_is_reported(settings):
    settings.PRIVATE_URL_EXPIRY_SECONDS = 86400
    assert [w.id for w in checks.check_private_url_expiry(None)] == ["core.W011"]
{%- if cookiecutter.media_storage == "filesystem" %}


def test_private_media_root_is_outside_media_root():
    # Under it, the public /media/ location would serve every private file.
    private = Path(base.PRIVATE_MEDIA_ROOT).resolve()
    assert not private.is_relative_to(Path(base.MEDIA_ROOT).resolve())


def test_private_media_root_inside_media_root_is_an_error(settings):
    settings.PRIVATE_MEDIA_ROOT = str(Path(settings.MEDIA_ROOT) / "private")
    errors = checks.check_private_media_root_is_outside_media_root(None)
    assert [error.id for error in errors] == ["core.E009"]
{%- endif %}
{%- if cookiecutter.media_storage != "filesystem" %}


# --- The bucket is not world-readable -----------------------------------------


def test_no_media_storage_sends_a_public_acl():
    for alias in ("default", "private"):
        assert base.STORAGES[alias]["OPTIONS"].get("default_acl") is None


def test_private_media_urls_are_signed_and_expire():
    options = base.STORAGES["private"]["OPTIONS"]
{%- if cookiecutter.media_storage == "azure" %}
    # Azure has no per-object ACL: an unsigned blob URL only resolves when the
    # whole container is open to the world, so a SAS lifetime is what makes the
    # container's privacy usable.
    assert options["expiration_secs"] == base.PRIVATE_URL_EXPIRY_SECONDS
{%- elif cookiecutter.media_storage == "s3" %}
    assert options["querystring_auth"] is True
    assert options["querystring_expire"] == base.PRIVATE_URL_EXPIRY_SECONDS
{%- else %}
    assert options["querystring_auth"] is True
    assert options["expiration"].total_seconds() == base.PRIVATE_URL_EXPIRY_SECONDS
{%- endif %}


def test_private_media_never_sits_behind_a_cdn():
    # An edge cache is a copy of the file living outside every permission check.
    assert base.STORAGES["private"]["OPTIONS"].get("custom_domain") is None
{%- if cookiecutter.media_storage == "s3" %}


def test_presigned_links_are_sigv4_and_virtual_hosted():
    # Left to botocore, older regions still sign SigV2, which buckets created
    # after June 2020 refuse with SignatureDoesNotMatch.
    options = base.STORAGES["private"]["OPTIONS"]
    assert options["signature_version"] == "s3v4"
    assert options["addressing_style"] == "virtual"


def test_presigned_links_tell_the_browser_not_to_keep_a_copy():
    from apps.core.storage import PrivateMediaStorage

    storage = PrivateMediaStorage(
        bucket_name="private-bucket",
        region_name="me-south-1",
        access_key="AKIAEXAMPLE",
        secret_key="example-secret",  # noqa: S106
        signature_version="s3v4",
        querystring_auth=True,
    )
    url = storage.url("members/civil-id.jpg")
    assert "X-Amz-Algorithm=AWS4-HMAC-SHA256" in url
    assert "response-cache-control=private%2C%20no-store" in url
{%- endif %}


def test_private_media_must_not_share_the_public_bucket(settings):
{%- if cookiecutter.media_storage == "s3" %}
    settings.AWS_STORAGE_BUCKET_NAME = settings.AWS_PRIVATE_BUCKET_NAME = "one-bucket"
{%- elif cookiecutter.media_storage == "gcs" %}
    settings.GS_BUCKET_NAME = settings.GS_PRIVATE_BUCKET_NAME = "one-bucket"
{%- else %}
    settings.AZURE_CONTAINER = settings.AZURE_PRIVATE_CONTAINER = "one-container"
{%- endif %}
    errors = checks.check_private_media_has_its_own_bucket(None)
    assert [error.id for error in errors] == ["core.E010"]


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
        "DJANGO_SETTINGS_MODULE",
        "{{ cookiecutter.project_slug }}.settings.production",
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
