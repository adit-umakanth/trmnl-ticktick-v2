"""Run the live read-only integration check from a private terminal."""

import argparse
from datetime import datetime
from getpass import GetPassWarning, getpass
from warnings import catch_warnings, simplefilter

from local_credentials import local_ticktick_token
from local_projects import dashboard_timezone, project_ids
from ticktick import TickTick, TickTickError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inbox_id", nargs="?", help="override the saved Inbox project ID")
    parser.add_argument("work_list_id", nargs="?", help="override the saved Work project ID")
    parser.add_argument("time_blocking_list_id", nargs="?", help="override the saved Time Blocking project ID")
    parser.add_argument("--timezone", help="override the saved dashboard time zone")
    parser.add_argument("--show-titles", action="store_true",
                        help="Print private titles for comparison in your own terminal")
    options = parser.parse_args()
    try:
        ids = project_ids((options.inbox_id, options.work_list_id, options.time_blocking_list_id))
        zone = dashboard_timezone(options.timezone)
    except ValueError as error:
        parser.error(str(error))
    token = local_ticktick_token()
    if not token:
        with catch_warnings():
            simplefilter("error", GetPassWarning)
            try:
                token = getpass("TickTick access token: ").strip()
            except (GetPassWarning, EOFError):
                parser.exit(1, "Load the TickTick token from Keychain or TICKTICK_TOKEN.\n")
    if not token:
        parser.exit(1, "A TickTick token is required.\n")
    try:
        inbox, work, habits, current, upcoming = TickTick(token).dashboard(
            *ids, datetime.now(zone),
        )
    except TickTickError as error:
        parser.exit(1, f"TickTick verification failed ({error}).\n")
    for label, items in (("Inbox", inbox), ("Work", work), ("Habits", habits)):
        print(f"{label}: {len(items)} eligible rows")
        if options.show_titles:
            for item in items:
                print(f"  {item if isinstance(item, str) else item.title}")
    for label, block in (("Current block", current), ("Upcoming block", upcoming)):
        print(f"{label}: {'present' if block else 'empty'}")
        if options.show_titles and block:
            print(f"  {block.title} ({block.hours})")


if __name__ == "__main__":
    main()
