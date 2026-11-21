# Engineering instructions

- Follow PRD.md and PLAN.md. Keep the fixture-based workflow runnable at each milestone and commit verified milestones separately.
- Use the official TickTick API for read-only integration. Treat live behavior as unverified until compared against the account and app. Keep fixtures synthetic or scrubbed.
- Keep network, rendering, and AWS integration independently testable. Run relevant tests and report skipped or blocked verification.
- Keep credentials and personal TickTick content out of Git, URLs, logs, and checked-in fixtures.
- Obtain explicit approval before incurring costs, deploying infrastructure, or making irreversible changes. Physical OG compatibility requires an actual device check.
