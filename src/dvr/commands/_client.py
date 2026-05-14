"""Lazy ResolveClient accessor.

Commands call `get()` instead of importing bootstrap directly so that:
- tests can monkeypatch the factory to inject a FakeResolveClient
- the real bridge connection is deferred until the first command actually
  needs Resolve (so `dvr --version` / `dvr --help` work without Resolve running)
"""
from __future__ import annotations

from typing import Callable, Optional

from ..bootstrap import connect_resolve
from ..resolve import RealResolveClient, ResolveClient

_factory: Optional[Callable[[], ResolveClient]] = None


def _default_factory() -> ResolveClient:
    return RealResolveClient(connect_resolve())


def set_factory(factory: Optional[Callable[[], ResolveClient]]) -> None:
    """Override the client factory (used by tests)."""
    global _factory
    _factory = factory


def get() -> ResolveClient:
    return (_factory or _default_factory)()
