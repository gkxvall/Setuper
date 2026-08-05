"""Browser window and tab detection through the native messaging protocol.

Browser capture requires an installed extension and its native messaging
host; Setuper never reads browser profile data directly. Incognito windows
are excluded entirely, and only tab URLs and titles are captured -- cookies,
form content, and authentication state are never requested.
"""

import subprocess
from pathlib import Path
from typing import Protocol, cast

from pydantic import JsonValue

from setuper.adapters.base import (
    BaseResourceAdapter,
    CaptureContext,
    DetectedResource,
)
from setuper.adapters.browser_protocol import (
    BrowserRequest,
    BrowserResponse,
    decode_response,
    encode_message,
    split_framed_message,
)
from setuper.adapters.identity import resource_slug
from setuper.domain.enums import CaptureSupport, Platform
from setuper.domain.errors import (
    AdapterUnavailableError,
    ManifestValidationError,
    UnsupportedPlatformError,
)
from setuper.domain.models import ResourceSpec

DEFAULT_TIMEOUT_SECONDS = 5.0
TAB_DATA_WARNING = "Cookies, form content, and authentication state are never captured."
MACHINE_BOUND_WARNING = "Browser profile and window identity are machine-bound."


class BrowserHost(Protocol):
    """Native messaging host boundary replaceable by deterministic fakes."""

    def list_windows(self) -> BrowserResponse:
        """Request the current non-incognito windows and their tabs."""


class NativeMessagingBrowserHost:
    """Speak the browser integration protocol to an installed native host."""

    def __init__(
        self,
        host_path: Path,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        """Create a transport bound to one native messaging host executable."""
        self._host_path = host_path
        self._timeout_seconds = timeout_seconds

    def list_windows(self) -> BrowserResponse:
        """Send one `list_windows` request and decode its framed response."""
        request = BrowserRequest(operation="list_windows")
        message = encode_message(request.to_message())
        try:
            completed = subprocess.run(
                (str(self._host_path),),
                input=message,
                capture_output=True,
                timeout=self._timeout_seconds,
                check=False,
            )
        except FileNotFoundError as error:
            raise AdapterUnavailableError(
                f"Browser integration host not found: {self._host_path}",
                details={"host": str(self._host_path)},
            ) from error
        except subprocess.TimeoutExpired as error:
            raise AdapterUnavailableError(
                f"Browser integration host timed out: {self._host_path}",
                details={"host": str(self._host_path)},
            ) from error
        except OSError as error:
            raise AdapterUnavailableError(
                f"Could not run browser integration host: {self._host_path}",
                details={"host": str(self._host_path)},
            ) from error
        if completed.returncode != 0:
            raise AdapterUnavailableError(
                f"Browser integration host exited with an error: {self._host_path}",
                details={
                    "host": str(self._host_path),
                    "returncode": completed.returncode,
                },
            )
        _, payload = split_framed_message(completed.stdout)
        return decode_response(payload, expected_request_id=request.request_id)


class BrowserAdapter(BaseResourceAdapter):
    """Detect open, non-incognito browser windows and their tabs."""

    type_name = "browser"

    def __init__(self, host: BrowserHost) -> None:
        """Create a browser adapter with an injectable native messaging host."""
        self._host = host

    def detect(self, context: CaptureContext) -> list[DetectedResource]:
        """Detect non-incognito windows and their tabs."""
        if context.platform is not Platform.MACOS:
            raise UnsupportedPlatformError(
                f"Browser detection is unsupported on: {context.platform.value}",
                details={"platform": context.platform.value},
            )
        response = self._host.list_windows()
        if not response.ok:
            return []
        windows = response.result.get("windows")
        if not isinstance(windows, list):
            return []

        findings = [
            finding
            for window in windows
            if isinstance(window, dict)
            if (finding := self._finding_for_window(window)) is not None
        ]
        return sorted(findings, key=lambda finding: finding.identity)

    def capture(self, resource: DetectedResource) -> ResourceSpec:
        """Convert one browser window finding into a review-required resource."""
        if resource.type_name != self.type_name:
            raise ManifestValidationError(
                f"Browser adapter cannot capture type: {resource.type_name}",
                details={"type": resource.type_name},
            )
        window_id = resource.config.get("window_id")
        if window_id is None:
            raise ManifestValidationError(
                "Detected browser window is missing its window ID",
            )
        metadata: dict[str, JsonValue] = dict(resource.metadata)
        metadata["capture_support"] = resource.support.value
        metadata["capture_warnings"] = list(resource.warnings)
        slug = resource_slug(str(window_id), fallback="window")
        return ResourceSpec(
            id=f"browser-{slug}",
            type=self.type_name,
            description=resource.display_name,
            config=dict(resource.config),
            metadata=metadata,
        )

    def _finding_for_window(
        self,
        window: dict[str, JsonValue],
    ) -> DetectedResource | None:
        """Build one finding from a non-incognito browser window record."""
        if window.get("incognito") is True:
            return None
        window_id = window.get("window_id")
        if not isinstance(window_id, str | int):
            return None
        raw_tabs = window.get("tabs")
        tabs = raw_tabs if isinstance(raw_tabs, list) else []
        tab_entries: list[dict[str, JsonValue]] = []
        for tab in tabs:
            if not isinstance(tab, dict):
                continue
            url = tab.get("url")
            if not isinstance(url, str) or not url:
                continue
            entry: dict[str, JsonValue] = {"url": url}
            title = tab.get("title")
            if isinstance(title, str) and title:
                entry["title"] = title
            tab_entries.append(entry)
        if not tab_entries:
            return None

        browser_name = window.get("browser")
        browser_label = (
            browser_name if isinstance(browser_name, str) and browser_name else None
        )
        config: dict[str, JsonValue] = {
            "window_id": window_id,
            "tabs": cast(JsonValue, tab_entries),
        }
        if browser_label:
            config["browser"] = browser_label

        return DetectedResource(
            identity=f"browser:{browser_label or 'unknown'}:{window_id}",
            type_name=self.type_name,
            display_name=f"{browser_label or 'Browser'} window {window_id}",
            support=CaptureSupport.PARTIALLY_SUPPORTED,
            config=config,
            metadata={"capture_source": "browser"},
            warnings=(TAB_DATA_WARNING, MACHINE_BOUND_WARNING),
        )
