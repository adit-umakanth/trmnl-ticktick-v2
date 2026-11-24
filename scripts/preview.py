"""Render a synthetic dashboard, outage, or sleep image without AWS or TickTick."""

import argparse
from datetime import datetime
from pathlib import Path

from dashboard import TaskRow, TimeBlock, render


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    layout = parser.add_mutually_exclusive_group()
    layout.add_argument("--outage", action="store_true")
    layout.add_argument("--after-hours", action="store_true", help="Show the expanded Todos layout")
    layout.add_argument("--sleep", action="store_true", help="Show the overnight sleep screen")
    options = parser.parse_args()
    options.output.write_bytes(render(
        [TaskRow("Todo 1"), TaskRow("Todo 2"),
         TaskRow("Todo 3 with checklist", ("Checklist item A", "Checklist item B")),
         *(TaskRow(f"Todo {index}") for index in range(4, 11))],
        None if options.after_hours else [TaskRow(f"Work task {index}") for index in range(1, 6)],
        ["Habit 1", "Habit 2", "Habit 3"],
        TimeBlock("Sample block A", "4:00pm - 5:30pm"),
        TimeBlock("Sample block B", "5:30pm - 6:15pm"),
        outage=options.outage,
        sleep_until=datetime(2026, 11, 24, 7) if options.sleep else None,
    ))


if __name__ == "__main__":
    main()
