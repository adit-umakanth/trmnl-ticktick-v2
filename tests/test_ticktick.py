import unittest
from datetime import datetime, timezone
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
        read.assert_any_call("/habit/checkins?habitIds=a%2Cb%2Cc&from=20261118&to=20261118")

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
            ([[], work, blocks, [habit], [{"habitId": "fixture-id", "checkins": None}]],
             "habit_checkins/invalid_type"),
        ]
        for responses, diagnostic in failures:
            with self.subTest(diagnostic=diagnostic), patch.object(
                self.client, "read", side_effect=responses
            ):
                with self.assertRaisesRegex(TickTickError, f"^unexpected_schema/{diagnostic}$"):
                    self.client.dashboard("inbox", "work", "blocks", self.now)

    def test_http_and_timeout_errors_are_sanitized(self):
        failures = [
            (HTTPError("https://example.test", 503, "private content", {}, None), "http_503"),
            (URLError(TimeoutError("private content")), "timeout"),
        ]
        for error, code in failures:
            with patch.object(self.client.opener, "open", side_effect=error):
                with self.assertRaisesRegex(TickTickError, f"^{code}$"):
                    self.client.read("/habit")
