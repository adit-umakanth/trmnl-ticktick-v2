import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts import local_projects


class LocalProjectsTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.dotenv = Path(directory) / ".env"
        self.enterContext(patch.object(local_projects, "ENV_FILE", self.dotenv))
        self.enterContext(patch.object(local_projects, "environ", {}))

    def test_loads_saved_ids_with_per_value_overrides(self):
        self.dotenv.write_text(
            'TICKTICK_INBOX_ID="saved-inbox" # comment\n'
            'TICKTICK_WORK_LIST_ID=saved_work\n'
            'TICKTICK_TIME_BLOCKING_LIST_ID=saved_blocks\n'
        )
        self.assertEqual(local_projects.project_ids(), ("saved-inbox", "saved_work", "saved_blocks"))
        local_projects.environ["TICKTICK_WORK_LIST_ID"] = "override_work"
        self.assertEqual(local_projects.project_ids(("override_inbox",)),
                         ("override_inbox", "override_work", "saved_blocks"))

    def test_fails_with_safe_messages_for_missing_and_invalid_values(self):
        with self.assertRaisesRegex(ValueError, "Set TICKTICK_INBOX_ID"):
            local_projects.project_ids()
        with self.assertRaisesRegex(ValueError, "^Invalid TICKTICK_INBOX_ID;"):
            local_projects.project_ids(("private invalid value", "work", "blocks"))

    def test_loads_dashboard_timezone_with_overrides(self):
        self.dotenv.write_text('DASHBOARD_TIMEZONE="Etc/UTC" # comment\n')
        self.assertEqual(local_projects.dashboard_timezone().key, "Etc/UTC")
        local_projects.environ["DASHBOARD_TIMEZONE"] = "Etc/GMT+6"
        self.assertEqual(local_projects.dashboard_timezone().key, "Etc/GMT+6")
        self.assertEqual(local_projects.dashboard_timezone("UTC").key, "UTC")

    def test_rejects_missing_and_invalid_dashboard_timezones(self):
        with self.assertRaisesRegex(ValueError, "^Set DASHBOARD_TIMEZONE in .env or the environment$"):
            local_projects.dashboard_timezone()
        for value in ("private invalid value", "../UTC"):
            with self.subTest(value=value), self.assertRaisesRegex(
                ValueError, "^Invalid DASHBOARD_TIMEZONE; use a valid IANA time zone$"
            ):
                local_projects.dashboard_timezone(value)
