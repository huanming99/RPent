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

"""RoboTwin environment extension backed by RLinf RoboTwinEnv."""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from robots.robotwin.prompt_bundle import system_prompt, user_prompt
from robots.robotwin.spec import (
    MODEL_SPEC,
    ROBOTWIN_DASHBOARD_SPEC,
    env_runtime_contract,
    vla_runtime_contract,
)
from rpent.dashboard.events import DashboardEventSink, RuntimeStatusEvent
from rpent.envs.env_spec import EnvSpec, RunConfig
from rpent.envs.prompt_bundle import PromptBundle
from rpent.utils.config import get_repo_root

if TYPE_CHECKING:
    from rpent.utils.daemon import ProcessDaemon

TASK_CONFIGS = ("demo_clean", "demo_randomized")


@dataclass(frozen=True, slots=True)
class RoboTwinRuntimePaths:
    """Validated runtime resources for a RoboTwin episode."""

    assets_root: Path | None
    model_path: Path | None


def get_env_spec() -> EnvSpec:
    return EnvSpec(
        name="robotwin",
        prompts=PromptBundle(system=system_prompt, user=user_prompt),
        add_cli_args=_add_cli_args,
        parse_config=_parse_config,
        init_shared_runtime=_init_shared_runtime,
        init_task_runtime=_init_task_runtime,
        init_runtime=_init_runtime,
        dashboard=ROBOTWIN_DASHBOARD_SPEC,
    )


def get_toolkit(
    *,
    primitives_kwargs: dict[str, Any],
    dashboard_events: DashboardEventSink,
):
    from robots.robotwin.toolkit import RoboTwinToolkit

    return RoboTwinToolkit(
        primitives_kwargs=primitives_kwargs,
        dashboard_events=dashboard_events,
    )


def _add_cli_args(parser: argparse.ArgumentParser, use_dashboard: bool) -> None:
    required = not use_dashboard
    parser.add_argument("--task-name", required=required)
    parser.add_argument("--seed", type=int, default=100002)
    parser.add_argument(
        "--task-language-file",
        default=None,
        help="Evaluation seed JSON containing the exact instruction for this task/seed.",
    )
    parser.add_argument(
        "--task-config",
        choices=TASK_CONFIGS,
        default="demo_randomized",
        help="Native RoboTwin task YAML.",
    )
    parser.add_argument(
        "--robotwin-assets-root",
        default=os.environ.get("ROBOTWIN_ASSETS_ROOT"),
        help=(
            "Root containing the RoboTwin assets directory. "
            "Defaults to ROBOTWIN_ASSETS_ROOT."
        ),
    )
    parser.add_argument("--env-endpoint", default=None)
    parser.add_argument("--vla-endpoint", default=None)
    parser.add_argument(
        "--vla-model-path",
        default=os.environ.get("LINGBOT_MODEL_PATH"),
        help=("LingBot checkpoint. Defaults to LINGBOT_MODEL_PATH when set."),
    )
    parser.add_argument(
        "--lingbot-robot-config",
        default=os.environ.get("LINGBOT_ROBOT_CONFIG"),
        help=(
            "Path to the LingBot FeatureTransform robot config. Defaults to "
            "the model snapshot's configs/robot_configs/robotwin_eef.yaml."
        ),
    )
    parser.add_argument("--cuda-device", default=None)
    parser.add_argument(
        "--env-cuda-device",
        default=None,
        help="CUDA_VISIBLE_DEVICES value for the RoboTwin EnvServer.",
    )
    parser.add_argument(
        "--vla-cuda-device",
        default=None,
        help="CUDA_VISIBLE_DEVICES value for the LingBot VLA server.",
    )


