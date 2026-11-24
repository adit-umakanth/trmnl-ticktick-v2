"""Render a synthetic dashboard or outage image without AWS or TickTick."""

import argparse
from pathlib import Path

from dashboard import TaskRow, TimeBlock, render


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--outage", action="store_true")
    parser.add_argument("--after-hours", action="store_true", help="Show the expanded Todos layout")
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
    ))


if __name__ == "__main__":
    main()
