"""Load the TickTick token for the opt-in live test."""

from os import environ
from subprocess import run
from sys import platform


def local_ticktick_token():
    token = environ.get("TICKTICK_TOKEN", "").strip()
    if token or platform != "darwin":
        return token

    try:
        result = run(
            ["/usr/bin/security", "find-generic-password", "-s", "trmnl-ticktick",
             "-a", "ticktick", "-w"],
            capture_output=True, text=True, check=False,
        )
    except OSError:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""
