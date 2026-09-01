"""Honeypot{% if cookiecutter.spam_protection == "turnstile_honeypot" %} and Turnstile{% endif %} protection on public forms."""

from django import forms

from apps.core.spam import (
    HONEYPOT_FIELD_NAME,
    SPAM_REJECTION_MESSAGE,
{%- if cookiecutter.spam_protection == "turnstile_honeypot" %}
    TURNSTILE_FIELD_NAME,
{%- endif %}
    SpamProtectedForm,
{%- if cookiecutter.spam_protection == "turnstile_honeypot" %}
    turnstile_configured,
{%- endif %}
)


class ExampleForm(SpamProtectedForm, forms.Form):
    email = forms.EmailField()


def test_the_honeypot_field_is_present_and_optional():
    form = ExampleForm()
    assert HONEYPOT_FIELD_NAME in form.fields
    assert form.fields[HONEYPOT_FIELD_NAME].required is False


def test_a_normal_submission_is_accepted():
    form = ExampleForm(data={"email": "person@example.com"})
    assert form.is_valid(), form.errors


def test_a_filled_honeypot_is_rejected():
    form = ExampleForm(data={"email": "person@example.com", HONEYPOT_FIELD_NAME: "http://spam"})
    assert not form.is_valid()


def test_the_rejection_reveals_nothing_about_what_caught_it():
    form = ExampleForm(data={"email": "person@example.com", HONEYPOT_FIELD_NAME: "http://spam"})
    form.is_valid()
    # No field-level error pointing at the honeypot, and the same wording any
    # other failure would produce: a bot must not learn which control fired.
    assert HONEYPOT_FIELD_NAME not in form.errors
    assert form.errors["__all__"] == [str(SPAM_REJECTION_MESSAGE)]
{%- if cookiecutter.spam_protection == "turnstile_honeypot" %}


def test_protection_degrades_to_honeypot_only_without_a_key(settings):
    settings.TURNSTILE_SECRET_KEY = ""
    assert turnstile_configured() is False
    # Development, CI and UAT have no key and must still be able to submit.
    form = ExampleForm(data={"email": "person@example.com"})
    assert form.is_valid(), form.errors


def test_a_missing_turnstile_token_is_rejected_when_a_key_is_configured(settings, monkeypatch):
    settings.TURNSTILE_SECRET_KEY = "test-secret"
    called = {}

    def _fake_verify(token, remote_ip=""):
        called["token"] = token
        return False

    monkeypatch.setattr("apps.core.spam.verify_turnstile", _fake_verify)
    form = ExampleForm(data={"email": "person@example.com"})
    assert not form.is_valid()
    assert called["token"] == ""


def test_a_verified_turnstile_token_is_accepted(settings, monkeypatch):
    settings.TURNSTILE_SECRET_KEY = "test-secret"
    monkeypatch.setattr("apps.core.spam.verify_turnstile", lambda token, remote_ip="": True)
    form = ExampleForm(data={"email": "person@example.com", TURNSTILE_FIELD_NAME: "a-token"})
    assert form.is_valid(), form.errors


def test_verification_fails_closed_when_cloudflare_is_unreachable(settings, monkeypatch):
    import requests

    from apps.core import spam

    settings.TURNSTILE_SECRET_KEY = "test-secret"

    def _raise(*args, **kwargs):
        raise requests.ConnectionError("unreachable")

    monkeypatch.setattr(requests, "post", _raise)
    # An outage at the provider must not silently disable the control.
    assert spam.verify_turnstile("a-token") is False
{%- endif %}
