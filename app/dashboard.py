"""Date selection and deterministic, native-resolution OG rendering."""

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from functools import lru_cache
from io import BytesIO
from math import ceil, floor
from pathlib import Path
from zoneinfo import ZoneInfo

import png
from dateutil.parser import isoparse
from dateutil.rrule import rrulestr
from PIL import Image, ImageDraw, ImageFont


def due_on(task, zone):
    raw = task.get("dueDate")
    if not raw:
        return None
    due = isoparse(raw)
    if task.get("isAllDay") in (True, "true"):
        task_zone = task.get("timeZone")
        if task_zone and due.tzinfo:
            return due.astimezone(ZoneInfo(task_zone)).date()
        return due.date()
    if due.tzinfo is None:
        raise ValueError("Timed task due date has no offset")
    return due.astimezone(zone).date()


@dataclass(frozen=True)
class TaskRow:
    title: str
    checklist: tuple[str, ...] = ()


@dataclass(frozen=True)
class TimeBlock:
    title: str
    hours: str


def is_open(task):
    return task["status"] == 0 and not task.get("completedTime") and task.get("kind") != "NOTE"


def task_rows(tasks, today, zone):
    eligible = [task for task in tasks if is_open(task)
                and (day := due_on(task, zone)) is not None and day <= today]
    return [
        TaskRow(task["title"], tuple(
            item["title"] for item in sorted(task.get("items") or (),
                                             key=lambda item: item.get("sortOrder", 0))
            if item.get("status", 0) == 0
        ))
        for task in sorted(eligible, key=lambda row: row["sortOrder"])
    ]


def work_task_rows(tasks, active_column_id):
    eligible = (task for task in tasks if task.get("columnId") == active_column_id
                and not task.get("parentId") and is_open(task))
    return [TaskRow(task["title"]) for task in sorted(eligible, key=lambda task: task["sortOrder"])]


def time_blocks(tasks, now):
    # Compare absolute instants so repeated wall times at a DST transition stay distinct.
    blocks = []
    for task in tasks:
        if (not is_open(task) or task.get("isAllDay") in (True, "true")
                or not task.get("startDate") or not task.get("dueDate")):
            continue
        start, end = isoparse(task["startDate"]), isoparse(task["dueDate"])
        if start.tzinfo is None or end.tzinfo is None or end <= start:
            continue
        blocks.append((start.timestamp(), end.timestamp(), task.get("sortOrder", 0),
                       task["title"]))
    instant = now.timestamp()
    # On overlap, prefer the block that started most recently, then the manual order.
    current = min((block for block in blocks if block[0] <= instant < block[1]),
                  key=lambda block: (-block[0], block[2]), default=None)
    upcoming = min((block for block in blocks if block[0] > instant),
                   key=lambda block: (block[0], block[2]), default=None)
    return display_block(current, now), display_block(upcoming, now)


def display_block(block, now):
    if block is None:
        return None
    start, end = (datetime.fromtimestamp(value, now.tzinfo) for value in block[:2])
    return TimeBlock(block[3], f"{clock_label(start, now)} - {clock_label(end, start)}")


def clock_label(value, reference):
    prefix = value.strftime("%a ") if value.date() != reference.date() else ""
    return prefix + value.strftime("%I:%M%p").lstrip("0").lower()


HABIT_LIMIT = 3


def habit_titles(habits, hidden, today):
    midnight = datetime.combine(today, time.min)
    end = midnight + timedelta(days=1)
    titles = []
    for habit in habits:
        if habit["id"] in hidden or not habit["active"]:
            continue
        rule = habit["rule"]
        if not rule:
            continue
        start = datetime.combine(habit["start"], time.min)
        occurrence = rrulestr(rule, dtstart=start).after(midnight, inc=True)
        if occurrence is not None and midnight <= occurrence < end:
            titles.append(habit["title"])
    return titles[:HABIT_LIMIT]


BLACK, DARK, LIGHT, WHITE = 0, 85, 170, 255
FONT_PATH = Path(__file__).parent / "fonts" / "SourceSans3.ttf"
TEXT_SCALE = 4


