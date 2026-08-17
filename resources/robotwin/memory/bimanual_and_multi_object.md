# Bimanual And Multi Object

## GM-BMO-001 Preserve completed objects one at a time

- Status: `supported`
- Condition: a task has multiple objects, stacking, binning, handover, or two-arm coordination
- Recommendation: After each object/subgoal, verify it remains stable before manipulating the next one. Prefer role separation between arms when one hand can stabilize or stay clear.
- Failure mode or antipattern: Failure mode varies by task; inspect supporting attempts before applying.
- Supporting attempts:
- `put_bottles_dustbin` attempt `006`: multi-object failure evidence
- `stack_blocks_three` attempt `003`: multi-object ordering/stacking failure evidence
- `handover_mic` attempt `000`: task-level success evidence if present
- `pick_dual_bottles` attempt `002`: two-object task evidence if present
- Contradictory attempts: tracked in the task-level raw attempts and unresolved memories; this compact leaf lists representative supporting/negative evidence only.
- Limits: This is a shared operation pattern, not an instruction to reuse any single task's full trajectory.

### Round-2 Cumulative Evidence

- Positive support: 3 attempt(s) from 3 distinct task(s).
- Negative evidence: 1 attempt(s) from 1 distinct task(s).
- Representative support: `blocks_ranking_rgb/007`, `place_cans_plasticbox/000`, `stack_blocks_two/007`
- Representative negative evidence: `place_dual_shoes/007`

#### Supported refinements
- `blocks_ranking_rgb/007`: When a small-block ordering task has a remaining out-of-order block after VLA has placed the other blocks, avoid repeated broad VLA or blind pushing.
- `place_cans_plasticbox/000`: For multi-object receptacle placement, if both objects are visually in the receptacle but `eval_success=false`, preserve the near-success state and use short, verified recovery: open/release any close gripper, try only small reachable retreats, then use a `chunks=1` VLA refinement if the remaining blocker is unclear.
- `run_3/put_bottles_dustbin/001`: For multi-object receptacle placement, handle one object at a time and verify the current object is contained before moving to the next.
- `stack_blocks_two/007`: For two-block stacking when the red block must become the base, splitting the opening VLA behavior into two short exact-prompt chunks can create a useful red pre-grasp verification gate before committing to longer continuous manipulation.

#### Negative evidence
- `place_dual_shoes/007`: For orientation-sensitive multi-object placement into a container, do not treat both objects being inside the receptacle as sufficient progress if the required tip/orientation relation is not visually correct.

## GM-BMO-002 Avoid disturbing a completed partial arrangement

- Status: `experimental`
- Condition: a previous object is already placed, stacked, inserted, or contained
- Recommendation: Do not send broad VLA chunks through the completed region unless the current observation shows enough clearance. Use a guarded approach or alternate arm if available.
- Failure mode or antipattern: Avoid this antipattern under the stated condition.
- Supporting attempts:
- `put_bottles_dustbin` attempt `006`: multi-object failure evidence
- `stack_blocks_three` attempt `003`: multi-object ordering/stacking failure evidence
- `handover_mic` attempt `000`: task-level success evidence if present
- `pick_dual_bottles` attempt `002`: two-object task evidence if present
- Contradictory attempts: tracked in the task-level raw attempts and unresolved memories; this compact leaf lists representative supporting/negative evidence only.
- Limits: Clean evidence only; randomized obstacle and pose variation still need validation.

### Round-2 Cumulative Evidence

- Positive support: 4 attempt(s) from 3 distinct task(s).
- Negative evidence: 1 attempt(s) from 1 distinct task(s).
- Representative support: `dump_bin_bigbin/006`, `place_dual_shoes/004`, `stack_blocks_three/004`, `stack_blocks_three/007`
- Representative negative evidence: `place_phone_stand/007`

#### Supported refinements
- `dump_bin_bigbin/006`: For container-pour tasks with an upright small bin, do not analytically transport after an ambiguous rim contact.
- `place_dual_shoes/004`: For container placement tasks, if the objects visually appear placed but official success is still false and an open gripper remains low inside or immediately over the container, prefer a small current-state upward retreat before issuing more VLA motion.
- `stack_blocks_three/004`: Clear the non-working gripper with small reachable moves before manipulating the next object.

#### Negative evidence
- `place_phone_stand/007`: For small flat-object pick-place tasks, do not treat an isolated VLA contact chunk followed by gripper closure as a hold unless the object visibly leaves the table or appears in the wrist view between the fingers.
