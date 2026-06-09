"""Shared task/category constants and small helpers."""

from __future__ import annotations

from typing import Any, TypedDict


TaskRecord = dict[str, Any]
CategoryRecord = dict[str, Any]


class DataRecord(TypedDict):
    tasks: list[TaskRecord]
    categories: list[CategoryRecord]
    completedCategoryOrder: list[str]


DEFAULT_DATA: DataRecord = {"tasks": [], "categories": [], "completedCategoryOrder": []}

PRIORITIES = ("Baja", "Media", "Alta")
DEFAULT_PRIORITY = "Media"

AVAILABLE_ICONS = (
    "label",
    "star",
    "bookmark",
    "work",
    "laptop_mac",
    "business_center",
    "school",
    "menu_book",
    "edit_document",
    "home",
    "person",
    "favorite",
    "shopping_cart",
    "fitness_center",
    "restaurant",
    "flight",
    "palette",
    "sports_esports",
    "music_note",
    "savings",
    "attach_money",
    "analytics",
    "auto_graph",
    "bar_chart",
    "account_balance",
    "trending_up",
    "how_to_vote",
)

ICON_LABELS = {
    "label": "Tag",
    "star": "Star",
    "bookmark": "Mark",
    "work": "Work",
    "laptop_mac": "Mac",
    "business_center": "Brief",
    "school": "School",
    "menu_book": "Book",
    "edit_document": "Doc",
    "home": "Home",
    "person": "User",
    "favorite": "Fav",
    "shopping_cart": "Cart",
    "fitness_center": "Fit",
    "restaurant": "Food",
    "flight": "Trip",
    "palette": "Art",
    "sports_esports": "Game",
    "music_note": "Music",
    "savings": "Save",
    "attach_money": "Money",
    "analytics": "Data",
    "auto_graph": "Graph",
    "bar_chart": "Chart",
    "account_balance": "Bank",
    "trending_up": "Trend",
    "how_to_vote": "Vote",
}

UNKNOWN_CATEGORY: CategoryRecord = {
    "id": "",
    "name": "Sin categoría",
    "color": "#8b7d6b",
    "icon": "label",
}


def icon_label(icon_name: str | None) -> str:
    if not icon_name:
        return ICON_LABELS["label"]
    return ICON_LABELS.get(icon_name, icon_name.replace("_", " ").title()[:12])


def get_category(categories: list[CategoryRecord], category_id: str | None) -> CategoryRecord:
    for category in categories:
        if category.get("id") == category_id:
            return category
    return UNKNOWN_CATEGORY.copy()


def record_id(record: dict[str, Any]) -> str:
    return str(record.get("id", ""))


def reorder_records_by_id(records: list[dict[str, Any]], moved_id: str, target_id: str) -> list[dict[str, Any]]:
    if moved_id == target_id:
        return records[:]

    moved_index = _index_by_id(records, moved_id)
    target_index = _index_by_id(records, target_id)
    if moved_index is None or target_index is None:
        return records[:]

    reordered = records[:]
    moved = reordered.pop(moved_index)
    target_index = _index_by_id(reordered, target_id)
    if target_index is None:
        return records[:]
    reordered.insert(target_index, moved)
    return reordered


def reorder_pending_tasks_within_category(
    tasks: list[TaskRecord],
    category_id: str,
    moved_id: str,
    target_id: str,
) -> list[TaskRecord]:
    pending_category_tasks = [
        task
        for task in tasks
        if not task.get("completed") and str(task.get("categoryId", "")) == category_id
    ]
    reordered_pending = reorder_records_by_id(pending_category_tasks, moved_id, target_id)
    if reordered_pending == pending_category_tasks:
        return tasks[:]

    reordered_iter = iter(reordered_pending)
    result: list[TaskRecord] = []
    for task in tasks:
        if not task.get("completed") and str(task.get("categoryId", "")) == category_id:
            result.append(next(reordered_iter))
        else:
            result.append(task)
    return result


def ordered_group_ids(
    grouped_ids: list[str],
    categories: list[CategoryRecord],
    preferred_order: list[str] | None = None,
) -> list[str]:
    remaining = list(dict.fromkeys(grouped_ids))
    ordered: list[str] = []
    for category_id in preferred_order or [record_id(category) for category in categories]:
        if category_id in remaining:
            ordered.append(category_id)
            remaining.remove(category_id)

    if preferred_order is not None:
        for category in categories:
            category_id = record_id(category)
            if category_id in remaining:
                ordered.append(category_id)
                remaining.remove(category_id)

    ordered.extend(remaining)
    return ordered


def normalize_completed_category_order(
    current_order: list[str],
    completed_group_ids: list[str],
    categories: list[CategoryRecord],
) -> list[str]:
    return ordered_group_ids(completed_group_ids, categories, current_order)


def _index_by_id(records: list[dict[str, Any]], item_id: str) -> int | None:
    for index, record in enumerate(records):
        if record_id(record) == item_id:
            return index
    return None
