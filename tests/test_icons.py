from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from icons import icon_path, material_icon, material_pixmap


class MaterialIconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_known_icon_path_resolves(self) -> None:
        self.assertEqual(icon_path("menu_book").name, "menu_book.svg")

    def test_data_folder_icon_path_resolves(self) -> None:
        self.assertEqual(icon_path("folder_open").name, "folder_open.svg")

    def test_unknown_icon_falls_back_to_label(self) -> None:
        self.assertEqual(icon_path("missing_icon_name").name, "label.svg")

    def test_material_icon_is_not_null(self) -> None:
        self.assertFalse(material_icon("work", "#735a3b", 24).isNull())

    def test_tinted_pixmap_contains_requested_color(self) -> None:
        pixmap = material_pixmap("work", "#735a3b", 24)
        image = pixmap.toImage()

        found_colored_pixel = False
        for y in range(image.height()):
            for x in range(image.width()):
                color = image.pixelColor(x, y)
                if color.alpha() > 0:
                    self.assertLessEqual(abs(color.red() - 0x73), 1)
                    self.assertLessEqual(abs(color.green() - 0x5A), 1)
                    self.assertLessEqual(abs(color.blue() - 0x3B), 1)
                    found_colored_pixel = True
                    break
            if found_colored_pixel:
                break

        self.assertTrue(found_colored_pixel)


if __name__ == "__main__":
    unittest.main()
