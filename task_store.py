"""JSON persistence for Mini Task Manager."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from models import DEFAULT_DATA, DataRecord


class TaskStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def load(self) -> DataRecord:
        try:
            with self.path.open("r", encoding="utf-8") as file:
                data = json.load(file)
            if not isinstance(data, dict):
                raise ValueError("tasks.json must contain an object")
            return {
                "tasks": self._list_or_empty(data.get("tasks")),
                "categories": self._list_or_empty(data.get("categories")),
                "completedCategoryOrder": self._string_list_or_empty(data.get("completedCategoryOrder")),
            }
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            default = self.default_data()
            self.save(default)
            return default

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

    @staticmethod
    def default_data() -> DataRecord:
        return copy.deepcopy(DEFAULT_DATA)

    @staticmethod
    def _list_or_empty(value: Any) -> list[dict[str, Any]]:
        return value if isinstance(value, list) else []

    @staticmethod
    def _string_list_or_empty(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str)]
