"""Cryptographic hashing for exact manifest revisions."""

import hashlib
from pathlib import Path

from setuper.domain.errors import ManifestIOError

READ_CHUNK_SIZE = 128 * 1024


def hash_manifest(path: Path) -> str:
    """Return the lowercase SHA-256 digest of exact manifest bytes."""
    digest = hashlib.sha256()
    try:
        with path.open("rb") as manifest_file:
            while chunk := manifest_file.read(READ_CHUNK_SIZE):
                digest.update(chunk)
    except OSError as error:
        raise ManifestIOError(
            f"Could not hash manifest: {path}",
            details={"path": str(path)},
        ) from error
    return digest.hexdigest()
