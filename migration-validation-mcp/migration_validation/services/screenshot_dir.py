"""Keeps the screenshots directory screenshots-only.

Playwright MCP's ``--output-dir`` is shared by every browser tool that
accepts an optional ``filename`` — not just ``browser_take_screenshot``.
If the agent ever passes a filename to ``browser_console_messages``,
``browser_snapshot``, or ``browser_network_request``, those files land in
the same folder as the screenshots. The playbook instructs the agent not to
do this, but prose-only compliance has proven unreliable in practice, so
this sweep is the deterministic backstop: anything that isn't an image gets
moved out, not just relied on to never appear.
"""

from pathlib import Path

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


class ScreenshotDirCleaner:
    """Moves non-image files out of the screenshots directory."""

    def __init__(self, screenshots_dir: Path, debug_artifacts_dir: Path) -> None:
        self.screenshots_dir = screenshots_dir
        self.debug_artifacts_dir = debug_artifacts_dir

    def sweep(self) -> list[str]:
        """Relocate any non-image file out of ``screenshots_dir``.

        Returns the names of files moved. A missing screenshots directory
        (no run has taken a screenshot yet) is not an error — nothing to do.
        """
        if not self.screenshots_dir.exists():
            return []

        moved: list[str] = []
        for entry in self.screenshots_dir.iterdir():
            if entry.is_file() and entry.suffix.lower() not in _IMAGE_EXTENSIONS:
                self.debug_artifacts_dir.mkdir(parents=True, exist_ok=True)
                entry.replace(self.debug_artifacts_dir / entry.name)
                moved.append(entry.name)
        return moved
