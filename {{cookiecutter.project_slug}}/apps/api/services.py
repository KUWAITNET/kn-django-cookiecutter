"""EXAMPLE outbound integration - the Part B pattern of api-standard.md.

Copy this module to ``apps/<domain>/services.py`` (or
``apps/integrations/<vendor>/``) per integration and delete the example. Never
put an outbound call in a view, a model method or a template tag.

What the pattern guarantees, and why each rule exists:

- **Our exceptions, not the library's.** A caller cannot be expected to know that
  a ``requests.Timeout``, an ``ssl.SSLError`` and a vendor library's own fault
  class all mean "the upstream is having a bad day".
- **Plain Python data crosses the boundary.** A vendor library's types must not
  leak past this module, or replacing the vendor becomes a rewrite.
- **A settings guard at the top of every public method.** The application boots
  with the integration unconfigured - a missing vendor credential must not block
  a deploy of an unrelated feature - and a missing setting produces a clear,
  early, actionable error naming the variables rather than an ``AttributeError``
  three frames into somebody else's library.
- **An explicit connect *and* read timeout on every call.** Library defaults are
  never relied on and never assumed to exist. An upstream that accepts a
  connection and then never answers holds a gunicorn worker forever; four workers
  and four such requests is a total outage of a site whose own code is fine.
- **Retries for idempotent methods only**, with exponential backoff and full
  jitter. Without jitter every worker that failed during an upstream blip retries
  in the same millisecond and the recovery attempt is the second outage.
- **TLS verification is never disabled**, in any environment, including local
  development. A vendor whose certificate does not validate has a problem we
  escalate to them; the workaround would be permanent and the escalation is not.
- **Failures never leak upstream internals to an end user.** The vendor's error
  text, status line and URL go to the log and to Sentry; the caller gets one of
  our own messages.

Settings this example reads (all optional, all defaulting to empty so the project
boots without them)::

    INTEGRATION_BASE_URL, INTEGRATION_USERNAME, INTEGRATION_PASSWORD
    INTEGRATION_TIMEOUT_CONNECT (default 5.0), INTEGRATION_TIMEOUT_READ (15.0)
    INTEGRATION_FORCE_TLS12 (default False)

Record the integration in ``docs/third-party-services.md`` when you build it, not
at handover: name, vendor, purpose, direction, base URL per environment, auth and
where the credential is stored, its named owner, rotation cadence, data sent and
received, timeouts, retry policy, degradation mode, health-check URL, cost,
support contact and the date somebody last verified the row.
"""

from __future__ import annotations

import logging
import ssl
import time
from typing import Any

import requests
{%- if cookiecutter.sentry == "yes" %}
import sentry_sdk
{%- endif %}
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.util.ssl_ import create_urllib3_context

logger = logging.getLogger("{{ cookiecutter.project_slug }}.integrations")


class UpstreamError(Exception):
    """Base class for every failure this service layer can raise."""


class UpstreamMisconfigured(UpstreamError, ImproperlyConfigured):
    """Required settings are absent. Raised before any network call is attempted."""


class UpstreamUnavailable(UpstreamError):
    """The upstream timed out, refused the connection, or returned 5xx."""


class UpstreamRejected(UpstreamError):
    """The upstream returned 4xx: our request was wrong, or our credentials were."""


class MinimumTLS12Adapter(HTTPAdapter):
    """Floor the negotiated TLS version at 1.2. Safe default for every integration.

    Certificate verification is untouched - this adapter never disables it, and
    no subclass of it may.
    """

    maximum_tls_version: ssl.TLSVersion | None = None

    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        if self.maximum_tls_version is not None:
            context.maximum_version = self.maximum_tls_version
        kwargs["ssl_context"] = context
        super().init_poolmanager(*args, **kwargs)


class PinnedTLS12Adapter(MinimumTLS12Adapter):
    """Pin TLS to exactly 1.2 for a legacy endpoint that cannot negotiate 1.3.

    This is a deliberate downgrade and is opt-in per integration
    (``INTEGRATION_FORCE_TLS12``), never global and never a default. A previous
    KUWAITNET project needed exactly this for a WCF/IIS SOAP service that
    advertised TLS 1.3 and then failed to complete the handshake. Record the
    reason and a review date in the third-party register, and remove the pin when
    the vendor fixes their endpoint.
    """

    maximum_tls_version = ssl.TLSVersion.TLSv1_2


