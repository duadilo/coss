"""Persistent memory store using OPENCODE.md files."""

from __future__ import annotations

from pathlib import Path

from opencode.config.constants import (
    GLOBAL_CONFIG_DIR,
    PROJECT_MEMORY_FILE_NAME,
)


class MemoryStore:
    """
    Reads and writes OPENCODE.md files:
    - Global: ~/.opencode/OPENCODE.md
    - Project: <project_root>/OPENCODE.md

    These files contain persistent instructions/context that gets
    injected into the system prompt every session.
    """

    def __init__(self, project_root: str | None = None) -> None:
        self._global_path = GLOBAL_CONFIG_DIR / "OPENCODE.md"
        self._project_root = Path(project_root) if project_root else self._find_project_root()
        self._project_path = (
            self._project_root / PROJECT_MEMORY_FILE_NAME if self._project_root else None
        )

    @property
    def global_path(self) -> Path:
        return self._global_path

    @property
    def project_path(self) -> Path | None:
        return self._project_path

    def read_global(self) -> str | None:
        """Read global memory file."""
        return self._read_file(self._global_path)

    def read_project(self) -> str | None:
        """Read project-level memory file."""
        if self._project_path:
            return self._read_file(self._project_path)
        return None

    def write_global(self, content: str) -> None:
        """Write to global memory file."""
        self._global_path.parent.mkdir(parents=True, exist_ok=True)
        self._global_path.write_text(content)

    def write_project(self, content: str) -> None:
        """Write to project-level memory file."""
        if self._project_path:
            self._project_path.parent.mkdir(parents=True, exist_ok=True)
            self._project_path.write_text(content)

    def _read_file(self, path: Path) -> str | None:
        if path.exists() and path.is_file():
            try:
                content = path.read_text()
                return content if content.strip() else None
            except (PermissionError, OSError):
                return None
        return None

    def _find_project_root(self) -> Path | None:
        """Walk up from cwd looking for git root or OPENCODE.md."""
        current = Path.cwd()
        while True:
            # Check for git repo
            if (current / ".git").exists():
                return current
            # Check for OPENCODE.md
            if (current / PROJECT_MEMORY_FILE_NAME).exists():
                return current
            parent = current.parent
            if parent == current:
                break
            current = parent
        # Fall back to cwd
        return Path.cwd()
