# Grasp And Hold

## GM-GH-001 Verify hold before transport

- Status: `supported`
- Condition: a task requires moving a held object, tool, mug, block, bottle, or container
- Recommendation: After close or VLA grasp, perform a short lift or observation check before large transport. If the object did not move with the gripper, switch to a regrasp or alternate approach instead of continuing the planned transport.
- Failure mode or antipattern: Failure mode varies by task; inspect supporting attempts before applying.
- Supporting attempts:
- `dump_bin_bigbin` attempt `001`: success required maintaining object control through transport/release
- `beat_block_hammer` attempt `002`: failed hammer attempts show contact without durable control is not enough
- `hanging_mug` attempt `001`: failed hanging attempts show lift/hold needs visual confirmation
- `place_object_scale` attempt `007`: partial placement without final success
- Contradictory attempts: tracked in the task-level raw attempts and unresolved memories; this compact leaf lists representative supporting/negative evidence only.
- Limits: This is not a fixed gripper-width rule; use current observation and task object geometry.

### Round-2 Cumulative Evidence

- Positive support: 10 attempt(s) from 8 distinct task(s).
- Negative evidence: 0 attempt(s) from 0 distinct task(s).
- Representative support: `beat_block_hammer/007`, `blocks_ranking_rgb/002`, `place_a2b_left/000`, `place_a2b_left/003`, `place_bread_skillet/004`

#### Supported refinements
- `beat_block_hammer/007`: Use a short lift or equivalent observation gate to verify that the tool moves with the gripper, then use a short VLA chunk for the terminal contact from the current held-tool geometry.
- `blocks_ranking_rgb/002`: For `blocks_ranking_rgb`, after VLA establishes the red/green partial order, verify the blue hold by lift/world-map z before high transport.
- `place_a2b_left/000`: For small-object pick-place tasks, do not treat VLA gripper closure or wrist proximity as a verified grasp.

## GM-GH-002 Avoid treating contact as grasp

- Status: `experimental`
- Condition: the gripper/tool touches the object but the object is not visibly controlled
- Recommendation: Do not proceed to place, hang, stack, or hit as if the object were secured. Continuing usually consumes no-reset budget and can create an unrecoverable scene.
- Failure mode or antipattern: Avoid this antipattern under the stated condition.
- Supporting attempts:
- `dump_bin_bigbin` attempt `001`: success required maintaining object control through transport/release
- `beat_block_hammer` attempt `002`: failed hammer attempts show contact without durable control is not enough
- `hanging_mug` attempt `001`: failed hanging attempts show lift/hold needs visual confirmation
- `place_object_scale` attempt `007`: partial placement without final success
- Contradictory attempts: tracked in the task-level raw attempts and unresolved memories; this compact leaf lists representative supporting/negative evidence only.
- Limits: The evidence is clean exploration failure evidence, not a randomized proof.

### Round-2 Cumulative Evidence

- Positive support: 3 attempt(s) from 2 distinct task(s).
- Negative evidence: 1 attempt(s) from 1 distinct task(s).
- Representative support: `beat_block_hammer/007`, `place_a2b_left/000`, `place_a2b_left/003`
- Representative negative evidence: `place_phone_stand/007`

#### Supported refinements
- `beat_block_hammer/007`: For hammer/tool contact tasks, do not advance from gripper closure alone to a strike.
- `place_a2b_left/000`: For small-object pick-place tasks, do not treat VLA gripper closure or wrist proximity as a verified grasp.
- `place_a2b_left/003`: For pick-transport-place tasks, if a VLA or contact attempt leaves a gripper closed near the object but no lift has been observed, perform a short lift/clear check before transport.

#### Negative evidence
- `place_phone_stand/007`: For small flat-object pick-place tasks, do not treat an isolated VLA contact chunk followed by gripper closure as a hold unless the object visibly leaves the table or appears in the wrist view between the fingers.

