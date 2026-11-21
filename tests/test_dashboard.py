import unittest
from datetime import date, datetime
from io import BytesIO
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw

from dashboard import TaskRow, TimeBlock, fit, habit_titles, render, task_rows, time_blocks


class DashboardTests(unittest.TestCase):
    def test_task_order_and_midnight(self):
        def task(title, sort, due, **fields):
            return dict(title=title, sortOrder=sort, dueDate=due, status=0) | fields

        tasks = [
            task("today", 2, "2026-11-19T05:59:00Z"),
            task("tomorrow", 0, "2026-11-19T06:00:00Z"),
            task("overdue", 3, "2026-11-17T12:00:00Z"),
            task("all day", 1, "2026-11-18T00:00:00Z", isAllDay=True),
            task("done", 0, "2026-11-18T00:00:00Z", status=2),
            task("undated", 0, None),
        ]
        self.assertEqual(task_rows(tasks, date(2026, 11, 18), ZoneInfo("Etc/GMT+6")),
                         [TaskRow("all day"), TaskRow("today"), TaskRow("overdue")])

    def test_first_three_active_unfinished_habits_today(self):
        start = date(2026, 11, 1)

        def habit(name, rule="FREQ=DAILY", active=True):
            return dict(id=name, title=name, rule=rule, active=active, start=start)

        habits = [habit("archived", active=False), habit("Tuesday", "FREQ=WEEKLY;BYDAY=TU"),
                  habit("done"), habit("first"), habit("second"), habit("third"), habit("fourth")]
        self.assertEqual(habit_titles(habits, {"done"}, date(2026, 11, 18)),
                         ["first", "second", "third"])

    def test_png_format_determinism_and_distinct_states(self):
        images = [render(), render([TaskRow("Long title " * 200)] * 9), render(outage=True)]
        for encoded in images:
            with Image.open(BytesIO(encoded)) as image:
                image.load()
                self.assertEqual((image.size, image.mode), ((800, 480), "L"))
                self.assertTrue(set(image.get_flattened_data()) <= {0, 85, 170, 255})
            self.assertEqual(encoded[24:26], bytes((2, 0)))  # IHDR bit depth and grayscale type.
            self.assertLessEqual(len(encoded), 90_000)
        with Image.open(BytesIO(images[1])) as image:
            # A text-only crop retains gray coverage at glyph edges after quantization.
            self.assertEqual(set(image.crop((41, 140, 220, 156)).get_flattened_data()),
                             {0, 85, 170, 255})
        self.assertEqual(render(), images[0])
        self.assertEqual(len(set(images)), 3)
        self.assertTrue(fit(ImageDraw.Draw(Image.new("L", (800, 480))),
                            "Long title " * 20, 200, 21).endswith("…"))

    def test_todos_heading_has_no_large_interletter_gap(self):
        with Image.open(BytesIO(render())) as image:
            heading = image.crop((59, 108, 105, 130))
        dark_columns = [
            x for x in range(heading.width)
            if heading.crop((x, 0, x + 1, heading.height)).getextrema()[0] <= 85
        ]
        # The previous native-size render left three empty columns after the d.
        self.assertLessEqual(max(right - left - 1
                                 for left, right in zip(dark_columns, dark_columns[1:])), 2)

    def test_overflow_count_changes_render(self):
        self.assertNotEqual(render([TaskRow("Same task")] * 9), render([TaskRow("Same task")] * 10))

    def test_overflow_keeps_parent_with_first_checklist_item(self):
        visible = [TaskRow("Visible task")] * 5
        first = TaskRow("First parent", ("Checklist item",))
        second = TaskRow("Second parent", first.checklist)
        self.assertNotEqual(render([*visible, first]), render([*visible, second]))
        self.assertEqual(render([*visible, first, TaskRow("Another task")]),
                         render([*visible, second, TaskRow("Another task")]))

    def test_open_checklist_rows_are_nested_and_sorted(self):
        today = date(2026, 11, 18)
        zone = ZoneInfo("Etc/UTC")
        parent = dict(title="Parent task", sortOrder=0, status=0, dueDate="2026-11-18",
                      isAllDay=True, items=[
                          dict(title="Item B", sortOrder=2, status=0),
                          dict(title="Done", sortOrder=0, status=1),
                          dict(title="Item A", sortOrder=1, status=0),
                      ])
        self.assertEqual(task_rows([parent], today, zone),
                         [TaskRow("Parent task", ("Item A", "Item B"))])

    def test_time_blocks_boundaries_overlap_and_local_hours(self):
        zone = ZoneInfo("Etc/GMT+6")
        now = datetime(2026, 11, 18, 17, 30, tzinfo=zone)

        def task(title, start, end, **fields):
            return dict(title=title, startDate=start, dueDate=end, status=0) | fields

        tasks = [
            task("Ended", "2026-11-18T22:00:00Z", "2026-11-18T23:30:00Z"),
            task("Long overlap", "2026-11-18T23:00:00Z", "2026-11-19T02:00:00Z"),
            task("Starts now", "2026-11-18T23:30:00Z", "2026-11-19T00:15:00Z"),
            task("Upcoming", "2026-11-19T00:15:00Z", "2026-11-19T01:00:00Z"),
            task("All day", "2026-11-18T23:35:00Z", "2026-11-19T00:00:00Z", isAllDay=True),
            task("Done", "2026-11-18T23:36:00Z", "2026-11-19T00:00:00Z", status=2),
            task("No end", "2026-11-18T23:38:00Z", None),
        ]
        self.assertEqual(time_blocks(tasks, now),
                         (TimeBlock("Starts now", "5:30pm - 6:15pm"),
                          TimeBlock("Upcoming", "6:15pm - 7:00pm")))
        tomorrow = task("Tomorrow", "2026-11-19T15:00:00Z", "2026-11-19T16:00:00Z")
        self.assertEqual(time_blocks([tomorrow], now),
                         (None, TimeBlock("Tomorrow", "Thu 9:00am - 10:00am")))
        self.assertEqual(time_blocks([], now), (None, None))
