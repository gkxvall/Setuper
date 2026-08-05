"""Tests for browser window and tab detection through native messaging."""

import json
import subprocess
from pathlib import Path

import pytest

from setuper.adapters import browser as browser_module
from setuper.adapters.base import CaptureContext, DetectedResource
from setuper.adapters.browser import BrowserAdapter, NativeMessagingBrowserHost
from setuper.adapters.browser_protocol import (
    PROTOCOL_VERSION,
    BrowserResponse,
    encode_message,
)
from setuper.domain.enums import CaptureSupport, Platform
from setuper.domain.errors import AdapterUnavailableError, ManifestValidationError


class FakeBrowserHost:
    """Host boundary returning one configured response."""

    def __init__(self, response: BrowserResponse) -> None:
        self._response = response

    def list_windows(self) -> BrowserResponse:
        """Return the configured response."""
        return self._response


def make_context(platform: Platform = Platform.MACOS) -> CaptureContext:
    """Create a deterministic capture context."""
    return CaptureContext(platform=platform, current_directory=Path("/repo"))


def test_browser_detection_captures_tabs_and_excludes_incognito() -> None:
    """Incognito windows are excluded; regular windows keep only URL and title."""
    response = BrowserResponse(
        request_id="abc",
        ok=True,
        result={
            "windows": [
                {
                    "window_id": 1,
                    "browser": "Safari",
                    "incognito": False,
                    "tabs": [
                        {"url": "https://example.com", "title": "Example"},
                        {"url": "https://second.example.com"},
                    ],
                },
                {
                    "window_id": 2,
                    "browser": "Safari",
                    "incognito": True,
                    "tabs": [{"url": "https://private.example.com"}],
                },
            ]
        },
    )
    adapter = BrowserAdapter(FakeBrowserHost(response))

    findings = adapter.detect(make_context())

    assert len(findings) == 1
    finding = findings[0]
    assert finding.support is CaptureSupport.PARTIALLY_SUPPORTED
    assert finding.config["tabs"] == [
        {"url": "https://example.com", "title": "Example"},
        {"url": "https://second.example.com"},
    ]
    assert "Cookies, form content, and authentication state" in " ".join(
        finding.warnings
    )

    resource = adapter.capture(finding)
    assert resource.id == "browser-1"
    assert resource.type == "browser"


def test_browser_detection_skips_windows_with_no_capturable_tabs() -> None:
    """A window whose tabs all lack a URL contributes no finding."""
    response = BrowserResponse(
        request_id="abc",
        ok=True,
        result={"windows": [{"window_id": 1, "tabs": [{"title": "No URL"}]}]},
    )

    assert BrowserAdapter(FakeBrowserHost(response)).detect(make_context()) == []


def test_browser_detection_handles_unsuccessful_response() -> None:
    """A host-reported failure yields no findings rather than raising."""
    response = BrowserResponse(request_id="abc", ok=False, error="extension not ready")

    assert BrowserAdapter(FakeBrowserHost(response)).detect(make_context()) == []


def test_browser_detection_rejects_unsupported_platform() -> None:
    """Browser capture stays within the documented macOS v1 scope."""
    adapter = BrowserAdapter(FakeBrowserHost(BrowserResponse("abc", True)))

    with pytest.raises(Exception, match="unsupported"):
        adapter.detect(make_context(Platform.LINUX))


def test_browser_capture_rejects_foreign_type() -> None:
    """Capture rejects findings produced by a different adapter."""
    adapter = BrowserAdapter(FakeBrowserHost(BrowserResponse("abc", True)))
    foreign = DetectedResource(
        identity="git:/repo",
        type_name="git",
        display_name="repo",
        support=CaptureSupport.MACHINE_BOUND,
    )

    with pytest.raises(ManifestValidationError):
        adapter.capture(foreign)


def test_native_messaging_host_sends_and_decodes_a_framed_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The native transport frames its request and decodes a framed response."""
    captured: dict[str, object] = {}

    def fake_run(
        arguments: tuple[str, ...],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[bytes]:
        captured["arguments"] = arguments
        sent_input = kwargs["input"]
        assert isinstance(sent_input, bytes)
        captured["input"] = sent_input
        request_id = json.loads(sent_input[4:])["request_id"]
        response_message = {
            "protocol_version": PROTOCOL_VERSION,
            "request_id": request_id,
            "ok": True,
            "result": {"windows": []},
        }
        return subprocess.CompletedProcess(
            arguments,
            0,
            encode_message(response_message),
            b"",
        )

    monkeypatch.setattr(browser_module.subprocess, "run", fake_run)
    host = NativeMessagingBrowserHost(Path("/usr/local/bin/setuper-browser-host"))

    response = host.list_windows()

    assert response.ok is True
    assert response.result == {"windows": []}


def test_native_messaging_host_types_missing_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing native messaging host uses the adapter error model."""

    def missing(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError

    monkeypatch.setattr(browser_module.subprocess, "run", missing)
    host = NativeMessagingBrowserHost(Path("/missing/host"))

    with pytest.raises(AdapterUnavailableError, match="not found"):
        host.list_windows()
