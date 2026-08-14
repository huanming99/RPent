# Copyright 2026 RPent Contributors
"""RoboTwin primitives built on RLinf environment APIs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np

from robots.robotwin.env_client import RoboTwinEnvClient
from robots.robotwin.spec import MODEL_SPEC
from robots.robotwin.vla_client import LingBotVLAClient


def _qmult(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    w1, x1, y1, z1 = left
    w2, x2, y2, z2 = right
    return np.asarray(
        [
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        ],
        dtype=np.float64,
    )


class RoboTwinPrimitives:
    """Compose RoboTwin operations from the RLinf environment API."""

    def __init__(
        self,
        *,
        env: RoboTwinEnvClient,
        model: LingBotVLAClient,
        seed: int,
        check_cancelled: Callable[[], None],
        seed_mode: str = "exact",
    ):
        if seed_mode != "exact":
            raise ValueError("standard RoboTwin integration requires seed_mode='exact'")
        self.env = env
        self.model = model
        self.seed = int(seed)
        self._check_cancelled = check_cancelled
        self.policy_actions = 0
        self.native_actions = 0

    def reset(
        self,
        *,
        instruction: str | None = None,
        feasibility_precheck: bool = True,
    ) -> dict[str, Any]:
        del instruction, feasibility_precheck
        self.model.reset()
        result = self.env.reset_exact(self.seed)
        return {**result, "success": True}

    @staticmethod
    def _completion(
        *, requested: int, executed: int, status: dict[str, Any]
    ) -> dict[str, Any]:
        step_lim = status.get("step_lim")
        budget_exhausted = step_lim is not None and int(
            status.get("take_action_cnt", 0)
        ) >= int(step_lim)
        completed = executed == requested
        if status.get("agent_valid") is not True:
            stop_reason = "runtime_failure"
        elif status.get("eval_success") is True:
            stop_reason = "native_success"
        elif budget_exhausted:
            stop_reason = "budget_exhausted"
        elif completed:
            stop_reason = "completed"
        else:
            stop_reason = "runtime_failure"
        return {
            "completed": completed,
            "requested_steps": requested,
            "executed_steps": executed,
            "stop_reason": stop_reason,
        }

    def lingbot_act(
        self, *, chunks: int = 4, use_length: int = 50, prompt: str | None = None
    ) -> dict[str, Any]:
        if int(chunks) < 1:
            raise ValueError("chunks must be at least 1")
        if int(use_length) != MODEL_SPEC.use_length:
            raise ValueError(
                f"RoboTwin LingBot requires use_length={MODEL_SPEC.use_length}"
            )
        executed = 0
        requested = int(chunks) * MODEL_SPEC.use_length
        native_prompt = None
        for _ in range(int(chunks)):
            self._check_cancelled()
            status = self.env.get_episode_status()
            if status.get("agent_valid") is not True:
                raise RuntimeError(
                    "RoboTwin agent episode is invalid: "
                    f"{status.get('invalid_reason') or 'unknown reason'}"
                )
            step_lim = status.get("step_lim")
            budget_exhausted = step_lim is not None and int(
                status.get("take_action_cnt", 0)
            ) >= int(step_lim)
            if status.get("eval_success") is True or budget_exhausted:
                break
            observation = self.env.capture_observation()
            native_prompt = observation["task_language"]
            actions = self.model.infer(observation)[: MODEL_SPEC.use_length]
            self._check_cancelled()
            result = self.env.execute_action_chunk("ee", actions)
            count = int(result.get("executed_actions", 0))
            executed += count
            self.policy_actions += count
            self.native_actions += count
            self._check_cancelled()
        status = self.env.get_episode_status()
        return {
            **self._completion(
                requested=requested,
                executed=executed,
                status=status,
            ),
            "success": True,
            "prompt": native_prompt,
            "agent_prompt_ignored": prompt is not None,
            "ignored_agent_prompt": prompt,
            "episode_status": status,
        }

    def move_to(
        self,
        *,
        arm: str,
        xyz: list[float],
        quat: list[float] | None = None,
        gripper: float | None = None,
        substeps: int = 25,
        _primitive_name: str = "move_to",
    ) -> dict[str, Any]:
        del _primitive_name
        if int(substeps) < 0:
            raise ValueError("substeps must be non-negative")
        self._check_cancelled()
        state = self.env.get_robot_state()
        if quat is None:
            key = "left_eef_pose" if arm == "left" else "right_eef_pose"
            quat = np.asarray(state[key], dtype=np.float64)[3:].tolist()
        target = np.asarray([*xyz, *quat], dtype=np.float64)
        planned = self.env.plan_arm_path(arm, target)
        self._check_cancelled()
        if planned["status"] != "Success" or planned.get("position") is None:
            return {
                "completed": False,
                "requested_steps": 0,
                "executed_steps": 0,
                "stop_reason": "plan_failed",
                "success": False,
                "plan_status": planned["status"],
                "hint": "target may be unreachable or in collision",
            }
        path = np.asarray(planned["position"], dtype=np.float64)
        if substeps == 1:
            path = path[-1:]
        elif substeps >= 2 and len(path) > substeps:
            indices = np.linspace(0, len(path) - 1, substeps).astype(int)
            path = path[indices]
        updates = [
            {"arm": arm, "arm_qpos": waypoint, "gripper": gripper} for waypoint in path
        ]
        execution = self.env.apply_qpos_updates(updates)
        executed = int(execution.get("executed_actions", 0))
        self.native_actions += executed
        self._check_cancelled()
        status = execution.get("episode_status") or self.env.get_episode_status()
        final = self.env.get_robot_state()
        key = "left_eef_pose" if arm == "left" else "right_eef_pose"
        final_pose = np.asarray(final[key], dtype=np.float64)
        return {
            **execution,
            **self._completion(
                requested=len(updates),
                executed=executed,
                status=status,
            ),
            "success": True,
            "plan_status": planned["status"],
            "waypoints": len(path),
            "final_eef_xyz": final_pose[:3].tolist(),
            "final_dist_m": float(
                np.linalg.norm(final_pose[:3] - np.asarray(xyz, dtype=np.float64))
            ),
        }

    def rotate_wrist(
        self,
        *,
        arm: str,
        delta_yaw_deg: float,
        gripper: float | None = None,
        substeps: int = 25,
    ) -> dict[str, Any]:
        state = self.env.get_robot_state()
        key = "left_eef_pose" if arm == "left" else "right_eef_pose"
        pose = np.asarray(state[key], dtype=np.float64)
        yaw = np.deg2rad(float(delta_yaw_deg))
        world_z = np.asarray([np.cos(yaw / 2), 0.0, 0.0, np.sin(yaw / 2)])
        result = self.move_to(
            arm=arm,
            xyz=pose[:3].tolist(),
            quat=_qmult(world_z, pose[3:]).tolist(),
            gripper=gripper,
            substeps=substeps,
            _primitive_name="rotate_wrist",
        )
        result["requested_delta_yaw_deg"] = float(delta_yaw_deg)
        return result

    def set_gripper(
        self,
        *,
        arm: str,
        val: float,
        steps: int = 10,
        _primitive_name: str = "set_gripper",
    ) -> dict[str, Any]:
        del _primitive_name
        if int(steps) < 1:
            raise ValueError("steps must be at least 1")
        self._check_cancelled()
        state = self.env.get_robot_state()
        current = float(state[f"{arm}_gripper"])
        step_count = int(steps)
        target = float(val)
        values = [
            current + (target - current) * index / step_count
            for index in range(1, step_count + 1)
        ]
        updates = [{"arm": arm, "gripper": float(value)} for value in values]
        execution = self.env.apply_qpos_updates(updates)
        executed = int(execution.get("executed_actions", 0))
        self.native_actions += executed
        self._check_cancelled()
        status = execution.get("episode_status") or self.env.get_episode_status()
        now = self.env.get_robot_state()
        return {
            **execution,
            **self._completion(
                requested=len(updates),
                executed=executed,
                status=status,
            ),
            "success": True,
            "gripper_val": float(now[f"{arm}_gripper"]),
        }

    def release(self, *, arm: str, val: float = 1.0, steps: int = 10) -> dict[str, Any]:
        return self.set_gripper(
            arm=arm,
            val=val,
            steps=steps,
            _primitive_name="release",
        )

    def status(self) -> dict[str, Any]:
        return {
            **self.env.get_episode_status(),
            "policy_actions": self.policy_actions,
            "native_actions": self.native_actions,
        }

    def finish(self, *, status: str, summary: str) -> dict[str, Any]:
        native = self.status()
        requested_success = status.lower() == "success"
        verified_success = bool(
            native.get("agent_valid") is True and native.get("eval_success") is True
        )
        reported_status = (
            "success"
            if verified_success
            else ("failure" if requested_success else status)
        )
        return {
            "_finish": True,
            "status": reported_status,
            "summary": summary,
            "requested_success": requested_success,
            "success": verified_success,
            "episode_status": native,
        }
