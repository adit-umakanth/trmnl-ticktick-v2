"""Read-only TickTick Open API adapter."""

import json
from contextlib import contextmanager
from datetime import date
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfoNotFoundError

from dateutil.parser import isoparse

from dashboard import habit_titles, task_rows, time_blocks

BASE_URL = "https://api.ticktick.com/open/v1"
MAX_RESPONSE = 2_000_000
SCHEMA_FIELDS = frozenset({
    "projectId", "project", "id", "tasks", "status", "sortOrder", "title", "name",
    "repeatRule", "createdTime", "habitId", "checkins", "stamp", "value",
})


class TickTickError(Exception):
    """A failure with a safe-to-log message."""


@contextmanager
def response_schema(section):
    # Exception details can contain payload values. Only report controlled labels.
    try:
        yield
    except (ValueError, OverflowError, ZoneInfoNotFoundError):
        raise TickTickError(f"unexpected_schema/{section}/invalid_value") from None
    except KeyError as error:
        field = error.args[0] if error.args else None
        detail = f"/{field}" if isinstance(field, str) and field in SCHEMA_FIELDS else ""
        raise TickTickError(f"unexpected_schema/{section}/missing_field{detail}") from None
    except (TypeError, AttributeError):
        raise TickTickError(f"unexpected_schema/{section}/invalid_type") from None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class TickTick:
    def __init__(self, token):
        self.token = token
        self.opener = build_opener(NoRedirect())

    def read(self, path, query=None):
        request = Request(BASE_URL + path, headers={
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        })
        if query is not None:
            request.data = json.dumps(query).encode()
            request.add_header("Content-Type", "application/json")
        try:
            with self.opener.open(request, timeout=2.5) as response:
                data = response.read(MAX_RESPONSE + 1)
            if len(data) > MAX_RESPONSE:
                raise TickTickError("response_too_large")
            return json.loads(data)
        except HTTPError as error:
            error.close()
            raise TickTickError(f"http_{error.code}") from None
        except (URLError, OSError, HTTPException) as error:
            raise TickTickError("timeout" if isinstance(getattr(error, "reason", error),
                                                        TimeoutError) else "transport") from None
        except ValueError:
            raise TickTickError("invalid_json") from None

    def dashboard(self, inbox_id, work_id, time_blocking_id, now):
        today = now.date()
        with response_schema("inbox"):
            inbox = self.read("/task/filter", {"projectIds": [inbox_id], "status": [0]})
            if not isinstance(inbox, list):
                raise TickTickError("unexpected_schema/inbox/expected_array")
            if len(inbox) >= 200:
                raise TickTickError("inbox_result_limit")
            if any(task["projectId"] != inbox_id for task in inbox):
                raise TickTickError("inbox_membership")
            inbox_rows = task_rows(inbox, today, now.tzinfo)
        with response_schema("work"):
            work = self.project_tasks(work_id, "work_membership")
            work_rows = task_rows(work, today, now.tzinfo)
        with response_schema("time_blocking"):
            blocks = self.project_tasks(time_blocking_id, "time_blocking_membership")
            current, upcoming = time_blocks(blocks, now)
        with response_schema("habits"):
            habits = self.read("/habit")
            if not isinstance(habits, list):
                raise TickTickError("unexpected_schema/habits/expected_array")
            stamp = int(today.strftime("%Y%m%d"))
            active = [habit for habit in habits if habit.get("status", 0) == 0
                      and habit.get("repeatRule")]
            scheduled = [
                {
                    "id": habit["id"], "title": habit["name"], "active": True,
                    "rule": habit["repeatRule"], "start": habit_start(habit, now),
                }
                for habit in sorted(active, key=lambda habit: habit.get("sortOrder", 0))
                if stamp not in {int(value) for value in habit.get("exDates", [])}
            ]
        with response_schema("habit_checkins"):
            completed = self.completed(active, stamp)
        with response_schema("habits"):
            titles = habit_titles(scheduled, completed, today)
        return inbox_rows, work_rows, titles, current, upcoming

    def project_tasks(self, project_id, mismatch):
        data = self.read(f"/project/{quote(project_id, safe='')}/data")
        if data["project"]["id"] != project_id:
            raise TickTickError(mismatch)
        if not isinstance(data["tasks"], list):
            raise TypeError("Expected a task array")
        return data["tasks"]

    def completed(self, habits, stamp):
        if not habits:
            return set()
        by_id = {habit["id"]: habit for habit in habits}
        query = urlencode({"habitIds": ",".join(by_id), "from": stamp, "to": stamp})
        rows = self.read("/habit/checkins?" + query)
        if not isinstance(rows, list):
            raise TickTickError("unexpected_schema/habit_checkins/expected_array")
        completed = set()
        for row in rows:
            habit = by_id.get(row["habitId"])
            if habit is None:
                raise TickTickError("habit_checkins_membership")
            for item in row["checkins"]:
                goal = item.get("goal") or habit.get("goal") or 1
                if item["stamp"] == stamp and item["value"] >= goal:
                    completed.add(habit["id"])
        return completed


def habit_start(habit, now):
    stamp = habit.get("targetStartDate")
    if stamp:
        raw = str(stamp)
        return date(int(raw[:4]), int(raw[4:6]), int(raw[6:]))
    created = isoparse(habit["createdTime"])
    return created.astimezone(now.tzinfo).date() if created.tzinfo else created.date()
