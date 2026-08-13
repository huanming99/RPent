# Copyright 2026 RPent Contributors
"""RPC client for RLinf's agent-facing RoboTwin environment APIs."""

from __future__ import annotations

from typing import Any, Literal

from rpent.utils.rpc import RpcClient

READ_TIMEOUT_S = 120.0
STATE_CHANGE_TIMEOUT_S = 600.0
ActionType = Literal["qpos", "ee"]


class RoboTwinExecutionError(RuntimeError):
    """Raised when a state-changing RPC does not explicitly succeed."""

    def __init__(self, method: str, error: Exception):
        self.method = method
        self.original_error = error
        super().__init__(
            f"{method} did not return a reliable result; the episode cannot continue: "
            f"{error}"
        )


class RoboTwinEnvClient:
    """Client for one standard RLinf ``RoboTwinEnv`` instance."""

    def __init__(self, client: RpcClient, *, expected_meta: dict[str, Any]):
        self._client = client
        self._fatal_error: RoboTwinExecutionError | None = None
        server_meta = self._client.call(
            "env.get_env_meta", timeout_s=READ_TIMEOUT_S
        )
        if server_meta != expected_meta:
            raise RuntimeError(
                "RoboTwin env metadata mismatch: "
                f"expected={expected_meta!r} actual={server_meta!r}. "
                "Connect to the EnvServer for the requested task and seed."
            )

    def _require_available(self) -> None:
        if self._fatal_error is not None:
            raise self._fatal_error

    def _read(
        self,
        method: str,
        *,
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        self._require_available()
        return self._client.call(
            f"env.{method}",
            kwargs=kwargs,
            timeout_s=READ_TIMEOUT_S,
        )

    def _execute_state_change(
        self,
        method: str,
        *,
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        self._require_available()
        try:
            result = self._client.call(
                f"env.{method}",
                kwargs=kwargs,
                timeout_s=STATE_CHANGE_TIMEOUT_S,
            )
        except Exception as error:
            fatal = RoboTwinExecutionError(method, error)
            self._fatal_error = fatal
            raise fatal from error
        status = result.get("episode_status") if isinstance(result, dict) else None
        if not isinstance(status, dict) or status.get("agent_valid") is not True:
            error = RuntimeError(
                f"{method} returned no explicit valid episode status: {result!r}"
            )
            fatal = RoboTwinExecutionError(method, error)
            self._fatal_error = fatal
            raise fatal from error
        return result

    def get_robot_state(self) -> dict[str, Any]:
        return self._read("get_robot_state")

    def capture_observation(self) -> dict[str, Any]:
        return self._read("capture_observation")

    def get_episode_status(self) -> dict[str, Any]:
        return self._read("get_episode_status")

    def plan_arm_path(self, arm: str, target_pose) -> dict[str, Any]:
        return self._read(
            "plan_arm_path",
            kwargs={"arm": arm, "target_pose": target_pose},
        )

    def execute_action_chunk(
        self,
        action_type: ActionType,
        actions,
    ) -> dict[str, Any]:
        return self._execute_state_change(
            "execute_action_chunk",
            kwargs={"action_type": action_type, "actions": actions},
        )

    def apply_qpos_updates(
        self,
        updates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return self._execute_state_change(
            "apply_qpos_updates",
            kwargs={"updates": updates},
        )

    def reset_exact(self, seed: int) -> dict[str, Any]:
        return self._execute_state_change("reset_exact", kwargs={"seed": seed})
