from __future__ import annotations

import unittest

from models import (
    normalize_completed_category_order,
    ordered_group_ids,
    reorder_pending_tasks_within_category_at_index,
    reorder_pending_tasks_within_category,
    reorder_records_by_id,
)


class ReorderingTests(unittest.TestCase):
    def test_reorder_records_by_id_moves_before_target(self) -> None:
        records = [{"id": "cat-1"}, {"id": "cat-2"}, {"id": "cat-3"}]

        reordered = reorder_records_by_id(records, "cat-3", "cat-1")

        self.assertEqual([record["id"] for record in reordered], ["cat-3", "cat-1", "cat-2"])
        self.assertEqual([record["id"] for record in records], ["cat-1", "cat-2", "cat-3"])

    def test_ordered_group_ids_uses_category_order_then_unknowns(self) -> None:
        categories = [{"id": "cat-2"}, {"id": "cat-1"}]

        ordered = ordered_group_ids(["cat-1", "missing", "cat-2"], categories)

        self.assertEqual(ordered, ["cat-2", "cat-1", "missing"])

    def test_completed_category_order_uses_preference_then_category_order(self) -> None:
        categories = [{"id": "cat-1"}, {"id": "cat-2"}, {"id": "cat-3"}]

        ordered = normalize_completed_category_order(["cat-3"], ["cat-1", "cat-2", "cat-3"], categories)

        self.assertEqual(ordered, ["cat-3", "cat-1", "cat-2"])

    def test_reorder_pending_tasks_within_category_preserves_other_tasks(self) -> None:
        tasks = [
            {"id": "done-1", "categoryId": "cat-1", "completed": True},
            {"id": "task-1", "categoryId": "cat-1", "completed": False},
            {"id": "other-1", "categoryId": "cat-2", "completed": False},
            {"id": "task-2", "categoryId": "cat-1", "completed": False},
            {"id": "task-3", "categoryId": "cat-1", "completed": False},
        ]

        reordered = reorder_pending_tasks_within_category(tasks, "cat-1", "task-3", "task-1")

        self.assertEqual(
            [task["id"] for task in reordered],
            ["done-1", "task-3", "other-1", "task-1", "task-2"],
        )

    def test_reorder_pending_tasks_within_category_at_index_moves_down_one_slot(self) -> None:
        tasks = [
            {"id": "task-1", "categoryId": "cat-1", "completed": False},
            {"id": "task-2", "categoryId": "cat-1", "completed": False},
            {"id": "task-3", "categoryId": "cat-1", "completed": False},
        ]

        reordered = reorder_pending_tasks_within_category_at_index(tasks, "cat-1", "task-1", 1)

        self.assertEqual([task["id"] for task in reordered], ["task-2", "task-1", "task-3"])

    def test_reorder_pending_tasks_within_category_at_index_moves_to_end(self) -> None:
        tasks = [
            {"id": "task-1", "categoryId": "cat-1", "completed": False},
            {"id": "task-2", "categoryId": "cat-1", "completed": False},
            {"id": "task-3", "categoryId": "cat-1", "completed": False},
        ]

        reordered = reorder_pending_tasks_within_category_at_index(tasks, "cat-1", "task-1", 2)

        self.assertEqual([task["id"] for task in reordered], ["task-2", "task-3", "task-1"])

    def test_reorder_pending_tasks_within_category_at_index_moves_up(self) -> None:
        tasks = [
            {"id": "task-1", "categoryId": "cat-1", "completed": False},
            {"id": "task-2", "categoryId": "cat-1", "completed": False},
            {"id": "task-3", "categoryId": "cat-1", "completed": False},
        ]

        reordered = reorder_pending_tasks_within_category_at_index(tasks, "cat-1", "task-3", 0)

        self.assertEqual([task["id"] for task in reordered], ["task-3", "task-1", "task-2"])

    def test_reorder_pending_tasks_within_category_at_index_preserves_other_tasks(self) -> None:
        tasks = [
            {"id": "done-1", "categoryId": "cat-1", "completed": True},
            {"id": "task-1", "categoryId": "cat-1", "completed": False},
            {"id": "other-1", "categoryId": "cat-2", "completed": False},
            {"id": "task-2", "categoryId": "cat-1", "completed": False},
            {"id": "task-3", "categoryId": "cat-1", "completed": False},
        ]

        reordered = reorder_pending_tasks_within_category_at_index(tasks, "cat-1", "task-1", 2)

        self.assertEqual(
            [task["id"] for task in reordered],
            ["done-1", "task-2", "other-1", "task-3", "task-1"],
        )

    def test_reorder_pending_tasks_within_category_at_index_ignores_invalid_input(self) -> None:
        tasks = [
            {"id": "task-1", "categoryId": "cat-1", "completed": False},
            {"id": "task-2", "categoryId": "cat-1", "completed": False},
        ]

        missing_task = reorder_pending_tasks_within_category_at_index(tasks, "cat-1", "missing", 0)
        invalid_index = reorder_pending_tasks_within_category_at_index(tasks, "cat-1", "task-1", 2)

        self.assertEqual(missing_task, tasks)
        self.assertEqual(invalid_index, tasks)


if __name__ == "__main__":
    unittest.main()
