#!/usr/bin/env python3
"""Mini Task Manager desktop entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from main_window import MainWindow


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "tasks.json"


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Mini Task Manager")

    window = MainWindow(DATA_FILE)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
