"""The OpenAPI schema is generated from the code and must generate cleanly.

A warning from drf-spectacular is an endpoint whose contract we cannot describe,
which is a client that will guess. CI runs the same generation with
``--fail-on-warn`` and diffs the committed file, so an unintended contract change
cannot merge without somebody looking at it.
"""

import pytest
import yaml
from django.core.management import call_command
from django.core.management.base import CommandError

pytestmark = pytest.mark.django_db


@pytest.fixture
def schema(tmp_path):
    target = tmp_path / "schema.yml"
    try:
        call_command("spectacular", "--fail-on-warn", "--file", str(target))
    except (SystemExit, CommandError) as exc:  # pragma: no cover - only on a real failure
        pytest.fail(f"drf-spectacular reported warnings while generating the schema: {exc}")
    return yaml.safe_load(target.read_text(encoding="utf-8"))


def test_the_schema_generates_without_warnings(schema):
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"]


def test_every_application_path_is_versioned(schema):
    application_paths = [path for path in schema["paths"] if not path.startswith("/api/schema")]

    assert application_paths
    for path in application_paths:
        assert path.startswith("/api/v1/"), path


def test_the_example_resource_is_documented(schema):
    assert "/api/v1/notes/" in schema["paths"]
    assert "/api/v1/notes/{uuid}/" in schema["paths"]
    assert "/api/v1/notes/{uuid}/publish/" in schema["paths"]


def test_the_write_shape_never_accepts_owner_or_status(schema):
    request_body = schema["paths"]["/api/v1/notes/"]["post"]["requestBody"]
    reference = request_body["content"]["application/json"]["schema"]["$ref"]
    component = schema["components"]["schemas"][reference.rsplit("/", 1)[-1]]

    assert "owner" not in component["properties"]
    assert "status" not in component["properties"]


def test_the_page_size_parameter_is_published(schema):
    parameters = schema["paths"]["/api/v1/notes/"]["get"]["parameters"]

    assert "page_size" in {parameter["name"] for parameter in parameters}
