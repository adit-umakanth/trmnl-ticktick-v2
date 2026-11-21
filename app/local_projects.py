"""Load project IDs and the dashboard time zone for local checks and deployment."""

from os import environ
from pathlib import Path
from re import fullmatch
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

PROJECT_ID_NAMES = ("TICKTICK_INBOX_ID", "TICKTICK_WORK_LIST_ID", "TICKTICK_TIME_BLOCKING_LIST_ID")
TIMEZONE_NAME = "DASHBOARD_TIMEZONE"
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def _file_settings():
    try:
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeError):
        raise ValueError("Could not read the repository's .env file") from None

    values = {}
    for line in lines:
        name, _, value = line.partition("#")[0].partition("=")
        name, value = name.strip(), value.strip()
        if name in (*PROJECT_ID_NAMES, TIMEZONE_NAME):
            if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
                value = value[1:-1]
            values[name] = value
    return values


def project_ids(overrides=()):
    explicit = dict(zip(PROJECT_ID_NAMES, overrides))
    values = [explicit.get(name) or environ.get(name, "").strip() for name in PROJECT_ID_NAMES]
    if not all(values):
        defaults = _file_settings()
        values = [value or defaults.get(name, "") for name, value in zip(PROJECT_ID_NAMES, values)]

    missing = [name for name, value in zip(PROJECT_ID_NAMES, values) if not value]
    if missing:
        raise ValueError("Set " + ", ".join(missing) + " in .env or the environment")
    for name, value in zip(PROJECT_ID_NAMES, values):
        if not fullmatch(r"[A-Za-z0-9_-]+", value):
            raise ValueError(f"Invalid {name}; use only letters, digits, underscores, or hyphens")
    return tuple(values)


def dashboard_timezone(override=None):
    value = override or environ.get(TIMEZONE_NAME, "").strip()
    if not value:
        value = _file_settings().get(TIMEZONE_NAME, "")
    if not value:
        raise ValueError(f"Set {TIMEZONE_NAME} in .env or the environment")
    try:
        return ZoneInfo(value)
    except (ValueError, ZoneInfoNotFoundError):
        raise ValueError(f"Invalid {TIMEZONE_NAME}; use a valid IANA time zone") from None
