from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from task_store import TaskStore


class TaskStoreTests(unittest.TestCase):
    def test_missing_file_creates_default_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tasks.json"
            data = TaskStore(path).load()

            self.assertEqual(data, {"tasks": [], "categories": [], "completedCategoryOrder": []})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), data)

    def test_corrupt_file_resets_default_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tasks.json"
            path.write_text("{bad json", encoding="utf-8")

            data = TaskStore(path).load()

            self.assertEqual(data, {"tasks": [], "categories": [], "completedCategoryOrder": []})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), data)

    def test_existing_records_without_completed_order_load_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tasks.json"
            original = {
                "tasks": [
                    {
                        "id": "task-1",
                        "title": "Leer",
                        "categoryId": "cat-1",
                        "priority": "Alta",
                        "completed": True,
                        "completedAt": "2026-05-12T01:51:48.363Z",
                    }
                ],
                "categories": [
                    {
                        "id": "cat-1",
                        "name": "Estudio",
                        "color": "#3584e4",
                        "icon": "menu_book",
                    }
                ],
            }
            path.write_text(json.dumps(original, ensure_ascii=False, indent=2), encoding="utf-8")
            store = TaskStore(path)

            loaded = store.load()
            store.save(loaded)

            expected = {**original, "completedCategoryOrder": []}
            self.assertEqual(loaded, expected)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), expected)

    def test_existing_completed_order_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tasks.json"
            original = {
                "tasks": [],
                "categories": [{"id": "cat-1", "name": "Estudio", "color": "#3584e4", "icon": "menu_book"}],
                "completedCategoryOrder": ["cat-1"],
            }
            path.write_text(json.dumps(original, ensure_ascii=False, indent=2), encoding="utf-8")
            store = TaskStore(path)

            loaded = store.load()
            store.save(loaded)

            self.assertEqual(loaded, original)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), original)


if __name__ == "__main__":
    unittest.main()
