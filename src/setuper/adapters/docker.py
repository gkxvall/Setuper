"""Docker container detection without mutating container state."""

import json
from typing import cast

from pydantic import JsonValue

from setuper.adapters.base import (
    BaseResourceAdapter,
    CaptureContext,
    DetectedResource,
)
from setuper.adapters.identity import resource_slug
from setuper.domain.enums import CaptureSupport, Platform
from setuper.domain.errors import ManifestValidationError, UnsupportedPlatformError
from setuper.domain.models import ResourceSpec
from setuper.infrastructure.commands import CommandResult, CommandRunner

SHORT_ID_LENGTH = 12


class DockerAdapter(BaseResourceAdapter):
    """Detect running containers through the Docker CLI JSON boundary."""

    type_name = "docker"

    def __init__(self, runner: CommandRunner) -> None:
        """Create a Docker adapter with an injectable command boundary."""
        self._runner = runner

    def detect(self, context: CaptureContext) -> list[DetectedResource]:
        """Detect running containers and their non-destructive configuration."""
        if context.platform is not Platform.MACOS:
            raise UnsupportedPlatformError(
                f"Docker detection is unsupported on: {context.platform.value}",
                details={"platform": context.platform.value},
            )
        ps_result = self._docker("ps", "--quiet", "--no-trunc")
        if ps_result.returncode != 0:
            return []
        container_ids = [
            line.strip() for line in ps_result.stdout.splitlines() if line.strip()
        ]
        if not container_ids:
            return []

        inspect_result = self._docker("inspect", *container_ids)
        containers = _parse_containers(inspect_result)
        findings = [
            finding
            for container in containers
            if (finding := self._finding_for(container)) is not None
        ]
        return sorted(findings, key=lambda finding: finding.identity)

    def capture(self, resource: DetectedResource) -> ResourceSpec:
        """Convert one Docker finding into a review-required resource."""
        if resource.type_name != self.type_name:
            raise ManifestValidationError(
                f"Docker adapter cannot capture type: {resource.type_name}",
                details={"type": resource.type_name},
            )
        container_id = resource.config.get("container_id")
        if not isinstance(container_id, str) or not container_id:
            raise ManifestValidationError(
                "Detected container is missing its container ID",
            )
        metadata: dict[str, JsonValue] = dict(resource.metadata)
        metadata["capture_support"] = resource.support.value
        metadata["capture_warnings"] = list(resource.warnings)
        name = resource.config.get("container_name")
        slug_source = name if isinstance(name, str) and name else container_id
        fallback = container_id[:SHORT_ID_LENGTH]
        return ResourceSpec(
            id=f"docker-{resource_slug(slug_source, fallback=fallback)}",
            type=self.type_name,
            description=resource.display_name,
            config=dict(resource.config),
            metadata=metadata,
        )

    def _finding_for(self, container: dict[str, JsonValue]) -> DetectedResource | None:
        """Build one finding from a `docker inspect` container record."""
        raw_id = container.get("Id")
        if not isinstance(raw_id, str) or not raw_id:
            return None
        short_id = raw_id[:SHORT_ID_LENGTH]
        raw_name = container.get("Name")
        name = raw_name.lstrip("/") if isinstance(raw_name, str) else ""

        config_section = container.get("Config")
        config_section = config_section if isinstance(config_section, dict) else {}
        image = config_section.get("Image")
        command = config_section.get("Cmd") or []
        working_dir = config_section.get("WorkingDir") or None
        env_entries = config_section.get("Env")
        env_names = sorted(
            {
                entry.split("=", 1)[0]
                for entry in (env_entries if isinstance(env_entries, list) else [])
                if isinstance(entry, str) and "=" in entry
            }
        )

        support = (
            CaptureSupport.PARTIALLY_SUPPORTED
            if isinstance(image, str) and image
            else CaptureSupport.UNSUPPORTED
        )

        config: dict[str, JsonValue] = {
            "container_id": short_id,
            "container_name": name,
        }
        if isinstance(image, str) and image:
            config["image"] = image
        if isinstance(command, list) and command:
            config["command"] = cast(JsonValue, list(command))
        if working_dir:
            config["working_dir"] = working_dir
        if env_names:
            config["env_names"] = cast(JsonValue, env_names)
        ports = _extract_ports(container)
        if ports:
            config["ports"] = cast(JsonValue, ports)
        mounts = _extract_mounts(container)
        if mounts:
            config["mounts"] = cast(JsonValue, mounts)

        warnings = [
            "Container state outside mounted volumes will not be restored.",
        ]
        if env_names:
            warnings.append(
                "Environment variable values were not captured; "
                "supply them through variables or secret references."
            )
        if mounts:
            warnings.append("Mount source paths are machine-bound.")

        return DetectedResource(
            identity=f"docker:{short_id}",
            type_name=self.type_name,
            display_name=name or short_id,
            support=support,
            config=config,
            metadata={"capture_source": "docker"},
            warnings=tuple(warnings),
        )

    def _docker(self, *arguments: str) -> CommandResult:
        """Run one read-only Docker CLI query."""
        return self._runner.run(("docker", *arguments))


def _parse_containers(result: CommandResult) -> list[dict[str, JsonValue]]:
    """Parse best-effort `docker inspect` JSON output."""
    text = result.stdout.strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [entry for entry in parsed if isinstance(entry, dict)]


def _extract_ports(container: dict[str, JsonValue]) -> list[dict[str, JsonValue]]:
    """Extract published and exposed ports from container network settings."""
    network_settings = container.get("NetworkSettings")
    network_settings = network_settings if isinstance(network_settings, dict) else {}
    ports_map = network_settings.get("Ports")
    ports_map = ports_map if isinstance(ports_map, dict) else {}

    ports: list[dict[str, JsonValue]] = []
    for container_port, bindings in sorted(ports_map.items()):
        port_number_text, _, protocol = container_port.partition("/")
        try:
            port_number = int(port_number_text)
        except ValueError:
            continue
        protocol = protocol or "tcp"
        if not isinstance(bindings, list) or not bindings:
            ports.append({"container_port": port_number, "protocol": protocol})
            continue
        for binding in bindings:
            if not isinstance(binding, dict):
                continue
            host_port_text = binding.get("HostPort")
            entry: dict[str, JsonValue] = {
                "container_port": port_number,
                "protocol": protocol,
            }
            host_ip = binding.get("HostIp")
            if isinstance(host_ip, str) and host_ip:
                entry["host_ip"] = host_ip
            if isinstance(host_port_text, str) and host_port_text.isdigit():
                entry["host_port"] = int(host_port_text)
            ports.append(entry)
    return ports


def _extract_mounts(container: dict[str, JsonValue]) -> list[dict[str, JsonValue]]:
    """Extract mount points without assuming their host paths are portable."""
    raw_mounts = container.get("Mounts")
    raw_mounts = raw_mounts if isinstance(raw_mounts, list) else []
    mounts: list[dict[str, JsonValue]] = []
    for mount in raw_mounts:
        if not isinstance(mount, dict):
            continue
        entry: dict[str, JsonValue] = {}
        for key, target in (
            ("Type", "type"),
            ("Source", "source"),
            ("Destination", "destination"),
            ("Mode", "mode"),
            ("RW", "read_write"),
        ):
            value = mount.get(key)
            if value is not None:
                entry[target] = cast(JsonValue, value)
        if entry:
            mounts.append(entry)
    return mounts
