import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from dashboard import TaskRow, TimeBlock
from ticktick import TickTick, TickTickError


class TickTickTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 18, tzinfo=timezone.utc)
        self.client = TickTick("synthetic-token")

    def test_read_only_dashboard_contract(self):
        task = dict(projectId="inbox", title="Inbox task", sortOrder=10, status=0,
                    dueDate="2026-11-18T00:00:00Z")
        habits = [
            dict(id="a", name="Partial goal", sortOrder=1, status=0,
                 targetStartDate=20261101, repeatRule="RRULE:FREQ=DAILY", goal=5),
            dict(id="b", name="Goal reached", sortOrder=0, status=0,
                 targetStartDate=20261101, repeatRule="RRULE:FREQ=DAILY", goal=5),
            dict(id="c", name="Excluded date", sortOrder=2, status=0,
                 targetStartDate=20261101, repeatRule="RRULE:FREQ=DAILY", exDates=["20261118"]),
        ]
        work = {"project": {"id": "work"}, "tasks": [task | {"title": "Work task"}]}
        checkins = [
            {"habitId": "a", "checkins": [{"stamp": 20261118, "value": 4}]},
            {"habitId": "b", "checkins": [{"stamp": 20261118, "value": 5}]},
        ]
        blocks = {"project": {"id": "blocks"}, "tasks": [
            dict(title="Planning", status=0, startDate="2026-11-18T01:00:00Z",
                 dueDate="2026-11-18T02:00:00Z"),
        ]}
        with patch.object(self.client, "read",
                          side_effect=[[task], work, blocks, habits, checkins]) as read:
            self.assertEqual(self.client.dashboard("inbox", "work", "blocks", self.now),
                             ([TaskRow("Inbox task")], [TaskRow("Work task")], ["Partial goal"],
                              None, TimeBlock("Planning", "1:00am - 2:00am")))
        read.assert_any_call("/project/blocks/data")
        read.assert_any_call("/task/filter", {"projectIds": ["inbox"], "status": [0]})
        read.assert_any_call("/habit/checkins?habitIds=a%2Cb%2Cc&from=20261118&to=20261119")

    def test_habits_follow_section_order_before_individual_order(self):
        scheduled = dict(targetStartDate=20261101, repeatRule="RRULE:FREQ=DAILY")
        habits = [
            dict(scheduled, id="a", name="Later section", sectionId="a", sortOrder=-10),
            dict(scheduled, id="b", name="First section, second habit", sectionId="z",
                 sortOrder=10, goal=4),
            dict(scheduled, id="c", name="Ungrouped", sortOrder=-20),
            dict(scheduled, id="d", name="First section, first habit", sectionId="z",
                 sortOrder=-10, goal=8),
        ]
        sections = [{"id": "a", "sortOrder": 40}, {"id": "z", "sortOrder": -50}]
        work = {"project": {"id": "work"}, "tasks": []}
        blocks = {"project": {"id": "blocks"}, "tasks": []}
        checkins = [
            {"habitId": "b", "checkins": [{"stamp": 20261118, "value": 4, "goal": 5, "status": 0}]},
            {"habitId": "d", "checkins": [{"stamp": 20261118, "value": 6, "goal": 5}]},
        ]
        adjacent_days = {"habitId": "a", "checkins": [{"stamp": 20261117, "value": 1},
                                                    {"stamp": 20261119, "value": 1}]}
        skipped = [
            {"habitId": "a", "checkins": [{"stamp": 20261118, "status": 1, "value": 0}]},
            {"habitId": "c", "checkins": [{"stamp": 20261117, "status": 1, "value": 0}]},
        ]
        cases = (
            ("unchecked", [], ["First section, first habit", "First section, second habit",
                               "Later section"]),
            ("checked in", [*checkins, adjacent_days],
             ["First section, second habit", "Later section", "Ungrouped"]),
            ("skipped", [*checkins, *skipped], ["First section, second habit", "Ungrouped"]),
        )
        for state, rows, expected in cases:
            with self.subTest(state=state), patch.object(
                self.client, "read", side_effect=[[], work, blocks, habits, sections, rows]
            ) as read:
                _, _, titles, _, _ = self.client.dashboard("inbox", "work", "blocks", self.now)
                self.assertEqual(titles, expected)
                read.assert_any_call("/habit/sections")
                read.assert_any_call("/habit/checkins?habitIds=a%2Cb%2Cc%2Cd&from=20261118&to=20261119")

    def test_habit_checkin_end_date_rolls_over_at_year_end(self):
        with patch.object(self.client, "read", return_value=[]) as read:
            self.assertEqual(self.client.hidden_habit_ids([{"id": "a"}], date(2026, 12, 31)), set())
        read.assert_called_once_with("/habit/checkins?habitIds=a&from=20261231&to=20270101")

    def test_refuses_potentially_truncated_inbox(self):
        with patch.object(self.client, "read", return_value=[{}] * 200):
            with self.assertRaisesRegex(TickTickError, "inbox_result_limit"):
                self.client.dashboard("inbox", "work", "blocks", self.now)

    def test_schema_errors_identify_the_section_without_payload_values(self):
        work = {"project": {"id": "work"}, "tasks": []}
        blocks = {"project": {"id": "blocks"}, "tasks": []}
        habit = dict(id="fixture-id", name="Fixture habit", targetStartDate=20261101,
                     repeatRule="RRULE:FREQ=DAILY")
        failures = [
            ([{"private-key": "private-value"}], "inbox/expected_array"),
            ([[], {"project": {"id": "work"}}], "work/missing_field/tasks"),
            ([[], work, blocks, [habit | {"repeatRule": "PRIVATE_VALUE"}], []],
             "habits/invalid_value"),
            ([[], work, blocks, [habit | {"sectionId": "private-section"}],
              [{"id": "private-section", "sortOrder": "PRIVATE_VALUE"}]],
             "habit_sections/invalid_type"),
            ([[], work, blocks, [habit], [{"habitId": "fixture-id", "checkins": None}]],
             "habit_checkins/invalid_type"),
        ]
        for responses, diagnostic in failures:
            with self.subTest(diagnostic=diagnostic), patch.object(
                self.client, "read", side_effect=responses
            ):
                with self.assertRaisesRegex(TickTickError, f"^unexpected_schema/{diagnostic}$"):
                    self.client.dashboard("inbox", "work", "blocks", self.now)

    def test_unknown_habit_section_is_an_incomplete_read(self):
        with patch.object(self.client, "read", return_value=[{"id": "other", "sortOrder": 0}]):
            with self.assertRaisesRegex(TickTickError, "^habit_sections_membership$"):
                self.client.habit_section_ranks({"missing"})

    def test_http_and_timeout_errors_are_sanitized(self):
        failures = [
            (HTTPError("https://example.test", 503, "private content", {}, None), "http_503"),
            (URLError(TimeoutError("private content")), "timeout"),
        ]
        for error, code in failures:
            with patch.object(self.client.opener, "open", side_effect=error):
                with self.assertRaisesRegex(TickTickError, f"^{code}$"):
                    self.client.read("/habit")
