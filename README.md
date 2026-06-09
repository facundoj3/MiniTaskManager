# Mini Task Manager

Mini Task Manager is a native desktop task manager built with Python and PyQt6.

## Requirements

- Python 3.12 or newer
- PyQt6

## Setup

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

The app stores local user data in `tasks.json`. That file is private, ignored by Git, and created automatically with an empty task list if it does not exist.

## Tests

```bash
python -m unittest discover -s tests
```
