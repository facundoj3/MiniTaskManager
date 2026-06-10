from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app_paths import DEV_SETTINGS_DIRNAME, DEV_SETTINGS_MARKER, SETTINGS_DIR_ENV, AppPaths, prepare_data_file


class AppPathsTests(unittest.TestCase):
    def test_active_data_file_defaults_to_program_dir(self) -> None:
        with tempfile.TemporaryDirectory() as program_dir, tempfile.TemporaryDirectory() as settings_dir:
            paths = AppPaths(program_dir, settings_dir)

            self.assertEqual(paths.active_data_file(), Path(program_dir) / "tasks.json")

    def test_save_custom_data_dir_updates_active_data_file(self) -> None:
        with (
            tempfile.TemporaryDirectory() as program_dir,
            tempfile.TemporaryDirectory() as settings_dir,
            tempfile.TemporaryDirectory() as custom_dir,
        ):
            paths = AppPaths(program_dir, settings_dir)

            paths.save_custom_data_dir(custom_dir)

            self.assertEqual(paths.active_data_file(), Path(custom_dir) / "tasks.json")
            settings = json.loads(paths.settings_file.read_text(encoding="utf-8"))
            self.assertEqual(settings["dataDir"], str(Path(custom_dir).resolve()))

    def test_invalid_settings_falls_back_to_program_dir(self) -> None:
        with tempfile.TemporaryDirectory() as program_dir, tempfile.TemporaryDirectory() as settings_dir:
            paths = AppPaths(program_dir, settings_dir)
            paths.settings_file.write_text("{bad json", encoding="utf-8")

            self.assertEqual(paths.active_data_file(), Path(program_dir) / "tasks.json")

    def test_missing_custom_dir_falls_back_to_program_dir(self) -> None:
        with tempfile.TemporaryDirectory() as program_dir, tempfile.TemporaryDirectory() as settings_dir:
            paths = AppPaths(program_dir, settings_dir)
            missing_dir = Path(settings_dir) / "missing"
            paths.settings_file.write_text(
                json.dumps({"dataDir": str(missing_dir)}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            self.assertEqual(paths.active_data_file(), Path(program_dir) / "tasks.json")

    def test_settings_dir_env_overrides_qstandardpaths(self) -> None:
        with tempfile.TemporaryDirectory() as program_dir, tempfile.TemporaryDirectory() as settings_dir:
            with patch.dict(os.environ, {SETTINGS_DIR_ENV: settings_dir}):
                paths = AppPaths(program_dir)

                self.assertEqual(paths.settings_dir, Path(settings_dir))

    def test_explicit_settings_dir_overrides_env(self) -> None:
        with (
            tempfile.TemporaryDirectory() as program_dir,
            tempfile.TemporaryDirectory() as explicit_settings_dir,
            tempfile.TemporaryDirectory() as env_settings_dir,
        ):
            with patch.dict(os.environ, {SETTINGS_DIR_ENV: env_settings_dir}):
                paths = AppPaths(program_dir, explicit_settings_dir)

                self.assertEqual(paths.settings_dir, Path(explicit_settings_dir))

    def test_local_dev_marker_uses_project_dev_settings_dir(self) -> None:
        with tempfile.TemporaryDirectory() as program_dir:
            Path(program_dir, DEV_SETTINGS_MARKER).write_text("dev", encoding="utf-8")
            with patch.dict(os.environ, {SETTINGS_DIR_ENV: ""}):
                paths = AppPaths(program_dir)

                self.assertEqual(paths.settings_dir, Path(program_dir) / DEV_SETTINGS_DIRNAME)


class PrepareDataFileTests(unittest.TestCase):
    def test_missing_tasks_file_copies_current_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            data_file = Path(tmpdir) / "tasks.json"
            current_data = {
                "tasks": [{"id": "task-1", "title": "Leer", "categoryId": "cat-1", "priority": "Media"}],
                "categories": [{"id": "cat-1", "name": "Estudio", "color": "#3584e4", "icon": "menu_book"}],
                "completedCategoryOrder": [],
            }

            prepared = prepare_data_file(data_file, current_data)

            self.assertEqual(prepared.data, current_data)
            self.assertTrue(prepared.created)
            self.assertEqual(json.loads(data_file.read_text(encoding="utf-8")), current_data)

    def test_existing_tasks_file_loads_without_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            data_file = Path(tmpdir) / "tasks.json"
            existing_data = {
                "tasks": [{"id": "task-2", "title": "Escribir", "categoryId": "cat-2", "priority": "Alta"}],
                "categories": [{"id": "cat-2", "name": "Trabajo", "color": "#735a3b", "icon": "work"}],
                "completedCategoryOrder": ["cat-2"],
            }
            current_data = {"tasks": [], "categories": [], "completedCategoryOrder": []}
            data_file.write_text(json.dumps(existing_data, ensure_ascii=False, indent=2), encoding="utf-8")

            prepared = prepare_data_file(data_file, current_data)

            self.assertEqual(prepared.data, existing_data)
            self.assertFalse(prepared.created)
            self.assertEqual(json.loads(data_file.read_text(encoding="utf-8")), existing_data)


if __name__ == "__main__":
    unittest.main()
