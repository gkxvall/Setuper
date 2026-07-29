"""Safe external editor invocation."""

import os
import shlex
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from setuper.domain.errors import AdapterUnavailableError, SetuperError


def open_editor(
    path: Path,
    *,
    environment: Mapping[str, str] | None = None,
    platform: str | None = None,
) -> None:
    """Open a file in the configured editor and wait for it to exit."""
    active_environment = os.environ if environment is None else environment
    command = active_environment.get("VISUAL") or active_environment.get("EDITOR")
    if command:
        try:
            arguments = shlex.split(command)
        except ValueError as error:
            raise AdapterUnavailableError(
                "Could not parse the configured editor command",
            ) from error
    elif (platform or sys.platform) == "darwin":
        arguments = ["/usr/bin/open", "-W", "-t"]
    else:
        raise AdapterUnavailableError(
            "No editor configured; set VISUAL or EDITOR",
        )
    if not arguments:
        raise AdapterUnavailableError(
            "The configured editor command is empty",
        )

    _run_editor((*arguments, str(path)))


def _run_editor(arguments: Sequence[str]) -> None:
    """Execute an editor argument vector without a shell."""
    try:
        result = subprocess.run(arguments, check=False)
    except OSError as error:
        raise AdapterUnavailableError(
            f"Could not start configured editor: {arguments[0]}",
            details={"executable": arguments[0]},
        ) from error
    if result.returncode != 0:
        raise SetuperError(
            f"Editor exited with status {result.returncode}",
            details={"exit_code": result.returncode},
        )
