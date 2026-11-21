"""Immutable private snapshots with firmware-friendly names."""

import hashlib
import re
from contextlib import closing

IMAGE_NAME = re.compile(r"screen-([0-9a-f]{12})-([0-9]{10})")
BUCKET_SECONDS = 86_400


def error_code(error):
    return error.response["Error"]["Code"]


def object_key(digest, timestamp):
    return f"screens/{timestamp // BUCKET_SECONDS}/{digest}.png"


class Snapshots:
    def __init__(self, client, bucket, client_error):
        self.client = client
        self.bucket = bucket
        self.client_error = client_error

    def publish(self, data, timestamp):
        digest = hashlib.sha256(data).hexdigest()[:12]
        key = object_key(digest, timestamp)
        try:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=data,
                                   ContentType="image/png", IfNoneMatch="*",
                                   Metadata={"created": str(timestamp)})
        except self.client_error as error:
            if error_code(error) not in {"PreconditionFailed", "412"}:
                raise
            existing = self.client.head_object(Bucket=self.bucket, Key=key)
            timestamp = int(existing["Metadata"]["created"])
        return f"screen-{digest}-{timestamp}"

    def get(self, filename):
        match = IMAGE_NAME.fullmatch(filename)
        if not match:
            return None
        digest, timestamp = match.groups()
        try:
            obj = self.client.get_object(Bucket=self.bucket, Key=object_key(digest, int(timestamp)))
        except self.client_error as error:
            # Private buckets without ListBucket may return 403 for an absent object.
            if error_code(error) in {"NoSuchKey", "AccessDenied", "404", "403"}:
                return None
            raise
        with closing(obj["Body"]) as body:
            if obj["Metadata"]["created"] != timestamp:
                return None
            return body.read()