class ExampleIntegrationClient:
    """Settings-guarded, timeout-bounded REST client. EXAMPLE - replace.

    Credentials come from the environment and the company secrets vault, and from
    nowhere else: not from a settings module, not from a committed ``.env``, not
    from a fixture, not from a ticket comment. A credential that has ever been
    committed is rotated, not deleted - git history is not a delete.
    """

    name = "example"

    _REQUIRED_SETTINGS = (
        "INTEGRATION_BASE_URL",
        "INTEGRATION_USERNAME",
        "INTEGRATION_PASSWORD",
    )

    # POST is deliberately absent: a read timeout on a non-idempotent call must
    # not be retried, because we do not know whether the upstream processed it
    # and a retry can double-charge. Where the upstream offers an idempotency
    # key, retry that call explicitly and send one.
    _IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "PUT", "DELETE"})

    def __init__(self) -> None:
        self._require_settings()
        self._session = self._build_session()

    # -- configuration ----------------------------------------------------

    @staticmethod
    def _setting(name: str, default: Any = "") -> Any:
        return getattr(settings, name, default)

    @classmethod
    def is_configured(cls) -> bool:
        """True when every required setting is present.

        URL registration and the health check consult this, so an unconfigured
        integration is *absent* rather than broken.
        """
        return all(cls._setting(name) for name in cls._REQUIRED_SETTINGS)

    def _require_settings(self) -> None:
        """Runs at the top of every public method, before any network work."""
        missing = [name for name in self._REQUIRED_SETTINGS if not self._setting(name)]
        if missing:
            raise UpstreamMisconfigured(
                f"{', '.join(missing)} must be set in the environment before the "
                f"{self.name} integration can be used."
            )

    @property
    def _timeout(self) -> tuple[float, float]:
        """(connect, read). Never omitted - requests waits forever without it."""
        return (
            float(self._setting("INTEGRATION_TIMEOUT_CONNECT", 5.0)),
            float(self._setting("INTEGRATION_TIMEOUT_READ", 15.0)),
        )

    # -- transport --------------------------------------------------------

    def _build_adapter(self) -> HTTPAdapter:
        retry = Retry(
            total=2,  # 2 retries = 3 attempts, bounded in attempts and wall clock
            connect=2,
            read=0,  # a response that started but did not finish is not retried
            status=2,
            status_forcelist=(408, 429, 500, 502, 503, 504),
            allowed_methods=self._IDEMPOTENT_METHODS,
            backoff_factor=0.5,
            backoff_jitter=1.0,
            backoff_max=8.0,
            # An upstream's own Retry-After overrides our backoff; ignoring it is
            # how a temporary 429 becomes a permanent block.
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter_class = (
            PinnedTLS12Adapter
            if self._setting("INTEGRATION_FORCE_TLS12", False)
            else MinimumTLS12Adapter
        )
        return adapter_class(max_retries=retry)

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        # Identify ourselves. If an upstream ever rejects this and demands a
        # browser string, say so here with the reason - an unexplained UA spoof
        # looks like a mistake and gets "cleaned up" by the next engineer.
        session.headers.update({"User-Agent": f"{settings.SITE_NAME}/1.0 (+KUWAITNET)"})
        session.auth = (
            self._setting("INTEGRATION_USERNAME"),
            self._setting("INTEGRATION_PASSWORD"),
        )
        session.mount("https://", self._build_adapter())
        return session

    def _breadcrumb(
        self,
        method: str,
        path: str,
        status_code: int | None,
        started: float,
        outcome: str,
    ) -> None:
        """One line per attempt: method, path template, status, duration, outcome.

        Never the request or response body, never the credentials, never the
        Authorization header. A retry that succeeds silently hides a degrading
        upstream until it fails completely, so this is the only place the
        degradation is visible before the outage.
        """
        record = {
            "integration": self.name,
            "upstream_method": method,
            "upstream_path": path,
            "upstream_status": status_code,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "outcome": outcome,
        }
{%- if cookiecutter.sentry == "yes" %}
        sentry_sdk.add_breadcrumb(
            category="integration",
            message=f"{self.name}.request",
            data=record,
            level="info" if outcome == "ok" else "warning",
        )
{%- endif %}
        if outcome == "ok":
            logger.info("integration.request", extra=record)
        else:
            logger.warning("integration.request", extra=record)

    def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        """Perform one upstream call and return plain Python data.

        Raises ``UpstreamUnavailable`` or ``UpstreamRejected``; the messages are
        ours, so nothing the vendor wrote can reach an end user through them.
        """
        self._require_settings()
        base_url = str(self._setting("INTEGRATION_BASE_URL")).rstrip("/")
        url = f"{base_url}/{path.lstrip('/')}"
        started = time.monotonic()

        try:
            response = self._session.request(method, url, timeout=self._timeout, **kwargs)
        except requests.Timeout as exc:
            self._breadcrumb(method, path, None, started, "timeout")
            raise UpstreamUnavailable("The upstream service did not respond in time.") from exc
        except requests.RequestException as exc:
            self._breadcrumb(method, path, None, started, "transport-error")
            raise UpstreamUnavailable("The upstream service could not be reached.") from exc

        status_code = response.status_code
        if status_code >= 500:
            self._breadcrumb(method, path, status_code, started, "upstream-error")
            raise UpstreamUnavailable("The upstream service reported an internal error.")
        if status_code >= 400:
            self._breadcrumb(method, path, status_code, started, "rejected")
            raise UpstreamRejected("The upstream service rejected the request.")

        try:
            payload = response.json()
        except ValueError as exc:
            self._breadcrumb(method, path, status_code, started, "malformed")
            raise UpstreamUnavailable(
                "The upstream service returned a malformed response."
            ) from exc

        self._breadcrumb(method, path, status_code, started, "ok")
        # Plain dicts cross the boundary, never the client library's own objects.
        return payload if isinstance(payload, dict) else {"data": payload}

    # -- public surface ---------------------------------------------------

    def ping(self) -> dict:
        """Cheap liveness call used by the health check. Upstream: ``GET /health``."""
        return self._request("GET", "/health")

    def fetch_record(self, reference: str) -> dict:
        """Upstream: ``GET /records/{reference}``. Idempotent, so it is retried."""
        return self._request("GET", f"/records/{reference}")

    def submit_enquiry(self, payload: dict) -> dict:
        """Upstream: ``POST /enquiries``. NOT retried - a duplicate has real cost.

        Where the upstream supports an idempotency key, send one and retry
        deliberately. Where it does not, surface the failure and let a human
        reconcile it; say so to the client explicitly for payment integrations.
        """
        return self._request("POST", "/enquiries", json=payload)
