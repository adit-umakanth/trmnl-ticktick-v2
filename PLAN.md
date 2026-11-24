# Implementation milestones

1. Review this plan, PRD.md, and AGENTS.md. Initialize Git and commit the documents.
2. Run the authenticated read-only integration check documented in README.md. Confirm Inbox, Work, and Time Blocking membership, due dates, sort order, block start/end times, and habit schedules and check-in semantics against the app. Record only scrubbed evidence. If a required capability is absent, stop before adopting any substitute.
3. Run the fixture renderer and the domain/render tests. Inspect the split time block header, stacked task cards with checklist rows, the habits strip, and the outage preview and verify the 2-bit grayscale PNG encoding, antialiased type, and byte limits.
4. Run the handler/storage tests, `sam validate --lint`, and `sam build`. Verify the source-IP policy, binary response, snapshot isolation, and sanitization. Prepare the regional cost estimate and deployment/rollback instructions.
5. Obtain approval before any cost or deployment. Verify both allowed and denied networks, then verify setup, normal rendering, outage, and recovery on the physical OG.

Commit each milestone after its checks pass. Fixture-backed results and authenticated results are recorded separately.

## Work Tasks from `Active`

- [x] Resolve the Work list's `Active` section from the project data response and select open, top-level tasks by section ID and parent ID.
- [x] Build one row per eligible Work task in manual order, independent of due date. Show “No active tasks” when there are no eligible rows.
- [x] Verify with fixtures. All 28 offline tests passed, and the dashboard and outage previews rendered as 800×480, 2-bit grayscale PNGs.
- [x] Verify the live preview. The authenticated API check found one `Active` section in the configured Work list, the live render passed its PNG checks, and the owner confirmed the preview worked as intended.

- [x] Verify Work Tasks from `Active` on the physical OG. The owner confirmed the behavior on the device.

## Live and physical OG verification

- [x] Confirm the live preview against the signed-in TickTick app. The owner verified built-in Inbox behavior, Work Tasks, Current and Upcoming Blocks, habit ordering, and archive and check-in behavior, including the applicable date, recurrence, and grouping checks.
- [x] Verify access from the allowed home network and rejection from an off-network connection before Lambda invocation. The owner confirmed both checks.
- [x] Verify BYOS setup, normal dashboard rendering, and image retrieval on repeated wakes on the physical OG. The owner confirmed normal behavior on the device.
- [ ] Verify outage rendering and recovery with a controlled TickTick authentication failure in the live integration and on the physical OG.

## Weekday Work Tasks

- [x] Gate the Work list read on the dashboard-local weekday and time. Distinguish a hidden Work card from an empty Work list during work hours.
- [x] Expand Todos when Work Tasks is hidden. Keep the header and Daily Habits strip in place and preserve checklist and overflow behavior.
- [x] All 30 offline tests passed, including the boundaries, seasonal UTC offsets, weekend behavior, and snapshot output. Work-hours, after-hours, and outage previews were visually inspected and verified as 800×480, 2-bit grayscale PNGs below 90,000 bytes.
- [x] SAM validation and the Linux arm64 build passed. Deployed `aea6f2e` to the existing `trmnl-ticktick` stack in `us-east-1` using its existing parameter values. CloudFormation reached `UPDATE_COMPLETE`, and live BYOS setup, display, and image retrieval verified the expanded Todos layout.
- [x] The owner confirmed the weekday Work Tasks schedule and after-hours Todos layout on the physical TRMNL OG.
- [ ] Compare both layouts against the signed-in TickTick app.

## Overnight sleep screen

Tracked in [issue #3](https://github.com/adit-umakanth/trmnl-ticktick-v2/issues/3).

- [x] Add dashboard-local `Bedtime` and `WakeTime` SAM parameters and calculate when the next transition occurs. Use elapsed seconds to set BYOS refresh timing across midnight and daylight-saving changes.
- [x] Publish a sleep snapshot through the existing image route before reading credentials or constructing the TickTick client. Resume normal reads at wake-up.
- [x] Add an offline sleep preview and document configuration and device verification.
- [x] Run the offline suite, SAM lint, and the Linux arm64 container build. All 33 offline tests passed, and the opt-in live TickTick test was skipped. SAM lint and the build passed. Visually inspected the sleep preview and verified it was an 800×480 2-bit grayscale PNG at 2,231 bytes.
- [x] Verify a same-day sleep window locally. With bedtime at 10:00 p.m. and wake-up at 10:15 p.m., the server returned 900 seconds at bedtime and 600 seconds for a 10:05 p.m. request. At 10:15 p.m. it served the regular dashboard.
- [x] Verify the sleep screen and automatic wake-up on the physical OG. The owner confirmed the 10:00–10:15 p.m. window worked as expected on November 23, 2026. The overnight and daylight-saving timing checks used fixtures.