@lru_cache
def font(size, weight=400):
    face = ImageFont.truetype(str(FONT_PATH), size * TEXT_SCALE)
    face.set_variation_by_axes([weight])
    return face


def fit(draw, value, width, size, weight=400):
    value = " ".join(value.split())
    face = font(size, weight)
    width *= TEXT_SCALE
    if draw.textlength(value, font=face) <= width:
        return value
    low, high = 0, len(value)
    while low < high:
        mid = (low + high + 1) // 2
        if draw.textlength(value[:mid] + "…", font=face) <= width:
            low = mid
        else:
            high = mid - 1
    return value[:low].rstrip() + "…"


def draw_text(draw, xy, label, size, weight=400, *, fill=BLACK, anchor="lt"):
    face = font(size, weight)
    left, top, right, bottom = face.getbbox(label, anchor=anchor)
    # Keep the mask aligned to native pixels and leave room for the Lanczos filter.
    padding = 3
    left = floor(left / TEXT_SCALE) - padding
    top = floor(top / TEXT_SCALE) - padding
    width = ceil(right / TEXT_SCALE) + padding - left
    height = ceil(bottom / TEXT_SCALE) + padding - top
    mask = Image.new("L", (width * TEXT_SCALE, height * TEXT_SCALE))
    ImageDraw.Draw(mask).text((-left * TEXT_SCALE, -top * TEXT_SCALE), label,
                              font=face, fill=WHITE, anchor=anchor)
    mask = mask.resize((width, height), Image.Resampling.LANCZOS)
    x, y = xy
    draw.bitmap((x + left, y + top), mask, fill=fill)


def list_icon(draw, x, y):
    for row in (y - 5, y, y + 5):
        draw.ellipse((x - 6, row - 1, x - 4, row + 1), fill=DARK)
        draw.line((x, row, x + 6, row), fill=DARK, width=2)


def briefcase_icon(draw, x, y):
    draw.rounded_rectangle((x - 3, y - 7, x + 3, y - 2), radius=2, outline=DARK)
    draw.rounded_rectangle((x - 7, y - 4, x + 7, y + 6), radius=2, fill=DARK)
    draw.line((x - 6, y, x + 6, y), fill=LIGHT)
    draw.rectangle((x - 1, y - 1, x + 1, y + 1), fill=WHITE)


def task_card(draw, title, tasks, y, bottom, *, icon, empty):
    draw.rounded_rectangle((12, y, 787, bottom), radius=10, outline=LIGHT)
    draw.line((13, y + 30, 786, y + 30), fill=LIGHT)
    draw.ellipse((28, y + 4, 50, y + 26), outline=LIGHT)
    icon(draw, 39, y + 15)
    draw_text(draw, (59, y + 15), title, 16, 650, anchor="lm")
    lines = []
    for task in tasks:
        lines.append((task.title, False))
        lines.extend((item, True) for item in task.checklist)
    if not lines:
        draw_text(draw, (28, y + 36), empty, 14, fill=DARK)
        return
    top = y + 36
    row_height, task_gap = 15, 2
    # Reserve space for the full row height and the gap between top-level tasks.
    capacity = (bottom - top + task_gap) // (row_height + task_gap)
    visible_count = min(len(lines), capacity)
    if len(lines) > capacity:
        visible_count -= 1  # Reserve a row for the overflow count.
        if not lines[visible_count - 1][1] and lines[visible_count][1]:
            visible_count -= 1  # Keep a parent with its first checklist item.
    for index, (label, child) in enumerate(lines[:visible_count]):
        if index and not child:
            top += task_gap
        marker_x = 46 if child else 28
        left = marker_x + 13
        marker = (marker_x, top + 4, marker_x + 5, top + 9)
        if child:
            draw.ellipse(marker, outline=BLACK)
        else:
            draw.ellipse(marker, fill=BLACK)
        draw_text(draw, (left, top), fit(draw, label, 770 - left, 14), 14)
        top += row_height
    if visible_count < len(lines):
        draw_text(draw, (41, top + task_gap), f"+{len(lines) - visible_count} more", 14, 550,
                  fill=DARK)


