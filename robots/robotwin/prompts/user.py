"""User prompt for one RoboTwin run."""

CELL = """- task: {{task_name}}
- requested_seed: {{seed}}
- initial_native_seed: {{initial_seed}}
- seed_mode: {{seed_mode}}
- task_config: {{task_config}}
- checkpoint: RLinf/LingBot-VLA-RoboTwin-EEF-ckpt1500
"""

BEGIN = """Follow the required read order, bind the current task's targets and
relations from fresh observation, then execute the first unmet recipe phase.
After each action verify its observable gate, preserve achieved relations, and
use the complete current task_language unchanged for every lingbot_act."""
