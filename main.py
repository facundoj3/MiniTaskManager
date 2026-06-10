#!/usr/bin/env python3
"""Mini Task Manager desktop entrypoint."""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from app_paths import APP_NAME, AppPaths, application_dir
from main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    paths = AppPaths(application_dir())
    window = MainWindow(paths.active_data_file(), paths)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
