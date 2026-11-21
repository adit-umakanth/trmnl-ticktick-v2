"""REST API proxy entry point for a single TRMNL OG."""

import base64
import json
import logging
import os
from datetime import datetime, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

from dashboard import render
from snapshots import Snapshots
from ticktick import TickTick, TickTickError

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.INFO)


def respond(status, data):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"},
        "body": json.dumps(data),
    }


def png(payload):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "image/png", "Content-Length": str(len(payload)),
                    "Cache-Control": "private, no-store"},
        "body": base64.b64encode(payload).decode("ascii"),
        "isBase64Encoded": True,
    }


def byos(event, settings, credentials, snapshots, clock, ticktick=TickTick):
    route = event.get("resource"), event.get("httpMethod")
    if route == ("/images/{image}", "GET"):
        image = (event.get("pathParameters") or {}).get("image", "")
        if image == "setup.png":
            return png(render())
        if image.endswith(".png"):
            payload = snapshots.get(image[:-4])
            if payload is not None:
                return png(payload)
        return respond(404, {"message": "Image unavailable"})

    if route not in {("/api/setup", "GET"), ("/api/display", "GET"), ("/api/log", "POST")}:
        return respond(404, {"message": "Unknown route"})
    if route[0] == "/api/log":
        LOG.info(json.dumps({"event": "device_log_received"}))
        return respond(200, {"status": 200})

    context = event["requestContext"]
    # API Gateway supplies these values. Never build a URL from the caller's Host header.
    base = f"https://{context['domainName']}/{context['stage']}"
    if route[0] == "/api/setup":
        # The firmware stores these fields. API Gateway controls access by source IP.
        return respond(200, {"status": 200, "api_key": "byos-local",
                             "friendly_id": "000001",
                             "image_url": f"{base}/images/setup.png",
                             "message": "Device ready"})

    token = credentials()["ticktick_token"]
    now = clock()
    local = now.astimezone(ZoneInfo(settings["DASHBOARD_TIMEZONE"]))
    try:
        sections = ticktick(token).dashboard(
            settings["INBOX_ID"], settings["WORK_LIST_ID"],
            settings["TIME_BLOCKING_LIST_ID"], local
        )
        payload = render(*sections)
    except TickTickError as error:
        LOG.warning(json.dumps({"event": "ticktick_unavailable", "reason": str(error)}))
        payload = render(outage=True)
    filename = snapshots.publish(payload, int(now.timestamp()))
    return respond(200, {
        "status": 0, "image_url": f"{base}/images/{filename}.png", "filename": filename,
        "refresh_rate": int(settings["REFRESH_SECONDS"]), "reset_firmware": False,
        "update_firmware": False, "firmware_url": None, "special_function": "none",
        "maximum_compatibility": False, "temperature_profile": "default",
    })


@lru_cache
def aws_clients():
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError

    config = Config(connect_timeout=2, read_timeout=3, retries={"total_max_attempts": 1})
    return (boto3.client("ssm", config=config),
            Snapshots(boto3.client("s3", config=config), os.environ["SNAPSHOT_BUCKET"],
                      ClientError))


def lambda_handler(event, _context):
    try:
        ssm, snapshots = aws_clients()

        def credentials():
            parameter = ssm.get_parameter(Name=os.environ["CREDENTIAL_PARAMETER"],
                                          WithDecryption=True)
            return json.loads(parameter["Parameter"]["Value"])

        return byos(event, os.environ, credentials, snapshots, lambda: datetime.now(timezone.utc))
    except Exception:
        LOG.error(json.dumps({"event": "dashboard_service_error"}))
        return respond(503, {"message": "Dashboard unavailable"})
