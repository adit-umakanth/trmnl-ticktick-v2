# TickTick dashboard for TRMNL OG

## Functional requirements

- A single configured TRMNL OG uses the stock BYOS setup, display, and log endpoints. It sees an 800×480 four-gray dashboard and refreshes every 900 seconds by default.
- The layout gives Current Block about 70% of the header, with a smaller Upcoming Block on the right. Use the same clock design at two sizes. Stack the Todos and Work Tasks cards above a Daily Habits strip with a leaf icon.
- Read the configured TickTick Time Blocking project. Use each open timed task’s start and due date as its block bounds. The current block includes its start and excludes its end. For overlaps, show the latest start, then manual order. The upcoming block is the earliest future start, including later days. Show times in the dashboard time zone and show explicit empty states. Ignore all-day tasks and tasks without both bounds.
- Todos (Inbox) and Work Tasks show open TickTick tasks due today or earlier, in manual order. Undated and future tasks are excluded. Use filled bullets for tasks and indented hollow bullets for unchecked checklist entries. Long titles are ellipsized and overflow counts hidden rows.
- Habits shows the first three active habits scheduled for today in TickTick order, excluding habits completed or skipped today. Partial check-ins stay eligible until they reach their goal. Unused habit slots stay blank, and reminder times are ignored. Other empty sections are labeled.
- Today is calculated in the configured IANA dashboard time zone.
- A failed or incomplete TickTick read produces a readable outage screen. The next wake attempts a fresh read.

## Nonfunctional requirements

- Use the configured home public IPv4 /32 as the sole access gate for the entire REST API. Enforce it in API Gateway before Lambda invocation.
- Keep credentials out of code, URLs, and logs. Store snapshots privately with automatic expiry. Log sanitized operational events with finite retention.
- Bound upstream time and use on-demand infrastructure without a scheduler or database.

## Acceptance criteria

- Local tests verify filtering across midnight, ordering, habit completion, overflow, empty states, checklist rows, time block boundaries and overlap, and outage behavior. The PNG decodes as 800×480 at two grayscale bits per pixel, uses levels 0, 85, 170, and 255, preserves gray pixels along antialiased Source Sans 3 glyph edges, and fits within 90,000 bytes.
- BYOS tests cover provisioning and requests with absent or arbitrary device headers, refresh timing, repeat filenames, and retrieval of an earlier snapshot after a newer publication.
- Live verification covers official TickTick reads, allowed and denied source networks, the display on physical hardware, and recovery from a controlled TickTick failure.