def clock_icon(draw, x, y, radius, color, width):
    draw.ellipse((x - radius, y - radius, x + radius, y + radius),
                 outline=color, width=width)
    draw.line((x, y - radius // 2, x, y, x + radius // 2, y + radius // 3),
              fill=color, width=width)


def block_panel(draw, current, upcoming):
    draw.rounded_rectangle((12, 10, 545, 96), radius=10, outline=DARK)
    draw.rounded_rectangle((557, 18, 787, 88), radius=10, outline=LIGHT)
    draw.ellipse((28, 31, 72, 75), fill=DARK)
    clock_icon(draw, 50, 53, 12, WHITE, 2)
    clock_icon(draw, 579, 53, 9, DARK, 1)
    for x, right, y, title_size, heading, block, empty in (
        (84, 529, 20, 24, "CURRENT BLOCK", current, "No current block"),
        (599, 775, 26, 17, "UPCOMING BLOCK", upcoming, "No upcoming block"),
    ):
        draw_text(draw, (x, y), heading, 12, 650, fill=DARK)
        label = fit(draw, block.title if block else empty, right - x, title_size, 650)
        draw_text(draw, (x, y + 15), label, title_size, 650)
        if block:
            draw_text(draw, (x, y + title_size + 20),
                      fit(draw, block.hours, right - x, 14), 14, fill=DARK)


def habits_strip(draw, habits):
    draw.rounded_rectangle((12, 431, 787, 469), radius=10, outline=LIGHT)
    draw.polygon(((30, 454), (29, 450), (32, 445), (37, 443), (45, 442),
                  (44, 450), (41, 454), (36, 456), (32, 456)), fill=DARK)
    draw.line((28, 458, 39, 448), fill=DARK)
    draw.line((33, 453, 39, 448), fill=WHITE)
    draw_text(draw, (54, 450), "Daily Habits", 16, 650, anchor="lm")
    width = 606 // HABIT_LIMIT
    for index, label in enumerate(habits[:HABIT_LIMIT]):
        left = 166 + width * index
        draw.line((left, 440, left, 460), fill=LIGHT)
        draw_text(draw, (left + width // 2, 450), fit(draw, label, width - 16, 14),
                  14, anchor="mm")


def render(inbox=(), work=(), habits=(), current=None, upcoming=None, *, outage=False,
           sleep_until=None):
    image = Image.new("L", (800, 480), WHITE)
    draw = ImageDraw.Draw(image)
    if sleep_until is not None:
        draw.ellipse((367, 128, 433, 194), fill=DARK)
        draw.ellipse((385, 119, 443, 177), fill=WHITE)
        draw_text(draw, (400, 224), "Sleeping", 42, 650, anchor="mt")
        wake_label = sleep_until.strftime("%I:%M %p").lstrip("0").lower()
        draw_text(draw, (400, 283), f"Next refresh at {wake_label}", 24,
                  fill=DARK, anchor="mt")
    elif outage:
        draw_text(draw, (400, 204), "TickTick unavailable", 38, 650, anchor="mt")
        draw_text(draw, (400, 258), "Trying again on the next refresh.", 23,
                  fill=DARK, anchor="mt")
    else:
        block_panel(draw, current, upcoming)
        # None hides the Work card. An empty sequence still shows its empty state.
        task_card(draw, "Todos", inbox, 104, 418 if work is None else 257,
                  icon=list_icon, empty="No tasks due")
        if work is not None:
            task_card(draw, "Work Tasks", work, 265, 418,
                      icon=briefcase_icon, empty="No active tasks")
        habits_strip(draw, habits)

    # Map the composited grayscale image to the OG's four native levels,
    # then encode grayscale PNG samples (color type 0).
    samples = image.point([(value + 42) // 85 for value in range(256)]).tobytes()
    rows = (samples[start:start + image.width]
            for start in range(0, len(samples), image.width))
    with BytesIO() as output:
        png.Writer(image.width, image.height, greyscale=True, bitdepth=2).write(output, rows)
        payload = output.getvalue()
    if len(payload) > 90_000:
        raise ValueError("Image exceeds the TRMNL OG byte limit")
    return payload
