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

## Data Folder Settings

The app can use a custom folder for `tasks.json`. That preference is saved in a user settings file, so different copies of the app may read the same configured data folder if they use the same application name.

For development or for keeping two local copies isolated, create this marker file in the copy that should use project-local settings:

```bash
touch .mini-task-manager-dev
```

When the marker exists, settings are stored in `.dev-settings/settings.json` inside that project folder. Both `.mini-task-manager-dev` and `.dev-settings/` are ignored by Git.

You can also override the settings location explicitly:

```bash
MINI_TASK_MANAGER_SETTINGS_DIR=/path/to/settings python main.py
```

## Tests

```bash
python -m unittest discover -s tests
```
