"""Application path and settings helpers."""

from __future__ import annotations

import copy
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from PyQt6.QtCore import QStandardPaths

from models import DataRecord
from task_store import TaskStore


APP_NAME = "Mini Task Manager"
SETTINGS_FILENAME = "settings.json"
TASKS_FILENAME = "tasks.json"
DATA_DIR_KEY = "dataDir"
SETTINGS_DIR_ENV = "MINI_TASK_MANAGER_SETTINGS_DIR"
DEV_SETTINGS_MARKER = ".mini-task-manager-dev"
DEV_SETTINGS_DIRNAME = ".dev-settings"


@dataclass(frozen=True)
class PreparedDataFile:
    data: DataRecord
    created: bool


def application_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


class AppPaths:
    def __init__(self, program_dir: Path | str, settings_dir: Path | str | None = None) -> None:
        self.program_dir = Path(program_dir)
        self._settings_dir = Path(settings_dir) if settings_dir is not None else None

    @property
    def settings_dir(self) -> Path:
        if self._settings_dir is not None:
            return self._settings_dir

        env_settings_dir = os.environ.get(SETTINGS_DIR_ENV)
        if env_settings_dir and env_settings_dir.strip():
            return Path(env_settings_dir).expanduser()

        dev_settings_dir = self.local_dev_settings_dir()
        if dev_settings_dir is not None:
            return dev_settings_dir

        location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
        if location:
            return Path(location)
        return Path.home() / ".config" / APP_NAME

    def local_dev_settings_dir(self) -> Path | None:
        if (self.program_dir / DEV_SETTINGS_MARKER).exists():
            return self.program_dir / DEV_SETTINGS_DIRNAME
        return None

    @property
    def settings_file(self) -> Path:
        return self.settings_dir / SETTINGS_FILENAME

    @property
    def default_data_file(self) -> Path:
        return self.program_dir / TASKS_FILENAME

    def active_data_file(self) -> Path:
        custom_dir = self.custom_data_dir()
        if custom_dir is not None:
            return custom_dir / TASKS_FILENAME
        return self.default_data_file

    def custom_data_dir(self) -> Path | None:
        value = self.load_settings().get(DATA_DIR_KEY)
        if not isinstance(value, str) or not value.strip():
            return None

        path = Path(value).expanduser()
        if not path.is_dir():
            return None
        return path

    def load_settings(self) -> dict[str, Any]:
        try:
            with self.settings_file.open("r", encoding="utf-8") as file:
                data = json.load(file)
            if isinstance(data, dict):
                return data
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass
        return {}

    def save_custom_data_dir(self, data_dir: Path | str) -> None:
        path = Path(data_dir).expanduser()
        if not path.is_dir():
            raise NotADirectoryError(str(path))

        settings = self.load_settings()
        settings[DATA_DIR_KEY] = str(path.resolve())
        self.settings_dir.mkdir(parents=True, exist_ok=True)
        with self.settings_file.open("w", encoding="utf-8") as file:
            json.dump(settings, file, ensure_ascii=False, indent=2)


def prepare_data_file(data_file: Path | str, current_data: DataRecord) -> PreparedDataFile:
    path = Path(data_file)
    store = TaskStore(path)
    if path.exists():
        return PreparedDataFile(store.load(), created=False)

    data_copy = cast(DataRecord, copy.deepcopy(current_data))
    store.save(data_copy)
    return PreparedDataFile(data_copy, created=True)
