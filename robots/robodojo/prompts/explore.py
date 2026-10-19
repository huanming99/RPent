# Copyright 2026 The RPent Authors.
"""RoboDojo exploration guidance; runtime guards enforce attempt limits."""

RULES = """Explore session {{session_number}} of {{session_max}}.
This session allows {{explore_attempts_per_session}} attempts including the
initial episode (0 means no attempt-count limit; other run limits still apply).
reset restores the same task, seed group and layout, not a new random scene.
Re-run perception and do not reuse pixels or coordinates across resets.
An unsolved finish is refused while a finite attempt budget remains. After
native success, stop motion, save evidence and finish; reset is then refused.

Before resetting, save an attempt report under {{output_dir}}/attempts/ and
append handoff notes under {{memory_inbox}}/wip/. Read previous notes before
trying a materially different strategy. Never write directly to published
memory. Put publishable Markdown proposals directly in {{memory_inbox}} with
YAML frontmatter delimited by --- lines. For task-family proposals, use
scope: task-family, suite: robodojo, regime: {{env_cfg_type}}, task_id: {{task}},
and task_language containing the observed natural-language instruction.
For global proposals, use scope: global, a descriptive id and title,
applies_when, and kind: primitive, perception, strategy, failure, or infra.
Both scopes require evidence.cells: [{{recipe_tag}}] and confidence:
single-shot, probable, or verified. A single scene supports single-shot only.
Do not generalize one scene's successful coordinates to other layouts. The runner exports motion
commands only from the successful attempt after the last reset."""
