# Copyright 2026 The RPent Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""LingBot RoboTwin runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RoboTwinModelSpec:
    """Values required by the LingBot EEF runtime."""

    policy_name: str
    robot_config_relpath: str
    norm_stats: str
    qwen_base: str
    camera_order: tuple[str, ...]
    state_layout: str
    action_layout: str
    use_length: int


MODEL_SPEC = RoboTwinModelSpec(
    policy_name="robotwin_eef",
    robot_config_relpath="configs/robot_configs/robotwin_eef.yaml",
    norm_stats="norm_stats/robotwin_eef.json",
    qwen_base="qwen_base",
    camera_order=("cam_high", "cam_left_wrist", "cam_right_wrist"),
    state_layout="eef16",
    action_layout="eef16",
    use_length=50,
)

ROBOTWIN_DASHBOARD_SPEC = {
    "task": {
        "command": "/rpent-task",
        "usage": "/rpent-task <task_name> <task_config> <seed>",
        "fields": (
            {"name": "task_name"},
            {
                "name": "task_config",
                "suggestions": ("demo_clean", "demo_randomized"),
            },
            {"name": "seed", "kind": "integer", "minimum": 0},
        ),
        "display": "{task_name} / {task_config} / seed {seed}",
        "output_slug": "{task_name}_{task_config}_s{seed}",
    },
    "runtime_components": (
        {"name": "env", "label": "ENV", "scope": "task"},
        {"name": "vla", "label": "VLA"},
    ),
    "frame_channels": (
        {"name": "camera", "label": "head camera"},
        {"name": "left_wrist", "label": "left wrist"},
        {"name": "right_wrist", "label": "right wrist"},
    ),
}


def env_runtime_contract(
    *, task_name: str, task_config: str, seed: int
) -> dict[str, object]:
    """Return the identity required from a RoboTwin EnvServer."""
    return {
        "runtime": "rlinf_robotwin_env",
        "api_version": 1,
        "task_name": task_name,
        "task_config": task_config,
        "seed": int(seed),
        "seed_mode": "exact",
        "action_layouts": ["qpos14", MODEL_SPEC.action_layout],
    }


def vla_runtime_contract() -> dict[str, object]:
    """Return the identity required from a LingBot RoboTwin server."""
    return {
        "runtime": "lingbotvla",
        "api_version": 1,
        "policy_name": MODEL_SPEC.policy_name,
        "camera_order": list(MODEL_SPEC.camera_order),
        "state_layout": MODEL_SPEC.state_layout,
        "action_layout": MODEL_SPEC.action_layout,
        "use_length": MODEL_SPEC.use_length,
    }
