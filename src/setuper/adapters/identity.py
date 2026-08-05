"""Shared helpers for building stable, schema-valid resource identities."""

import re


def resource_slug(value: str, *, fallback: str) -> str:
    """Create a schema-valid resource-ID suffix or a safe fallback."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or fallback
