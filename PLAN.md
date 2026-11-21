# Implementation milestones

1. Review this plan, PRD.md, and AGENTS.md. Initialize Git and commit the documents.
2. Run the authenticated read-only integration check documented in README.md. Confirm Inbox, Work, and Time Blocking membership, due dates, sort order, block start/end times, and habit schedules and check-in semantics against the app. Record only scrubbed evidence. If a required capability is absent, stop before adopting any substitute.
3. Run the fixture renderer and the domain/render tests. Inspect the split time block header, stacked task cards with checklist rows, the habits strip, and the outage preview and verify the 2-bit grayscale PNG encoding, antialiased type, and byte limits.
4. Run the handler/storage tests, `sam validate --lint`, and `sam build`. Verify the source-IP policy, binary response, snapshot isolation, and sanitization. Prepare the regional cost estimate and deployment/rollback instructions.
5. Obtain approval before any cost or deployment. Verify both allowed and denied networks, then verify setup, normal rendering, outage, and recovery on the physical OG.

Commit each milestone after its checks pass. Fixture-backed results and authenticated results are recorded separately.
