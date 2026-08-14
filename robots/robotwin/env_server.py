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

"""RPC server owning one RLinf RoboTwin environment."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import sys
from pathlib import Path
from typing import Any, Literal

import numpy as np

# Support direct execution from an RPent checkout before package imports.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rpent.utils.config import get_rlinf_repo_path
from rpent.utils.logging import get_logger
from rpent.utils.rpc import RpcFacade

logger = get_logger("robotwin_env_server")
ActionType = Literal["qpos", "ee"]

RLINF_REPO_PATH = get_rlinf_repo_path()
if RLINF_REPO_PATH is not None:
    if not (RLINF_REPO_PATH / "rlinf").is_dir():
        raise RuntimeError(
            f"explicit RLinf source override does not contain rlinf/: {RLINF_REPO_PATH}"
        )
    sys.path.insert(0, str(RLINF_REPO_PATH))

import rlinf  # noqa: E402
import robotwin  # noqa: E402
from omegaconf import OmegaConf  # noqa: E402
from rlinf.envs.robotwin.robotwin_env import RoboTwinEnv  # noqa: E402
from robotwin.assets import validate_root  # noqa: E402
from robotwin.config import load_task_config  # noqa: E402

_REQUIRED_ROBOTWIN_CAPABILITIES = (
    "apply_qpos_updates",
    "capture_observation",
    "execute_action_chunk",
    "get_episode_status",
    "get_robot_state",
    "plan_arm_path",
    "reset_exact",
)


_RUNTIME_DISTRIBUTIONS = (
    "rpent",
    "rlinf",
    "rlinf-robotwin-runtime",
    "rlinf-lingbotvla",
)


def _distribution_versions() -> dict[str, str]:
    """Return installed versions for the RoboTwin dependencies."""
    result = {}
    for distribution in _RUNTIME_DISTRIBUTIONS:
        try:
            result[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            result[distribution] = "not-installed"
    return result


def _require_active_environment(module_name: str, module_file: str) -> Path:
    """Require an imported runtime module to live in the active environment."""
    module_path = Path(module_file).resolve()
    if Path(sys.prefix).resolve() not in module_path.parents:
        raise RuntimeError(
            f"{module_name} was imported outside the active Python environment: "
            f"{module_path}"
        )
    return module_path


def _validate_rlinf_runtime() -> None:
    """Require the RoboTwin methods used by RPent."""
    missing = [
        name
        for name in _REQUIRED_ROBOTWIN_CAPABILITIES
        if not callable(getattr(RoboTwinEnv, name, None))
    ]
    if missing:
        raise RuntimeError(
            "the active RLinf installation does not provide the typed RoboTwin "
            f"Agent API; missing {missing}. Install RPent with .[robotwin] or "
            "set RPENT_RLINF_ROOT/RLINF_REPO_PATH to an explicit development "
            "checkout."
        )
    module_path = Path(rlinf.__file__).resolve()
    if RLINF_REPO_PATH is None:
        module_path = _require_active_environment("rlinf", rlinf.__file__)
    robotwin_path = _require_active_environment("robotwin", robotwin.__file__)
    distributions = _distribution_versions()
    source_override = RLINF_REPO_PATH is not None
    logger.info(
        "RoboTwin runtime: rlinf=%s robotwin=%s distributions=%s "
        "rlinf_source_override=%s",
        module_path,
        robotwin_path,
        distributions,
        source_override,
    )
    print(
        "robotwin_runtime "
        f"rlinf_module={module_path} robotwin_module={robotwin_path} "
        f"distributions={json.dumps(distributions, sort_keys=True)} "
        f"rlinf_source_override={str(source_override).lower()}",
        flush=True,
    )


_validate_rlinf_runtime()


def _to_numpy_tree(value: Any) -> Any:
    """Convert RPC results to numpy arrays and plain Python values."""
    if hasattr(value, "detach") and hasattr(value, "cpu") and hasattr(value, "numpy"):
        return value.detach().cpu().numpy()
    if isinstance(value, dict):
        return {key: _to_numpy_tree(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_numpy_tree(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_numpy_tree(item) for item in value)
    if isinstance(value, np.generic):
        return value.item()
    return value


class RoboTwinEnvFacade(RpcFacade):
    """Expose one RLinf RoboTwin environment over RPC."""

    def __init__(self, env: RoboTwinEnv, *, metadata: dict[str, Any]):
        super().__init__()
        self._env = env
        self._metadata = dict(metadata)

    def get_env_meta(self) -> dict[str, Any]:
        """Return immutable identity for endpoint compatibility checks."""
        return dict(self._metadata)

    def get_robot_state(self) -> dict[str, Any]:
        return self._env.get_robot_state(env_id=0)

    def capture_observation(self) -> dict[str, Any]:
        return self._env.capture_observation(env_id=0)

    def get_episode_status(self) -> dict[str, Any]:
        return self._env.get_episode_status(env_id=0)

    def plan_arm_path(self, arm: str, target_pose) -> dict[str, Any]:
        return self._env.plan_arm_path(0, arm, target_pose)

    def execute_action_chunk(self, action_type: ActionType, actions) -> dict[str, Any]:
        return self._env.execute_action_chunk(
            actions,
            action_type=action_type,
            env_id=0,
        )

    def apply_qpos_updates(self, updates: list[dict[str, Any]]) -> dict[str, Any]:
        return self._env.apply_qpos_updates(updates, env_id=0)

    def reset_exact(self, seed: int) -> dict[str, Any]:
        return self._env.reset_exact(0, int(seed))

    def _dispatch(self, method: str, args: tuple, kwargs: dict) -> Any:
        handlers = {
            "env.get_env_meta": self.get_env_meta,
            "env.get_robot_state": self.get_robot_state,
            "env.capture_observation": self.capture_observation,
            "env.get_episode_status": self.get_episode_status,
            "env.plan_arm_path": self.plan_arm_path,
            "env.execute_action_chunk": self.execute_action_chunk,
            "env.apply_qpos_updates": self.apply_qpos_updates,
            "env.reset_exact": self.reset_exact,
        }
        handler = handlers.get(method)
        if handler is None:
            raise ValueError(f"unknown RoboTwin env method: {method!r}")
        return _to_numpy_tree(handler(*args, **kwargs))


def build_env_cfg(
    *,
    task_name: str,
    task_config: str,
    seed: int,
    assets_root: str,
) -> Any:
    """Build a single-env RLinf config from packaged RoboTwin resources."""
    native_task_config = OmegaConf.create(load_task_config(task_config))
    native_task_config.task_name = task_name
    native_task_config.task_config = task_config
    native_task_config.ckpt_setting = "hybrid_lingbot"
    native_task_config.policy_name = "hybrid_lingbot"
    native_task_config.planner_backend = "curobo"
    native_task_config.eval_video_log = False
    native_task_config.render_freq = 0

    return OmegaConf.create(
        {
            "env_type": "robotwin",
            "initial_env_seeds": [int(seed)],
            "auto_reset": False,
            "ignore_terminations": False,
            "reward_coef": 1.0,
            "use_custom_reward": True,
            "use_rel_reward": True,
            "center_crop": False,
            "seed": seed,
            "group_size": 1,
            "use_fixed_reset_state_ids": True,
            "max_steps_per_rollout_epoch": 450,
            "max_episode_steps": 450,
            "is_eval": True,
            "assets_path": assets_root,
            "seeds_path": None,
            "video_cfg": {
                "save_video": False,
                "info_on_video": False,
                "video_base_dir": None,
            },
            "enable_offload": False,
            "task_config": native_task_config,
        }
    )


def make_env(
    task_name: str,
    task_config: str,
    seed: int,
    assets_root: str,
) -> RoboTwinEnv:
    """Construct the only simulator owner used by an RPent run."""
    assets_identity = validate_root(assets_root)
    assets_path = Path(assets_identity["root"])
    os.environ["ROBOTWIN_ASSETS_ROOT"] = str(assets_path)
    logger.info("RoboTwin assets: %s", assets_identity)
    print(
        f"robotwin_assets {json.dumps(assets_identity, sort_keys=True)}",
        flush=True,
    )
    cfg = build_env_cfg(
        task_name=task_name,
        task_config=task_config,
        seed=seed,
        assets_root=str(assets_path),
    )
    return RoboTwinEnv(
        cfg=cfg,
        num_envs=1,
        seed_offset=0,
        total_num_processes=1,
        worker_info=None,
        record_metrics=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=["socket", "http"], default="http")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--task-name", required=True)
    parser.add_argument(
        "--task-config",
        choices=("demo_clean", "demo_randomized"),
        required=True,
    )
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--assets-root", required=True)
    parser.add_argument("--parent-watch", action="store_true")
    args = parser.parse_args()

    env = make_env(
        args.task_name,
        args.task_config,
        args.seed,
        args.assets_root,
    )
    from robots.robotwin.spec import env_runtime_contract

    facade = RoboTwinEnvFacade(
        env,
        metadata=env_runtime_contract(
            task_name=args.task_name,
            task_config=args.task_config,
            seed=args.seed,
        ),
    )
    try:
        facade.serve(
            transport=args.transport,
            host=args.host,
            port=args.port,
            parent_watch=args.parent_watch,
        )
    finally:
        env.offload(clear_cache=True)


if __name__ == "__main__":
    main()