def _parse_config(args: argparse.Namespace) -> RunConfig:
    if not args.task_name:
        raise ValueError("--task-name is required")
    env_cuda_device, vla_cuda_device = _resolve_cuda_devices(args)
    args._robotwin_runtime_paths = _resolve_runtime_paths(args)
    output_dir = args.output_dir
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H:%M:%S")
        output_dir = (
            get_repo_root()
            / "logs"
            / f"{timestamp}_robotwin_{args.task_name}_s{args.seed}"
        )
    output_dir = Path(output_dir)
    recipe_tag = f"robotwin_{args.task_name}_s{args.seed}"
    task_config = getattr(args, "task_config", "demo_randomized")
    initial_seed = int(args.seed)
    task_language = _load_task_language(
        args.task_language_file,
        task_name=args.task_name,
        task_config=task_config,
        seed=initial_seed,
    )
    args._robotwin_task_language = task_language
    return RunConfig(
        recipe_tag=recipe_tag,
        output_dir=output_dir,
        prompt_vars={
            "task_name": args.task_name,
            "seed": args.seed,
            "initial_seed": initial_seed,
            "seed_mode": "exact",
            "task_config": task_config,
            "instruction": task_language,
        },
        task_desc={
            "env": "robotwin",
            "task_name": args.task_name,
            "requested_seed": args.seed,
            "initial_native_seed": initial_seed,
            "seed_mode": "exact",
            "task_config": task_config,
            "instruction": task_language,
            "task_language_file": str(Path(args.task_language_file).resolve()),
            "policy_name": MODEL_SPEC.policy_name,
            "action_layout": MODEL_SPEC.action_layout,
            "env_cuda_device": env_cuda_device,
            "vla_cuda_device": vla_cuda_device,
        },
    )


def _load_task_language(
    source: str | None, *, task_name: str, task_config: str, seed: int
) -> str:
    """Load and validate the exact evaluation instruction for a task/seed."""
    if not source:
        raise ValueError("--task-language-file is required for RoboTwin evaluation")
    path = Path(source).expanduser().resolve()
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read task language file {path}: {error}") from error
    task = payload.get(task_name)
    if not isinstance(task, dict):
        raise ValueError(f"task {task_name!r} is absent from {path}")
    configured = task.get("task_config")
    if configured != task_config:
        raise ValueError(
            f"task_config mismatch for {task_name}: requested={task_config!r}, "
            f"file={configured!r}"
        )
    seeds = task.get("seeds", [])
    if seed not in seeds:
        raise ValueError(f"seed {seed} is not listed for task {task_name!r} in {path}")
    instruction = task.get("instructions", {}).get(str(seed))
    if not isinstance(instruction, str) or not instruction.strip():
        raise ValueError(f"instruction for {task_name} seed {seed} is absent from {path}")
    return instruction.strip()


def _rpc_client(endpoint: str):
    from rpent.utils.http_rpc import HttpRpcClient
    from rpent.utils.rpc import parse_endpoint
    from rpent.utils.socket_rpc import SocketRpcClient

    protocol, host, port = parse_endpoint(endpoint)
    if protocol == "http":
        return HttpRpcClient(f"http://{host}:{port}")
    if protocol == "socket":
        return SocketRpcClient(host, port)
    raise ValueError(f"unsupported RPC protocol: {protocol!r}")


def _wait_for_tcp(host: str, port: int, daemon, timeout_s: float = 900.0) -> None:
    deadline = time.time() + timeout_s
    last_error = None
    while time.time() < deadline:
        if daemon is not None and daemon.poll() is not None:
            raise RuntimeError(
                f"{daemon.name} exited before listening; inspect its log"
            )
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return
        except OSError as error:
            last_error = error
            time.sleep(0.5)
    raise TimeoutError(f"LingBot server not ready: {last_error}")


def _parse_vla_endpoint(endpoint: str) -> tuple[str, int]:
    value = endpoint.split("://", 1)[-1]
    host, separator, port_text = value.rpartition(":")
    if not separator or not host or not port_text:
        raise ValueError("--vla-endpoint must be [ws://]host:port")
    return host, int(port_text)


def _require_directory(path: Path, option: str) -> None:
    if not path.is_dir():
        raise ValueError(f"{option} directory not found: {path}")


def _resolve_runtime_paths(args: argparse.Namespace) -> RoboTwinRuntimePaths:
    return RoboTwinRuntimePaths(
        assets_root=_resolve_env_runtime_path(args),
        model_path=_resolve_vla_runtime_path(args),
    )


def _resolve_env_runtime_path(args: argparse.Namespace) -> Path | None:
    assets_root: Path | None = None
    if args.env_endpoint is None:
        configured_assets = getattr(args, "robotwin_assets_root", None)
        if not configured_assets:
            raise ValueError(
                "--robotwin-assets-root is required when launching the local "
                "env server; set ROBOTWIN_ASSETS_ROOT or pass the option explicitly"
            )
        assets_root = Path(configured_assets).expanduser().resolve()
        from robotwin.assets import validate_root

        validate_root(assets_root)
    return assets_root


