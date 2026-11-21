import base64
import json
import unittest
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import Mock, patch

from byos import byos, lambda_handler
from dashboard import TaskRow, TimeBlock, render
from snapshots import Snapshots
from ticktick import TickTickError

CONFIG = {
    "DASHBOARD_TIMEZONE": "Etc/UTC",
    "INBOX_ID": "inbox", "WORK_LIST_ID": "work", "REFRESH_SECONDS": "900",
    "TIME_BLOCKING_LIST_ID": "blocks",
}
CREDENTIALS = {"ticktick_token": "test-token"}


class StorageError(Exception):
    def __init__(self, code):
        self.response = {"Error": {"Code": code}}


class MemoryS3:
    def __init__(self):
        self.objects = {}

    def put_object(self, *, Bucket, Key, Body, IfNoneMatch, ContentType, Metadata):
        assert IfNoneMatch == "*" and ContentType == "image/png"
        if Key in self.objects:
            raise StorageError("PreconditionFailed")
        self.objects[Key] = Body, Metadata

    def head_object(self, *, Bucket, Key):
        return {"Metadata": self.objects[Key][1]}

    def get_object(self, *, Bucket, Key):
        if Key not in self.objects:
            raise StorageError("NoSuchKey")
        body, metadata = self.objects[Key]
        return {"Body": BytesIO(body), "Metadata": metadata}


class Feed:
    def __init__(self):
        self.sections = ([TaskRow("Test task")], [], [], TimeBlock("Test block", "4:00pm - 5:30pm"), None)
        self.failure = None
        self.calls = 0

    def dashboard(self, inbox, work, blocks, now):
        assert blocks == "blocks"
        self.calls += 1
        if self.failure:
            raise TickTickError(self.failure)
        return self.sections


class ByosTests(unittest.TestCase):
    def setUp(self):
        self.storage = Snapshots(MemoryS3(), "private", StorageError)
        self.feed = Feed()
        self.time = 1_794_999_000
        self.credentials = Mock(return_value=CREDENTIALS)

    def event(self, route, method="GET", *, headers=None, image=None):
        event = {
            "resource": route, "httpMethod": method,
            "requestContext": {"domainName": "api.example.test", "stage": "byos"},
            "pathParameters": {"image": image} if image else None,
        }
        if headers is not None:
            event["headers"] = headers
        return event

    def request(self, route, method="GET", **kwargs):
        return byos(self.event(route, method, **kwargs), CONFIG, self.credentials, self.storage,
                    lambda: datetime.fromtimestamp(self.time, timezone.utc),
                    lambda token: self.feed)

    def test_setup_log_and_setup_image_ignore_headers_and_skip_credentials(self):
        arbitrary = {"ID": "arbitrary-id", "Access-Token": "arbitrary-token", "Host": "untrusted.test"}
        for headers in (None, arbitrary):
            with self.subTest(headers=headers):
                response = self.request("/api/setup", headers=headers)
                self.assertEqual(response["statusCode"], 200)
                setup = json.loads(response["body"])
                self.assertEqual(setup["status"], 200)
                self.assertEqual(setup["api_key"], "byos-local")
                self.assertEqual(setup["friendly_id"], "000001")
                self.assertEqual(setup["image_url"], "https://api.example.test/byos/images/setup.png")
                self.assertEqual(self.request("/api/log", "POST", headers=headers)["statusCode"], 200)
                image = self.request("/images/{image}", headers=headers, image="setup.png")
                self.assertEqual(image["statusCode"], 200)
        self.credentials.assert_not_called()
        self.assertEqual(self.feed.calls, 0)

    def test_display_reads_legacy_or_token_only_ssm_json(self):
        ssm = Mock()
        settings = {**CONFIG, "CREDENTIAL_PARAMETER": "/test/credentials"}
        arbitrary = {"ID": "arbitrary-id", "Access-Token": "arbitrary-token"}
        with (patch.dict("os.environ", settings),
              patch("byos.aws_clients", return_value=(ssm, self.storage)),
              patch("byos.TickTick.dashboard", autospec=True, return_value=self.feed.sections) as dashboard):
            for credentials in (CREDENTIALS, {**CREDENTIALS, "device_key": "legacy-test-key"}):
                ssm.get_parameter.return_value = {"Parameter": {"Value": json.dumps(credentials)}}
                for headers in (None, arbitrary):
                    with self.subTest(fields=sorted(credentials), headers=headers):
                        ssm.reset_mock()
                        dashboard.reset_mock()
                        response = lambda_handler(self.event("/api/display", headers=headers), None)
                        self.assertEqual(response["statusCode"], 200)
                        display = json.loads(response["body"])
                        self.assertEqual(display["status"], 0)
                        self.assertEqual(dashboard.call_args.args[0].token, "test-token")
                        ssm.get_parameter.assert_called_once_with(Name="/test/credentials", WithDecryption=True)

    def test_unchanged_and_overlapping_snapshots(self):
        first = json.loads(self.request("/api/display")["body"])
        self.time += 900
        same = json.loads(self.request("/api/display")["body"])
        self.assertEqual(first, same)
        self.assertEqual(first["refresh_rate"], 900)
        self.assertFalse(first["update_firmware"])
        self.assertFalse(first["reset_firmware"])
        self.feed.sections = ([TaskRow("New task")], [], [], None, None)
        new = json.loads(self.request("/api/display")["body"])
        self.assertNotEqual(first["filename"], new["filename"])
        old_image = self.request("/images/{image}", image=first["filename"] + ".png")
        self.assertTrue(old_image["isBase64Encoded"])
        decoded = base64.b64decode(old_image["body"])
        self.assertEqual(int(old_image["headers"]["Content-Length"]), len(decoded))
        self.assertEqual(old_image["headers"]["Content-Type"], "image/png")
        self.assertEqual(decoded, render([TaskRow("Test task")],
                                         current=TimeBlock("Test block", "4:00pm - 5:30pm")))
        self.assertEqual(self.feed.calls, 3)

    def test_outage_and_recovery(self):
        for reason in ("timeout", "http_503"):
            self.feed.failure = reason
            with self.assertLogs("byos", "WARNING") as logs:
                display = json.loads(self.request("/api/display")["body"])
            self.assertIn(reason, logs.output[0])
            self.assertEqual(display["status"], 0)
            image = self.request("/images/{image}", image=display["filename"] + ".png")
            self.assertEqual(base64.b64decode(image["body"]), render(outage=True))
        self.feed.failure = None
        recovered = json.loads(self.request("/api/display")["body"])
        self.assertNotEqual(recovered["filename"], display["filename"])

    def test_unknown_image(self):
        self.assertEqual(self.request("/images/{image}", image="unknown.png")["statusCode"], 404)
