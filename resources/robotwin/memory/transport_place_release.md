# Transport Place Release

## GM-TPR-001 Slow down near release and verify the postcondition

- Status: `supported`
- Condition: an object is near a receptacle, scale, pad, bin, plate, basket, or stacking/contact target
- Recommendation: Use smaller chunks near the final approach. When hold and target geometry are visible and collision-clear, a guarded vertical correction may use one current-state 0.005-0.010 m lower `move_to` with preserved x/y, orientation, and gripper and `substeps<=8`; re-observe and recompute before any next increment. Use short exact-prompt VLA when contact height is uncertain. Release only after the target relation is visually plausible, then observe the final state before spending remaining budget.
- Failure mode or antipattern: Failure mode varies by task; inspect supporting attempts before applying.
- Supporting attempts:
- `dump_bin_bigbin` attempt `001`: only success indicates controlled final release matters
- `move_stapler_pad` attempt `000`: object manipulation can fail after partial displacement
- `put_bottles_dustbin` attempt `006`: multi-object transport failures need per-object verification
- `place_object_scale` attempt `007`: placement on target surface needs final verification
- Contradictory attempts: tracked in the task-level raw attempts and unresolved memories; this compact leaf lists representative supporting/negative evidence only.
- Limits: Do not encode the clean seed release coordinates as reusable positions.

### Round-2 Cumulative Evidence

- Positive support: 17 attempt(s) from 10 distinct task(s).
- Negative evidence: 2 attempt(s) from 2 distinct task(s).
- Representative support: `handover_block/002`, `place_a2b_left/007`, `place_a2b_right/000`, `place_a2b_right/007`, `place_dual_shoes/004`
- Representative negative evidence: `move_stapler_pad/000`, `place_can_basket/005`

#### Supported refinements
- `handover_block/002`: When a VLA pick/place attempt leaves the object visibly at the target area but official success is still false and the nearby gripper is not fully open, prefer a minimal release/open action before any larger repositioning.
- `place_a2b_left/007`: For simple tabletop left/right placement tasks, when VLA has visibly moved the object to the correct side of the reference object but the object is still held or hovering, use one live-state 0.005-0.010 m lower `move_to`, preserve x/y/orientation/gripper, and re-observe before deciding whether another increment or release is safe.
- `place_a2b_right/000`: For a simple "place A to the right of B" tabletop task, let the VLA perform the initial grasp/local interaction with the original task language, rebind the reference object's current head-world position, then use current observation to choose an allowed transport and terminal approach before release and official-success verification.
- `run_3/move_stapler_pad/000`: For target-footprint placement, use a small current-observation correction only after release/clearance shows an edge-biased near-success state.
- `run_3/put_bottles_dustbin/001`: For receptacle tasks with several objects, verify containment of the current object before moving the next object near the receptacle.
- `run_3/put_bottles_dustbin/005`: Near-release analytic shaping was only conditional support when the held-object/receptacle relation was visible. If geometry is collision-clear, use at most one observation-bound lower `move_to` increment before re-observing; prefer short exact-prompt VLA for contact-rich completion and still verify containment.

#### Negative evidence
- `move_stapler_pad/000`: After release and clearance, verify the object is centered well inside the colored target footprint
- `place_can_basket/005`: For container tasks that also require lifting the receptacle, verify the object is visibly contained before applying a receptacle-lift primitive assist.

## GM-TPR-002 Avoid blind long transport after an ambiguous grasp

- Status: `experimental`
- Condition: the object may be slipping, occluded, or not held
- Recommendation: Re-observe and rebind the object/EEF relation first. A long move with an uncertain hold frequently turns a recoverable failure into a terminal one.
- Failure mode or antipattern: Avoid this antipattern under the stated condition.
- Supporting attempts:
- `dump_bin_bigbin` attempt `001`: only success indicates controlled final release matters
- `move_stapler_pad` attempt `000`: object manipulation can fail after partial displacement
- `put_bottles_dustbin` attempt `006`: multi-object transport failures need per-object verification
- `place_object_scale` attempt `007`: placement on target surface needs final verification
- Contradictory attempts: tracked in the task-level raw attempts and unresolved memories; this compact leaf lists representative supporting/negative evidence only.
- Limits: Apply as a no-reset budget rule, not as a task-specific recipe.

### Round-2 Cumulative Evidence

- Positive support: 2 attempt(s) from 2 distinct task(s).
- Negative evidence: 0 attempt(s) from 0 distinct task(s).
- Representative support: `dump_bin_bigbin/006`, `place_a2b_left/003`

#### Supported refinements
- `dump_bin_bigbin/006`: For container-pour tasks with an upright small bin, do not analytically transport after an ambiguous rim contact.
- `place_a2b_left/003`: For pick-transport-place tasks, if a VLA or contact attempt leaves a gripper closed near the object but no lift has been observed, perform a short lift/clear check before transport.
