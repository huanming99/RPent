# Recovery And Budget

## GM-RB-001 Prefer minimal recovery inside no-reset attempts

- Status: `supported`
- Condition: a grasp slips, placement is ambiguous, or the target relation is partly achieved
- Recommendation: Choose the smallest recovery that preserves current progress: observe, short VLA, guarded primitive, or regrasp. Do not restart the plan mentally; RESET is forbidden.
- Failure mode or antipattern: Failure mode varies by task; inspect supporting attempts before applying.
- Supporting attempts:
- `dump_bin_bigbin` attempt `001`: success should be compared against seven failures, not blindly replayed
- `beat_block_hammer` attempt `002`: failed attempts show budget can be exhausted by repeated uncertain actions
- `move_stapler_pad` attempt `000`: partial progress can be lost by over-recovery
- `stack_blocks_three` attempt `003`: multi-step attempts require budget discipline
- Contradictory attempts: tracked in the task-level raw attempts and unresolved memories; this compact leaf lists representative supporting/negative evidence only.
- Limits: This rule concerns no-reset exploration and future eval discipline only.

### Round-2 Cumulative Evidence

- Positive support: 4 attempt(s) from 4 distinct task(s).
- Negative evidence: 1 attempt(s) from 1 distinct task(s).
- Representative support: `dump_bin_bigbin/007`, `place_a2b_left/000`, `stack_blocks_three/007`, `turn_switch/007`
- Representative negative evidence: `place_phone_stand/007`

#### Supported refinements
- `dump_bin_bigbin/007`: For dump-bin style container tasks, if an early VLA chunk closes the gripper near or inside the small bin but does not visibly lift, tilt, or pour, use a minimal recovery checkpoint before repeating contact.
- `place_a2b_left/000`: For small-object pick-place tasks, do not treat VLA gripper closure or wrist proximity as a verified grasp.
- `stack_blocks_three/007`: For block stacking, treat release as incomplete until the block remains upright after gripper opening and withdrawal.

#### Negative evidence
- `place_phone_stand/007`: For small flat-object pick-place tasks, do not treat an isolated VLA contact chunk followed by gripper closure as a hold unless the object visibly leaves the table or appears in the wrist view between the fingers.
- `run_3/hanging_mug/000-007`: Correlated failure cluster; if repeated rack-adjacent terminal attempts do not improve the support relation, return to hold/orientation verification instead of spending budget on similar actions.

## GM-RB-002 Stop testing before a near-success state is damaged

- Status: `experimental`
- Condition: the scene appears close to success but final signal is not yet confirmed
- Recommendation: Do not perform exploratory actions just to collect more evidence. If one verification or gentle correction remains, prioritize that over role adherence.
- Failure mode or antipattern: Avoid this antipattern under the stated condition.
- Supporting attempts:
- `dump_bin_bigbin` attempt `001`: success should be compared against seven failures, not blindly replayed
- `beat_block_hammer` attempt `002`: failed attempts show budget can be exhausted by repeated uncertain actions
- `move_stapler_pad` attempt `000`: partial progress can be lost by over-recovery
- `stack_blocks_three` attempt `003`: multi-step attempts require budget discipline
- Contradictory attempts: tracked in the task-level raw attempts and unresolved memories; this compact leaf lists representative supporting/negative evidence only.
- Limits: Requires visual judgment; if current observation contradicts the memory, trust observation.

### Round-2 Cumulative Evidence

- Positive support: 6 attempt(s) from 6 distinct task(s).
- Negative evidence: 1 attempt(s) from 1 distinct task(s).
- Representative support: `blocks_ranking_rgb/007`, `dump_bin_bigbin/007`, `handover_block/002`, `place_a2b_right/003`, `stack_bowls_two/004`
- Representative negative evidence: `move_pillbottle_pad/006`

#### Supported refinements
- `blocks_ranking_rgb/007`: When a small-block ordering task has a remaining out-of-order block after VLA has placed the other blocks, avoid repeated broad VLA or blind pushing.
- `dump_bin_bigbin/007`: A render plus a guarded current-state clearance/open move can preserve the upright bin and still leave budget for a final VLA completion sequence.
- `handover_block/002`: When a VLA pick/place attempt leaves the object visibly at the target area but official success is still false and the nearby gripper is not fully open, prefer a minimal release/open action before any larger repositioning.

#### Negative evidence
- `move_pillbottle_pad/006`: A close-only action can topple or displace a near-success placement.