def _resolve_vla_runtime_path(args: argparse.Namespace) -> Path | None:
    model_path: Path | None = None
    if args.vla_endpoint is None:
        configured_model = getattr(args, "vla_model_path", None)
        if not configured_model:
            raise ValueError(
                "--vla-model-path is required when launching the local VLA "
                "server; set LINGBOT_MODEL_PATH or pass the option explicitly"
            )
        model_path = Path(configured_model).expanduser().resolve()
        _validate_local_model_files(model_path)
        _resolve_lingbot_robot_config(args, model_path)
    return model_path


def _validate_local_model_files(model_path: Path) -> None:
    required = [
        model_path / "config.json",
        model_path / "lingbotvla_cli.yaml",
        model_path / MODEL_SPEC.norm_stats,
        model_path / MODEL_SPEC.qwen_base,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise ValueError(f"LingBot model snapshot is incomplete: {missing}")


def _resolve_lingbot_robot_config(
    args: argparse.Namespace,
    model_path: Path,
) -> Path:
    configured = getattr(args, "lingbot_robot_config", None)
    path = (
        Path(configured).expanduser()
        if configured
        else model_path / MODEL_SPEC.robot_config_relpath
    ).resolve()
    if not path.is_file():
        raise ValueError(
            "LingBot robot config not found: "
            f"{path}. Pass --lingbot-robot-config or download the complete "
            "pinned model snapshot."
        )
    return path


def _subprocess_env(cuda_device: str | None, **extra: str) -> dict[str, str]:
    env = os.environ.copy()
    if cuda_device is not None:
        env["CUDA_VISIBLE_DEVICES"] = str(cuda_device)
    env.update(extra)
    return env


def _resolve_cuda_devices(
    args: argparse.Namespace,
) -> tuple[str | None, str | None]:
    shared = getattr(args, "cuda_device", None)
    env_device = getattr(args, "env_cuda_device", None)
    vla_device = getattr(args, "vla_cuda_device", None)
    if shared is not None and (env_device is not None or vla_device is not None):
        raise ValueError(
            "--cuda-device cannot be combined with --env-cuda-device or "
            "--vla-cuda-device"
        )
    if shared is not None:
        value = str(shared)
        return value, value
    return (
        str(env_device) if env_device is not None else None,
        str(vla_device) if vla_device is not None else None,
    )


def _init_shared_runtime(
    args: argparse.Namespace,
    output_dir: Path,
    dashboard_events: DashboardEventSink,
) -> tuple[list["ProcessDaemon"], dict[str, Any]]:
    daemons: list["ProcessDaemon"] = []
    dashboard_events.emit(RuntimeStatusEvent("vla", "starting"))
    try:
        result = _init_shared_runtime_impl(args, output_dir, daemons)
    except Exception as exc:
        for daemon in reversed(daemons):
            daemon.stop()
        dashboard_events.emit(RuntimeStatusEvent("vla", "failed", error=exc))
        raise
    dashboard_events.emit(RuntimeStatusEvent("vla", "ready"))
    return result


def _init_task_runtime(
    args: argparse.Namespace,
    output_dir: Path,
    dashboard_events: DashboardEventSink,
) -> tuple[list["ProcessDaemon"], dict[str, Any]]:
    daemons: list["ProcessDaemon"] = []
    dashboard_events.emit(RuntimeStatusEvent("env", "starting"))
    try:
        result = _init_task_runtime_impl(args, output_dir, daemons)
    except Exception as exc:
        for daemon in reversed(daemons):
            daemon.stop()
        dashboard_events.emit(RuntimeStatusEvent("env", "failed", error=exc))
        raise
    dashboard_events.emit(RuntimeStatusEvent("env", "ready"))
    return result


def _init_runtime(
    args: argparse.Namespace,
    output_dir: Path,
    dashboard_events: DashboardEventSink,
) -> tuple[list["ProcessDaemon"], dict[str, Any]]:
    shared_daemons: list["ProcessDaemon"] = []
    try:
        shared_daemons, shared_kwargs = _init_shared_runtime(
            args, output_dir, dashboard_events
        )
        task_daemons, task_kwargs = _init_task_runtime(
            args, output_dir, dashboard_events
        )
    except Exception:
        for daemon in reversed(shared_daemons):
            daemon.stop()
        raise
    # Stop the task environment before the shared VLA.
    return [*task_daemons, *shared_daemons], {**task_kwargs, **shared_kwargs}


def _init_shared_runtime_impl(
    args: argparse.Namespace,
    output_dir: Path,
    daemons: list["ProcessDaemon"],
) -> tuple[list["ProcessDaemon"], dict[str, Any]]:
    from robots.robotwin.vla_client import LingBotVLAClient
    from rpent.utils.daemon import ProcessDaemon, pick_free_port

    _, vla_cuda_device = _resolve_cuda_devices(args)
    model_path = _resolve_vla_runtime_path(args)
    if args.vla_endpoint is None:
        assert model_path is not None
        robot_config = _resolve_lingbot_robot_config(args, model_path)

    if args.vla_endpoint is None:
        host, vla_port = "127.0.0.1", pick_free_port()
        norm_path = model_path / MODEL_SPEC.norm_stats
        qwen_path = model_path / MODEL_SPEC.qwen_base
        vla_daemon = ProcessDaemon(
            "lingbot_vla_server",
            [
                sys.executable,
                str(get_repo_root() / "robots" / "robotwin" / "vla_server.py"),
                "--model-path",
                str(model_path),
                "--use-length",
                str(MODEL_SPEC.use_length),
                "--port",
                str(vla_port),
                "--norm-path",
                str(norm_path),
                "--lingbot-robot-config",
                str(robot_config),
                "--parent-watch",
            ],
            env=_subprocess_env(
                vla_cuda_device,
                QWEN25_PATH=str(qwen_path),
            ),
            log_path=str(output_dir / "lingbot_vla_server.log"),
        )
        vla_daemon.start()
        daemons.append(vla_daemon)
        _wait_for_tcp(host, vla_port, vla_daemon)
    else:
        host, vla_port = _parse_vla_endpoint(args.vla_endpoint)
        _wait_for_tcp(host, vla_port, None)

    model = LingBotVLAClient(
        host=host,
        port=vla_port,
    )
    model.validate_contract(vla_runtime_contract())
    return daemons, {"model": model}


def _init_task_runtime_impl(
    args: argparse.Namespace,
    output_dir: Path,
    daemons: list["ProcessDaemon"],
) -> tuple[list["ProcessDaemon"], dict[str, Any]]:
    from robots.robotwin.env_client import RoboTwinEnvClient
    from rpent.utils.daemon import ProcessDaemon, pick_free_port
    from rpent.utils.rpc import wait_for_ready

    env_cuda_device, _ = _resolve_cuda_devices(args)
    assets_path = _resolve_env_runtime_path(args)
    assets_root = str(assets_path) if assets_path else None
    initial_seed = int(args.seed)

    if args.env_endpoint is None:
        if assets_root is None:
            raise ValueError(
                "--robotwin-assets-root is required to launch the env server"
            )
        host, env_port = "127.0.0.1", pick_free_port()
        env_daemon = ProcessDaemon(
            "robotwin_env_server",
            [
                sys.executable,
                str(get_repo_root() / "robots" / "robotwin" / "env_server.py"),
                "--task-name",
                args.task_name,
                "--task-config",
                args.task_config,
                "--seed",
                str(initial_seed),
                "--task-language",
                args._robotwin_task_language,
                "--assets-root",
                assets_root,
                "--transport",
                "http",
                "--host",
                host,
                "--port",
                str(env_port),
                "--parent-watch",
            ],
            env=_subprocess_env(
                env_cuda_device,
                ROBOTWIN_ASSETS_ROOT=assets_root,
            ),
            log_path=str(output_dir / "robotwin_env_server.log"),
        )
        env_daemon.start()
        daemons.append(env_daemon)
        env_rpc = _rpc_client(f"http://{host}:{env_port}")
        wait_for_ready(env_rpc, daemon=env_daemon, timeout_s=900)
    else:
        env_rpc = _rpc_client(args.env_endpoint)
        wait_for_ready(env_rpc)

    return daemons, {
        "env": RoboTwinEnvClient(
            env_rpc,
            expected_meta=env_runtime_contract(
                task_name=args.task_name,
                task_config=args.task_config,
                seed=initial_seed,
            ),
        ),
        "seed": initial_seed,
        "seed_mode": "exact",
    }
