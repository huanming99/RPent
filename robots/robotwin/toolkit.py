# Copyright 2026 RPent Contributors
"""RPent toolkit for RLinf's agent-facing RoboTwin environment APIs."""

from __future__ import annotations

import json
from functools import partial
from pathlib import Path
from typing import Any

from robots.robotwin import tools
from robots.robotwin.env_client import RoboTwinExecutionError
from robots.robotwin.primitives import RoboTwinPrimitives
from robots.robotwin.resources import RoboTwinResourceReader
from rpent.dashboard.events import DashboardEventSink
from rpent.tools.state import EnvState
from rpent.tools.toolkit import RunFinalization, Toolkit, ToolResult, readonly
from rpent.utils.config import get_resources_dir
from rpent.utils.logging import get_output_dir


class RoboTwinToolkit(Toolkit):
    """Common RPent tools plus RoboTwin primitives."""

    _SPECS = {spec["name"]: spec for spec in tools.TOOLS_SPEC}
    _FRAME_ARTIFACTS = {
        "camera": "head_rgb.png",
        "left_wrist": "left_wrist_rgb.png",
        "right_wrist": "right_wrist_rgb.png",
    }

    def __init__(
        self,
        *,
        primitives_kwargs: dict[str, Any],
        dashboard_events: DashboardEventSink,
    ):
        state = EnvState(get_output_dir())
        super().__init__(dashboard_events=dashboard_events, state=state)
        self._output_dir = Path(get_output_dir())
        self._recipe: list[dict[str, Any]] = []
        self._latest_status: dict[str, Any] = {}
        self._runtime_failure: dict[str, Any] | None = None
        self._verified_finish_result: dict[str, Any] | None = None
        self._planner_finish_count = 0
        self._resource_reader = RoboTwinResourceReader(get_resources_dir("robotwin"))
        self._primitives = RoboTwinPrimitives(
            check_cancelled=self.raise_if_cancelled,
            **primitives_kwargs,
        )
        reset_result = self._primitives.reset()
        self._register_robotwin_tools()
        initial = self._capture("reset", reset_result, elapsed_s=0.0)
        record = self._state.latest_record()
        if record is not None:
            self._publish_step(record)
        initial_state = initial.get("state")
        if isinstance(initial_state, dict):
            self._latest_status = initial_state.get(
                "episode_status", self._latest_status
            )

    def _register_robotwin_tools(self) -> None:
        self._remove_generic_file_tools()
        self._tools.pop("finish", None)
        self.add_tool(
            "read_text_file",
            self._SPECS["read_text_file"],
            self._resource_reader.read_text_file,
        )
        self.add_tool(
            "list_dir",
            self._SPECS["list_dir"],
            self._resource_reader.list_dir,
        )
        self.add_tool(
            "view_env_state",
            self._SPECS["view_env_state"],
            partial(tools.view_env_state, state=self._state),
        )
        self.add_tool(
            "sample_world_xyz",
            self._SPECS["sample_world_xyz"],
            partial(tools.sample_world_xyz, self._state),
        )
        self.add_tool(
            "query_world_map",
            self._SPECS["query_world_map"],
            partial(tools.query_world_map, self._state),
        )
        self.add_tool("render", self._SPECS["render"], partial(self._step, "render"))
        for name in (
            "lingbot_act",
            "move_to",
            "rotate_wrist",
            "set_gripper",
            "release",
        ):
            self.add_tool(name, self._SPECS[name], partial(self._step, name))
        self.add_tool("finish", self._SPECS["finish"], self._finish)

    @readonly
    def _finish(self, *, status: str, summary: str) -> dict[str, Any]:
        result = self._primitives.finish(status=status, summary=summary)
        self._verified_finish_result = dict(result)
        self._planner_finish_count += 1
        episode_status = result.get("episode_status")
        if isinstance(episode_status, dict):
            self._latest_status = dict(episode_status)
        return result

    def before_execute_tool(
        self,
        name: str,
        input_dict: dict[str, Any],
    ) -> dict[str, Any] | None:
        if self._runtime_failure is not None:
            return dict(self._runtime_failure)
        native_success = (
            self._latest_status.get("agent_valid") is True
            and self._latest_status.get("eval_success") is True
        )
        if name != "finish" and native_success:
            return {
                "error": "native_success_requires_finish",
                "success": True,
                "required_next_tool": "finish",
                "message": "Native success is verified; call finish now.",
            }
        return None

    def _remove_generic_file_tools(self) -> None:
        for name in ("read_text_file", "write_text_file", "list_dir"):
            self._tools.pop(name, None)

    def _capture(
        self, command: str, result: dict[str, Any], *, elapsed_s: float
    ) -> dict[str, Any]:
        if self._runtime_failure is not None:
            return result
        try:
            status = self._primitives.status()
            self._latest_status = status
            observation = self._primitives.env.capture_observation()
        except Exception as error:
            self._runtime_failure = {
                "_finish": True,
                "_runtime_failure": True,
                "status": "failure",
                "success": False,
                "error": "robotwin_state_capture_error",
                "operation": command,
                "summary": str(error),
                "completed": False,
                "requested_steps": int(result.get("requested_steps", 0)),
                "executed_steps": int(result.get("executed_steps", 0)),
                "stop_reason": "runtime_failure",
            }
            raise
        record = tools.dump_observation(
            observation,
            env_state=self._state,
            status=status,
            log={
                "command": command,
                "result": result,
                "elapsed_s": elapsed_s,
            },
        )
        return tools.view_env_state(record.step_idx, state=self._state)

    def get_env_state(
        self,
        *,
        command: dict[str, Any],
        result: dict[str, Any],
        elapsed_s: float,
    ) -> dict[str, Any]:
        return self._capture(
            str(command.get("action", "unknown")),
            result,
            elapsed_s=elapsed_s,
        )

    def _step(self, name: str, **kwargs) -> dict[str, Any]:
        self._recipe.append({"action": name, **kwargs})
        try:
            self.raise_if_cancelled()
            if name == "render":
                return {"success": True}
            return getattr(self._primitives, name)(**kwargs)
        except RoboTwinExecutionError as error:
            self._runtime_failure = {
                "_finish": True,
                "_runtime_failure": True,
                "status": "failure",
                "success": False,
                "error": "robotwin_execution_transport_error",
                "operation": error.method,
                "summary": str(error),
                "completed": False,
                "requested_steps": 0,
                "executed_steps": 0,
                "stop_reason": "runtime_failure",
            }
            return dict(self._runtime_failure)

    def on_tool_event(self, name: str, result: ToolResult) -> None:
        """Observe tool execution without owning correctness-critical state."""
        del name, result

    @property
    def verified_finish_result(self) -> dict[str, Any] | None:
        if self._verified_finish_result is None:
            return None
        return dict(self._verified_finish_result)

    def finalize_run(
        self,
        *,
        planner_result: dict[str, Any] | None,
        planner_error: str | None,
    ) -> RunFinalization:
        if self._runtime_failure is None:
            try:
                self._latest_status = self._primitives.status()
            except Exception as error:
                self._runtime_failure = {
                    "_finish": True,
                    "_runtime_failure": True,
                    "status": "failure",
                    "success": False,
                    "error": "robotwin_final_status_error",
                    "summary": str(error),
                }
        agent_valid = self._latest_status.get("agent_valid") is True
        native_success = agent_valid and self._latest_status.get("eval_success") is True
        finish_count = self._planner_finish_count
        finish_called = finish_count > 0
        if not agent_valid:
            failure_class = "runtime_failure"
            failure_reason = "invalid_agent_episode"
        elif self._runtime_failure is not None:
            failure_class = "runtime_failure"
            failure_reason = "state_change_transport_error"
        elif planner_error:
            failure_class = "planner_failure"
            failure_reason = "planner_error"
        elif finish_count > 1:
            failure_class = "planner_failure"
            failure_reason = "duplicate_finish"
        elif native_success and not finish_called:
            failure_class = "planner_failure"
            failure_reason = "native_success_without_finish"
        elif not native_success:
            failure_class = "task_failure"
            failure_reason = "native_eval_success_false"
        else:
            failure_class = None
            failure_reason = None
        summary = {
            "native_success": native_success,
            "accepted_episode_success": bool(
                native_success
                and finish_count == 1
                and self._runtime_failure is None
                and planner_error is None
            ),
            "finish_called": finish_called,
            "finish_count": finish_count,
            "failure_class": failure_class,
            "failure_reason": failure_reason,
        }
        (self._output_dir / "robotwin_episode_result.json").write_text(
            json.dumps(summary, indent=2, default=tools._json_default)
        )
        final_result = self.verified_finish_result
        final_error = None
        if failure_class in {"planner_failure", "runtime_failure"}:
            final_result = self._runtime_failure or {
                "_runtime_failure": True,
                "status": "failure",
                "success": False,
                "summary": f"RoboTwin runtime gate failed: {failure_reason}",
            }
            final_error = f"RoboTwin hard failure: {failure_reason}"
        return RunFinalization(final_result=final_result, error=final_error)

    def write_recipe(self, recipe_tag: str) -> str:
        name = f"recipe_{recipe_tag}.jsonl"
        saved = self._state.save(name, self._recipe, step=None)
        if saved is None:
            raise RuntimeError(f"failed to save RoboTwin recipe artifact: {name}")
        return str(self._state.artifact_path(name, step=None))
