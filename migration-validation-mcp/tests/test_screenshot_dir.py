"""Unit tests for keeping the screenshots directory screenshots-only."""

from migration_validation.services.screenshot_dir import ScreenshotDirCleaner


def test_missing_screenshots_dir_is_a_no_op(tmp_path):
    cleaner = ScreenshotDirCleaner(
        screenshots_dir=tmp_path / "validation-screenshots",
        debug_artifacts_dir=tmp_path / "playwright-debug",
    )
    assert cleaner.sweep() == []


def test_images_are_left_in_place(tmp_path):
    screenshots_dir = tmp_path / "validation-screenshots"
    screenshots_dir.mkdir()
    (screenshots_dir / "20260715_120000_tableau-full.png").write_bytes(b"fake-png")
    (screenshots_dir / "20260715_120000_pbi.jpg").write_bytes(b"fake-jpg")

    cleaner = ScreenshotDirCleaner(screenshots_dir, tmp_path / "playwright-debug")
    moved = cleaner.sweep()

    assert moved == []
    assert (screenshots_dir / "20260715_120000_tableau-full.png").exists()
    assert (screenshots_dir / "20260715_120000_pbi.jpg").exists()


def test_non_image_files_are_relocated(tmp_path):
    screenshots_dir = tmp_path / "validation-screenshots"
    screenshots_dir.mkdir()
    (screenshots_dir / "console-2026.log").write_text("log contents")
    (screenshots_dir / "page-2026.yml").write_text("yaml contents")
    (screenshots_dir / "keep-me.png").write_bytes(b"fake-png")

    debug_dir = tmp_path / "playwright-debug"
    cleaner = ScreenshotDirCleaner(screenshots_dir, debug_dir)
    moved = cleaner.sweep()

    assert sorted(moved) == ["console-2026.log", "page-2026.yml"]
    assert not (screenshots_dir / "console-2026.log").exists()
    assert not (screenshots_dir / "page-2026.yml").exists()
    assert (screenshots_dir / "keep-me.png").exists()
    assert (debug_dir / "console-2026.log").read_text() == "log contents"
    assert (debug_dir / "page-2026.yml").read_text() == "yaml contents"


def test_sweep_is_idempotent(tmp_path):
    screenshots_dir = tmp_path / "validation-screenshots"
    screenshots_dir.mkdir()
    (screenshots_dir / "stray.log").write_text("x")

    cleaner = ScreenshotDirCleaner(screenshots_dir, tmp_path / "playwright-debug")
    first = cleaner.sweep()
    second = cleaner.sweep()

    assert first == ["stray.log"]
    assert second == []
