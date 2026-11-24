# Roadmap

Upcoming and in-progress features for the TickTick dashboard on TRMNL OG, in priority order. When a feature is selected for implementation, use [PRD.md](PRD.md) to define its behavior and acceptance criteria and [PLAN.md](PLAN.md) to track the work. Remove completed features from this roadmap and record their verification in [PLAN.md](PLAN.md).

1. **Calculate the screen refresh interval dynamically.** Use upcoming dashboard changes to decide when the TRMNL should wake again. Decide which events should trigger a refresh, how often to poll for TickTick changes, and what interval to use after a failed read.
2. **Update how subtasks appear in Todos.** Define the desired display for parents and subtasks, including completion and overflow. The current dashboard shows unchecked checklist entries indented beneath their parent task. Clarify whether this change applies to those entries, to TickTick subtasks, or to both.
