"""Ordered immutable database migrations."""

from setuper.infrastructure.database import Migration
from setuper.infrastructure.migrations.v0001_initial import INITIAL_SCHEMA

MIGRATIONS: tuple[Migration, ...] = (INITIAL_SCHEMA,)

__all__ = ["MIGRATIONS"]
