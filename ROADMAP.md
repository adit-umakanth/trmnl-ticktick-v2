# Roadmap

Features for the TickTick dashboard on TRMNL OG, in priority order. When a feature is selected for implementation, use [PRD.md](PRD.md) to define its behavior and acceptance criteria and [PLAN.md](PLAN.md) to track the work.

1. **Completed and verified — Show open, top-level Work Tasks from Active regardless of due date.** Work Tasks includes overdue, due-today, future-dated, and undated tasks in TickTick manual order. The owner confirmed the live preview from the configured Work list.
2. **Calculate the screen refresh interval dynamically.** Use upcoming dashboard changes to decide when the TRMNL should wake again. Decide which events should trigger a refresh, how often to poll for TickTick changes, and what interval to use after a failed read.
3. **Hide Work Tasks outside work hours and on weekends.** Show the card only during configured weekday work hours. Decide the default hours, which time zone to use, and how to use the space when the card is hidden.
4. **Update how subtasks appear in Todos.** Define the desired display for parents and subtasks, including completion and overflow. The current dashboard shows unchecked checklist entries indented beneath their parent task. Clarify whether this change applies to those entries, to TickTick subtasks, or to both.
