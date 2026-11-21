import unittest
from datetime import datetime
from io import BytesIO
from os import environ
from tempfile import NamedTemporaryFile

from PIL import Image

from dashboard import render
from local_credentials import local_ticktick_token
from local_projects import dashboard_timezone, project_ids
from ticktick import TickTick, TickTickError


@unittest.skipUnless(environ.get("TICKTICK_LIVE") == "1", "requires TICKTICK_LIVE=1")
class TickTickLiveTests(unittest.TestCase):
    def test_render_dashboard_from_official_api(self):
        try:
            ids = project_ids()
            now = datetime.now(dashboard_timezone())
        except ValueError as error:
            self.fail(str(error))
        token = local_ticktick_token()
        if not token:
            self.fail("Load the TickTick token from Keychain or TICKTICK_TOKEN")
        try:
            sections = TickTick(token).dashboard(*ids, now)
        except TickTickError as error:
            self.fail(f"Live TickTick verification failed ({error})")

        payload = render(*sections)
        with Image.open(BytesIO(payload)) as image:
            image.load()
            self.assertEqual((image.format, image.size, image.mode), ("PNG", (800, 480), "L"))
        self.assertEqual(payload[24:26], bytes((2, 0)))  # PNG bit depth and grayscale color type.
        self.assertLessEqual(len(payload), 90_000)

        if preview_dir := environ.get("TICKTICK_PREVIEW_DIR"):
            with NamedTemporaryFile(dir=preview_dir, prefix="live-dashboard-", suffix=".png",
                                    delete=False) as preview:
                preview.write(payload)
