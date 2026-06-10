from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication, QPushButton

from app_paths import AppPaths
from main_window import MainWindow


class MainWindowTaskPopupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_task_combo_popups_use_custom_popup_without_native_scrollers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_file = root / "tasks.json"
            data_file.write_text(
                json.dumps(
                    {
                        "tasks": [],
                        "categories": [
                            {"id": "cat-1", "name": "Prueba", "color": "#68abff", "icon": "school"}
                        ],
                        "completedCategoryOrder": [],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            window = MainWindow(data_file, AppPaths(root, root / "settings"))

            try:
                window.show()
                self.app.processEvents()

                for combo in (window.taskCategoryCombo, window.taskPriorityCombo):
                    controller = combo._task_combo_popup_controller
                    controller.show_popup()
                    self.app.processEvents()

                    popup = controller.popup
                    self.assertIsNotNone(popup)
                    self.assertEqual(popup.objectName(), "taskComboPopup")
                    option_buttons = popup.findChildren(QPushButton, "taskComboPopupOption")
                    self.assertEqual(popup.findChildren(QPushButton), option_buttons)
                    self.assertEqual(len(option_buttons), combo.count())

                    popup.close()
                    self.app.processEvents()
            finally:
                window.close()

    def test_task_combo_popup_selection_updates_combo(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_file = root / "tasks.json"
            data_file.write_text(
                json.dumps({"tasks": [], "categories": [], "completedCategoryOrder": []}),
                encoding="utf-8",
            )
            window = MainWindow(data_file, AppPaths(root, root / "settings"))

            try:
                controller = window.taskPriorityCombo._task_combo_popup_controller
                controller.show_popup()
                self.app.processEvents()

                popup = controller.popup
                self.assertIsNotNone(popup)
                popup.select_index(window.taskPriorityCombo.findData("Alta"))
                self.app.processEvents()

                self.assertEqual(window.taskPriorityCombo.currentData(), "Alta")
                self.assertIsNone(controller.popup)
            finally:
                window.close()

    def test_task_combo_double_click_is_intercepted_by_custom_popup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_file = root / "tasks.json"
            data_file.write_text(
                json.dumps({"tasks": [], "categories": [], "completedCategoryOrder": []}),
                encoding="utf-8",
            )
            window = MainWindow(data_file, AppPaths(root, root / "settings"))

            try:
                combo = window.taskPriorityCombo
                controller = combo._task_combo_popup_controller
                event = QMouseEvent(
                    QEvent.Type.MouseButtonDblClick,
                    QPointF(4, 4),
                    Qt.MouseButton.LeftButton,
                    Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier,
                )

                handled = controller.eventFilter(combo, event)

                self.assertTrue(handled)
                self.assertIsNotNone(controller.popup)
            finally:
                window.close()


if __name__ == "__main__":
    unittest.main()
