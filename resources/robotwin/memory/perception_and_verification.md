# Perception And Verification

## GM-PV-001 Official success is the only promotion gate

- Status: `supported`
- Condition: a primitive reports success, an object appears moved, or a VLA segment finishes without error
- Recommendation: Treat this as local progress only. Before promoting a recipe or declaring recovery complete, check the driver final state or latest `eval_success` field; primitive success is not task success.
- Failure mode or antipattern: Failure mode varies by task; inspect supporting attempts before applying.
- Supporting attempts:
- `dump_bin_bigbin` attempt `001`: single official success among seven failures; final eval is the only reliable success signal
- `place_object_scale` attempt `007`: partial progress still failed official eval, showing visual/primitive success is insufficient
- `move_stapler_pad` attempt `000`: near-progress attempt without official success; must verify semantic end condition
- `stack_blocks_three` attempt `003`: partial stack evidence but official failure; verify after each contact
- Contradictory attempts: tracked in the task-level raw attempts and unresolved memories; this compact leaf lists representative supporting/negative evidence only.
- Limits: Supported only by clean-seed evidence; randomized generalization still needs strict eval.

### Round-2 Cumulative Evidence

- Positive support: 25 attempt(s) from 20 distinct task(s).
- Negative evidence: 0 attempt(s) from 0 distinct task(s).
- Representative support: `blocks_ranking_rgb/004`, `click_alarmclock/002`, `dump_bin_bigbin/006`, `handover_block/002`, `move_playingcard_away/007`

#### Supported refinements
- `blocks_ranking_rgb/004`: After release, if official success is false, clear occluding grippers and verify row alignment plus spacing before using broad VLA recovery.
- `click_alarmclock/002`: For click-style contact tasks, if LingBot localizes the target but stops high with official eval still false, preserve the VLA-aligned target area and perform a guarded primitive press using the current TCP-to-EE offset.
- `dump_bin_bigbin/006`: For container-pour tasks with an upright small bin, do not analytically transport after an ambiguous rim contact.

## GM-PV-002 Re-observe after contact-changing actions

- Status: `supported`
- Condition: the robot has grasped, released, hit, stacked, inserted, or pushed an object
- Recommendation: Use the next state/images before choosing the next primitive or VLA chunk. Do not assume a grasp, placement, or impact succeeded from the command result alone.
- Failure mode or antipattern: Failure mode varies by task; inspect supporting attempts before applying.
- Supporting attempts:
- `dump_bin_bigbin` attempt `001`: single official success among seven failures; final eval is the only reliable success signal
- `place_object_scale` attempt `007`: partial progress still failed official eval, showing visual/primitive success is insufficient
- `move_stapler_pad` attempt `000`: near-progress attempt without official success; must verify semantic end condition
- `stack_blocks_three` attempt `003`: partial stack evidence but official failure; verify after each contact
- Contradictory attempts: tracked in the task-level raw attempts and unresolved memories; this compact leaf lists representative supporting/negative evidence only.
- Limits: Do not read hidden object state or task checkers; use agent-visible state, images, logs, and final official signal.

### Round-2 Cumulative Evidence

- Positive support: 13 attempt(s) from 11 distinct task(s).
- Negative evidence: 2 attempt(s) from 2 distinct task(s).
- Representative support: `blocks_ranking_rgb/002`, `blocks_ranking_rgb/004`, `click_alarmclock/007`, `move_playingcard_away/005`, `place_mouse_pad/003`
- Representative negative evidence: `move_stapler_pad/000`, `place_can_basket/005`

#### Supported refinements
- `blocks_ranking_rgb/002`: For `blocks_ranking_rgb`, after VLA establishes the red/green partial order, verify the blue hold by lift/world-map z before high transport.
- `blocks_ranking_rgb/004`: After release, if official success is false, clear occluding grippers and verify row alignment plus spacing before using broad VLA recovery.
- `click_alarmclock/007`: For contact-only button tasks, if a visually salient printed panel or label is near the target but VLA contact fails, re-observe with the wrist camera and distinguish the raised physical control from the printed/label-like surface before using an analytic press.
- `run_3/move_stapler_pad/000`: After release and gripper clearance, re-observe the object-target relation and require the object to be fully inside the target footprint before treating placement as terminal.

#### Negative evidence
- `move_stapler_pad/000`: After release and clearance, verify the object is centered well inside the colored target footprint
- `place_can_basket/005`: For container tasks that also require lifting the receptacle, verify the object is visibly contained before applying a receptacle-lift primitive assist.
- `run_3/hanging_mug/000-007`: Correlated failure cluster; proximity/contact near a support fixture is not a verified load-bearing support relation.
