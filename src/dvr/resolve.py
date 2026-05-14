"""Thin facade over DaVinciResolveScript primitives.

We expose a `ResolveClient` Protocol so unit tests can substitute FakeResolve.
The real implementation defers all heavy work to the underlying Resolve handle.
"""
from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class ResolveClient(Protocol):
    def version(self) -> str: ...
    def edition(self) -> str: ...
    def project_manager(self) -> Any: ...
    def current_project(self) -> Optional[Any]: ...
    def raw(self) -> Any: ...


class RealResolveClient:
    """Wraps a live DaVinciResolveScript Resolve handle."""

    def __init__(self, resolve_handle: Any) -> None:
        self._resolve = resolve_handle

    def raw(self) -> Any:
        return self._resolve

    def version(self) -> str:
        return self._resolve.GetVersionString() or ""

    def edition(self) -> str:
        product = (self._resolve.GetProductName() or "").lower()
        return "Studio" if "studio" in product else "Free"

    def project_manager(self) -> Any:
        return self._resolve.GetProjectManager()

    def current_project(self) -> Optional[Any]:
        pm = self.project_manager()
        if pm is None:
            return None
        return pm.GetCurrentProject()
