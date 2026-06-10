from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox

from app_paths import AppPaths
from main_window import MainWindow


class MainWindowDataFolderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.original_get_existing_directory = QFileDialog.getExistingDirectory
        self.original_information = QMessageBox.information
        self.original_warning = QMessageBox.warning
        self.original_critical = QMessageBox.critical

        QMessageBox.information = staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
        QMessageBox.warning = staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
        QMessageBox.critical = staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Ok)

    def tearDown(self) -> None:
        QFileDialog.getExistingDirectory = self.original_get_existing_directory
        QMessageBox.information = self.original_information
        QMessageBox.warning = self.original_warning
        QMessageBox.critical = self.original_critical

    def test_change_data_folder_removes_old_file_when_target_is_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            old_dir = root / "old"
            new_dir = root / "new"
            settings_dir = root / "settings"
            old_dir.mkdir()
            new_dir.mkdir()
            old_file = old_dir / "tasks.json"
            new_file = new_dir / "tasks.json"
            current_data = {
                "tasks": [{"id": "task-1", "title": "Leer", "categoryId": "cat-1", "priority": "Media"}],
                "categories": [{"id": "cat-1", "name": "Estudio", "color": "#3584e4", "icon": "menu_book"}],
                "completedCategoryOrder": [],
            }
            old_file.write_text(json.dumps(current_data, ensure_ascii=False, indent=2), encoding="utf-8")
            QFileDialog.getExistingDirectory = staticmethod(lambda *args, **kwargs: str(new_dir))
            window = MainWindow(old_file, AppPaths(old_dir, settings_dir))

            try:
                window.change_data_folder()

                self.assertFalse(old_file.exists())
                self.assertEqual(json.loads(new_file.read_text(encoding="utf-8")), current_data)
                self.assertEqual(window.store.path, new_file)
                settings = json.loads((settings_dir / "settings.json").read_text(encoding="utf-8"))
                self.assertEqual(settings["dataDir"], str(new_dir.resolve()))
            finally:
                window.close()

    def test_change_data_folder_keeps_old_file_when_target_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            old_dir = root / "old"
            new_dir = root / "new"
            settings_dir = root / "settings"
            old_dir.mkdir()
            new_dir.mkdir()
            old_file = old_dir / "tasks.json"
            new_file = new_dir / "tasks.json"
            old_data = {
                "tasks": [{"id": "task-old", "title": "Vieja", "categoryId": "", "priority": "Media"}],
                "categories": [],
                "completedCategoryOrder": [],
            }
            new_data = {
                "tasks": [{"id": "task-new", "title": "Nueva", "categoryId": "", "priority": "Alta"}],
                "categories": [],
                "completedCategoryOrder": [],
            }
            old_file.write_text(json.dumps(old_data, ensure_ascii=False, indent=2), encoding="utf-8")
            new_file.write_text(json.dumps(new_data, ensure_ascii=False, indent=2), encoding="utf-8")
            QFileDialog.getExistingDirectory = staticmethod(lambda *args, **kwargs: str(new_dir))
            window = MainWindow(old_file, AppPaths(old_dir, settings_dir))

            try:
                window.change_data_folder()

                self.assertTrue(old_file.exists())
                self.assertEqual(json.loads(old_file.read_text(encoding="utf-8")), old_data)
                self.assertEqual(json.loads(new_file.read_text(encoding="utf-8")), new_data)
                self.assertEqual(window.tasks, new_data["tasks"])
                self.assertEqual(window.store.path, new_file)
            finally:
                window.close()


if __name__ == "__main__":
    unittest.main()
