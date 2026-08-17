# RoboTwin Curated Global Memory Candidate


This is the candidate Global Memory index for the next clean exploration iteration.
Read this index first, then open only the leaf files relevant to the current task and observation.
Do not load raw attempt directories as memory context.

## Leaf Index

- [Perception and verification](perception_and_verification.md): official success gates, post-action observation, primitive-result limits.
- [Grasp and hold](grasp_and_hold.md): hold verification, contact-versus-grasp failures.
- [Transport, place, and release](transport_place_release.md): guarded final approach, release verification, transport risks.
- [VLA chunk and primitive selection](vla_chunk_and_primitive_selection.md): chunk sizing, VLA-to-primitive handoffs.
- [Bimanual and multi-object](bimanual_and_multi_object.md): preserving partial progress in multi-object or two-arm tasks.
- [Recovery and budget](recovery_and_budget.md): no-reset recovery discipline and budget management.

## Scope Limits

- Evidence is from demo_clean exact seeds only.
- Rule status is limited to `experimental` or `supported`; no Round-1 rule is verified for randomized eval.
- These rules do not contain hidden object state, check_success logic, or GT object poses.
- Executed clean-seed coordinates in raw JSONL are evidence, not transferable world-coordinate rules.
- LingBot-VLA must still receive the original task_language, not memory text.
- Agent-authored GM proposals are preserved as provenance, but wrapper-generated `No new candidate` files are not treated as positive evidence.
- `PROVENANCE.json` is historical audit data, not runtime guidance. Do not load
  retired-action references from provenance into a new episode.
