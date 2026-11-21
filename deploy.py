"""Start guided SAM deployment using the saved dashboard settings."""

import argparse
from pathlib import Path
from subprocess import run

from app.local_projects import dashboard_timezone, project_ids


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--stack-name", default="trmnl-ticktick")
    parser.add_argument("--profile")
    options = parser.parse_args()
    try:
        ids = project_ids()
        zone = dashboard_timezone()
    except ValueError as error:
        parser.error(str(error))

    command = ["sam", "deploy", "--guided", "--confirm-changeset", "--region", options.region,
               "--stack-name", options.stack_name]
    if options.profile:
        command.extend(["--profile", options.profile])
    command.append("--parameter-overrides")
    for parameter, value in zip(("InboxId", "WorkListId", "TimeBlockingListId"), ids):
        command.append(f"ParameterKey={parameter},ParameterValue={value}")
    command.append(f"ParameterKey=DashboardTimezone,ParameterValue={zone.key}")

    try:
        return run(command, cwd=Path(__file__).resolve().parent, check=False).returncode
    except FileNotFoundError:
        parser.exit(1, "Install the AWS SAM CLI and make sure sam is on PATH.\n")


if __name__ == "__main__":
    raise SystemExit(main())
