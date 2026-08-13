"""Read-only access to curated RoboTwin runtime resources."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rpent.tools.toolkit import readonly

MAX_RESOURCE_CHARS = 40_000
_REPO_PREFIX = ("resources", "robotwin")


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return (
        text[:max_chars]
        + f"\n\n[TRUNCATED — file is {len(text)} chars, showed first {max_chars}]"
    )


class RoboTwinResourceReader:
    """Expose only files below ``resources/robotwin`` to the Planner."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def _resolve(
        self,
        path: str,
        *,
        allow_root: bool = False,
    ) -> tuple[Path | None, str | None]:
        relative = Path(path)
        if relative.is_absolute():
            return None, "absolute paths are not allowed"
        parts = relative.parts
        if parts[:2] == _REPO_PREFIX:
            relative = Path(*parts[2:])
        if not relative.parts:
            if allow_root:
                return self._root, None
            return None, "path must name a file under resources/robotwin"
        if ".." in relative.parts:
            return None, "path must stay under resources/robotwin"
        resolved = (self._root / relative).resolve()
        try:
            resolved.relative_to(self._root)
        except ValueError:
            return None, "path must stay under resources/robotwin"
        return resolved, None

    @readonly
    def read_text_file(
        self,
        path: str,
        max_chars: int = MAX_RESOURCE_CHARS,
    ) -> dict[str, Any]:
        resolved, error = self._resolve(path)
        if error is not None:
            return {"error": error, "path": path}
        assert resolved is not None
        if not resolved.exists():
            return {"error": "file not found", "path": path}
        if not resolved.is_file():
            return {"error": "is not a file", "path": path}
        try:
            text = resolved.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return {"error": str(exc), "path": path}
        limit = min(max(1, int(max_chars)), MAX_RESOURCE_CHARS)
        return {
            "path": str(resolved.relative_to(self._root)),
            "size": len(text),
            "content": _truncate(text, limit),
        }

    @readonly
    def list_dir(self, path: str = ".") -> dict[str, Any]:
        resolved, error = self._resolve(path, allow_root=True)
        if error is not None:
            return {"error": error, "path": path}
        assert resolved is not None
        if not resolved.exists():
            return {"error": "directory not found", "path": path}
        if not resolved.is_dir():
            return {"error": "is not a directory", "path": path}
        entries = sorted(child.name for child in resolved.iterdir())
        relative = resolved.relative_to(self._root)
        return {
            "path": "." if str(relative) == "." else str(relative),
            "count": len(entries),
            "files": entries,
        }
