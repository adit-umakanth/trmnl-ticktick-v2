# Engineering instructions

- Follow [PRD.md](PRD.md) and [PLAN.md](PLAN.md). Keep the fixture-based workflow runnable at each milestone and commit verified milestones separately.
- Read [ROADMAP.md](ROADMAP.md) when planning feature work. Use its priority order when proposing what to work on next. When a feature is selected for implementation, document its requirements and acceptance criteria in PRD.md and its implementation steps in PLAN.md.
- Use the official TickTick API for read-only integration. Treat live behavior as unverified until compared against the account and app. Keep fixtures synthetic or scrubbed.
- Keep network, rendering, and AWS integration independently testable. Run relevant tests and report skipped or blocked verification.
- Keep credentials and personal TickTick content out of Git, URLs, logs, and checked-in fixtures.
- Obtain explicit approval before incurring costs, deploying infrastructure, or making irreversible changes. Physical OG compatibility requires an actual device check.

Roadmap feature 1 (Work Tasks from `Active`) is complete. See [PLAN.md](PLAN.md) for fixture and live preview verification.
