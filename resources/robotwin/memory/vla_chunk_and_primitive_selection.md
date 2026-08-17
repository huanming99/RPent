# VLA Chunk And Primitive Selection

## GM-VLA-001 Use short chunks around contact, longer chunks only for open-loop approach

- Status: `supported`
- Condition: approaching a grasp/release/contact point, recovering from ambiguity, or manipulating small/unstable objects
- Recommendation: `chunks=1` or `chunks=2` preserve observation opportunities around irreversible contact. Longer chunks are better suited to coarse approach when the scene is uncluttered and the next subgoal is visually obvious.
- Failure mode or antipattern: Failure mode varies by task; inspect supporting attempts before applying.
- Supporting attempts:
- `dump_bin_bigbin` attempt `001`: success came from one clean attempt; compare with failed attempts before promoting task recipe
- `beat_block_hammer` attempt `002`: VLA/primitive handoffs can stall without verification
- `stack_blocks_three` attempt `003`: multi-step construction benefits from shorter verified segments
- `move_stapler_pad` attempt `000`: long execution after partial progress can miss the semantic target
- Contradictory attempts: tracked in the task-level raw attempts and unresolved memories; this compact leaf lists representative supporting/negative evidence only.
- Limits: The VLA instruction remains the original task_language; memory must not become a new VLA prompt.

### Round-2 Cumulative Evidence

- Positive support: 6 attempt(s) from 4 distinct task(s).
- Negative evidence: 0 attempt(s) from 0 distinct task(s).
- Representative support: `move_playingcard_away/005`, `move_playingcard_away/007`, `place_cans_plasticbox/000`, `place_shoe/004`, `stack_blocks_two/004`

#### Supported refinements
- `move_playingcard_away/005`: For VLA-driven pick-move tasks where a supported baseline uses a longer first LingBot chunk followed by a short terminal chunk, splitting the long chunk into single chunks with render checkpoints can preserve success while improving contact/release observability.
- `move_playingcard_away/007`: For small-object move-away tasks where a short VLA segment visibly moves/contact-grasps the object but official success is still false, a single small primitive assist can be inserted before the final short VLA chunk.
- `place_cans_plasticbox/000`: For multi-object receptacle placement, if both objects are visually in the receptacle but `eval_success=false`, preserve the near-success state and use short, verified recovery: open/release any close gripper, try only small reachable retreats, then use a `chunks=1` VLA refinement if the remaining blocker is unclear.
- `run_3/put_bottles_dustbin/001`: Short exact-prompt VLA chunks can preserve observation checkpoints during multi-object receptacle placement.

## GM-VLA-002 Switch to primitives for precise guarded motion after VLA localizes the object

- Status: `experimental`
- Condition: the VLA has moved the EEF near the object or target but exact final relation still needs controlled motion
- Recommendation: Use `move_to`, `set_gripper`, `release`, or `rotate_wrist` only after rebinding from visible state. For a collision-clear guarded vertical approach, lower from the latest achieved EE pose by one 0.005-0.010 m `move_to` increment with preserved x/y/orientation/gripper and `substeps<=8`, then re-observe before another increment. Use short exact-prompt VLA for contact-rich or visually guided approach. Primitive success is a motion-result signal, not semantic success.
- Failure mode or antipattern: Failure mode varies by task; inspect supporting attempts before applying.
- Supporting attempts:
- `dump_bin_bigbin` attempt `001`: success came from one clean attempt; compare with failed attempts before promoting task recipe
- `beat_block_hammer` attempt `002`: VLA/primitive handoffs can stall without verification
- `stack_blocks_three` attempt `003`: multi-step construction benefits from shorter verified segments
- `move_stapler_pad` attempt `000`: long execution after partial progress can miss the semantic target
- Contradictory attempts: tracked in the task-level raw attempts and unresolved memories; this compact leaf lists representative supporting/negative evidence only.
- Limits: Do not force primitives when the task requires visual servoing or bimanual coordination better handled by VLA.

### Round-2 Cumulative Evidence

- Positive support: 12 attempt(s) from 8 distinct task(s).
- Negative evidence: 1 attempt(s) from 1 distinct task(s).
- Representative support: `click_alarmclock/001`, `click_alarmclock/002`, `click_alarmclock/007`, `open_microwave/004`, `place_a2b_right/000`
- Representative negative evidence: `lift_pot/007`

#### Supported refinements
- `click_alarmclock/001`: For contact-only button tasks, if a supported LingBot recipe places the tool above the correct target area but `eval_success` remains false, verify the hover with current images/state and use a small guarded analytic press derived from the current EE/TCP offset and same-step surface geometry.
- `click_alarmclock/002`: For click-style contact tasks, if LingBot localizes the target but stops high with official eval still false, preserve the VLA-aligned target area and perform a guarded primitive press using the current TCP-to-EE offset.
- `click_alarmclock/007`: For contact-only button tasks, if a visually salient printed panel or label is near the target but VLA contact fails, re-observe with the wrist camera and distinguish the raised physical control from the printed/label-like surface before using an analytic press.
- `run_3/put_bottles_dustbin/005`: Near-release analytic shaping was not sufficient by itself; subsequent short VLA and containment verification were still required.

#### Negative evidence
- `lift_pot/007`: Prefer very small verified increments or a short VLA re-balance, and treat primitive `success=true` as insufficient if `final_dist_m` is large.
