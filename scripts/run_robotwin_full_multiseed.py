#!/usr/bin/env python3
"""Resumable four-GPU scheduler for the package-first RoboTwin evaluation."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import threading
import time
from typing import Any


V3 = Path("/mnt/public2/zhanghuanming/projects/rpent-rlinf-test-v3")
RPENT = V3 / "RPent"
PYTHON = V3 / ".venv-robotwin/bin/python"
RPENT_BIN = V3 / ".venv-robotwin/bin/rpent"
SEED_TABLE = V3 / "robotwin_randomized_eval_seeds.json"
OUTPUT = RPENT / "result_multiseed"
ASSETS = Path("/mnt/public2/zhanghuanming/projects/rpent-rlinf-test/RoboTwin")
MODEL = V3 / "local-vla-robotwin-eef"
RLINF_ENV = V3 / ".venv-robotwin/lib/python3.11/site-packages/rlinf/envs/robotwin/robotwin_env.py"
VECTOR_ENV = V3 / ".venv-robotwin/lib/python3.11/site-packages/robotwin/envs/vector_env.py"
EXPECTED_HEADS = {
    "RPent": "2791a694fd02a74ce2629e95209f0b56a0fb21a2",
    "RLinf": "2dd1b2ffedcef6bccb00d469644b34737ffbdde6",
    "RoboTwin": "11d2d4ba1ba4819ebf63bb91ba0c5dfd4b0f81f2",
}
GPUS = (0, 1, 2, 3)
MAX_ATTEMPTS = 1
PROCESS_TIMEOUT_S = 4500

LOCK = threading.Lock()
STOP = threading.Event()
ACTIVE: dict[int, subprocess.Popen] = {}
RECORDS: dict[str, dict[str, Any]] = {}


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def snapshot_files(paths: list[Path]) -> dict[str, str]:
    """Return stable RPent-relative SHA256 records for an experiment snapshot."""
    return {
        str(path.relative_to(RPENT)): sha256(path)
        for path in sorted(paths, key=lambda item: str(item))
    }


def git_head(repo: Path) -> str:
    return subprocess.check_output(
        ["/usr/bin/git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()


def source_preflight() -> dict[str, Any]:
    for repo, expected in EXPECTED_HEADS.items():
        actual = git_head(V3 / repo)
        if actual != expected:
            raise RuntimeError(f"{repo} HEAD changed: expected={expected}, actual={actual}")

    vector_text = VECTOR_ENV.read_text(encoding="utf-8")
    reset_block = vector_text.split("    def reset(self, env_seed=None):", 1)[1].split(
        "    def get_obs(self):", 1
    )[0]
    if "get_info(" in reset_block or "play_once(" in reset_block:
        raise RuntimeError("anti-cheat gate: real SubEnv.reset invokes get_info/play_once")
    setup_block = vector_text.split("    def setup_task(self):", 1)[1].split(
        "    def create_instruction(self):", 1
    )[0]
    required = ("task = class_decorator", "episode_info = task.get_info()", "task.close_env()")
    if not all(token in setup_block for token in required):
        raise RuntimeError("anti-cheat gate: temporary metadata-task lifecycle changed")
    rlinf_text = RLINF_ENV.read_text(encoding="utf-8")
    exact_block = rlinf_text.split("    def reset_exact(", 1)[1].split(
        "    @property\n    def device", 1
    )[0]
    if "check_seed(" in exact_block or "play_once(" in exact_block or "get_info(" in exact_block:
        raise RuntimeError("anti-cheat gate: reset_exact invokes expert feasibility code")
    return {
        "checked_at": now(),
        "vector_env": str(VECTOR_ENV),
        "vector_env_sha256": sha256(VECTOR_ENV),
        "rlinf_env": str(RLINF_ENV),
        "rlinf_env_sha256": sha256(RLINF_ENV),
        "conclusion": (
            "get_info runs only on a disposable metadata task; the real Agent reset "
            "does not invoke get_info, play_once, check_seed, or expert feasibility"
        ),
    }


def load_jobs() -> list[dict[str, Any]]:
    data = json.loads(SEED_TABLE.read_text(encoding="utf-8"))
    jobs: list[dict[str, Any]] = []
    for task, row in data.items():
        if task == "_meta":
            continue
        task_config = row.get("task_config")
        if task_config != "demo_randomized":
            raise RuntimeError(f"unexpected task_config for {task}: {task_config!r}")
        for seed_value in row.get("seeds", []):
            seed = int(seed_value)
            instruction = row.get("instructions", {}).get(str(seed))
            if not isinstance(instruction, str) or not instruction.strip():
                raise RuntimeError(f"missing instruction for {task}/{seed}")
            jobs.append(
                {
                    "task": task,
                    "task_config": task_config,
                    "seed": seed,
                    "instruction": instruction.strip(),
                }
            )
    identities = {(job["task"], job["seed"]) for job in jobs}
    if len(jobs) != 250 or len(identities) != 250:
        raise RuntimeError(f"expected 250 unique jobs, got jobs={len(jobs)} unique={len(identities)}")
    return jobs


def job_key(job: dict[str, Any]) -> str:
    return f"{job['task']}/seed_{job['seed']}"


def output_dir(job: dict[str, Any]) -> Path:
    return OUTPUT / job["task"] / f"seed_{job['seed']}"


def command(job: dict[str, Any], gpu: int) -> list[str]:
    return [
        str(RPENT_BIN),
        "--env", "robotwin",
        "--task-name", job["task"],
        "--task-config", job["task_config"],
        "--seed", str(job["seed"]),
        "--task-language-file", str(SEED_TABLE),
        "--planner", "codex",
        "--model", "gpt-5.5",
        "--reasoning-effort", "high",
        "--planner-timeout-s", "3600",
        "--max-turns", "100",
        "--cuda-device", str(gpu),
        "--robotwin-assets-root", str(ASSETS),
        "--vla-model-path", str(MODEL),
        "--output-dir", str(output_dir(job)),
        "--verbose",
    ]


def initial_state_audit(path: Path, job: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads((path / "states.json").read_text(encoding="utf-8"))
        first = payload["steps"][0]
        state = first["state"]
        status = state["episode_status"]
        observed_instruction = state["task_language"]
        observed_seed = int(status["actual_seed"])
        clean = (
            status.get("eval_success") is False
            and int(status.get("take_action_cnt", -1)) == 0
            and int(status.get("policy_actions", -1)) == 0
            and int(status.get("native_actions", -1)) == 0
            and observed_seed == job["seed"]
            and observed_instruction == job["instruction"]
        )
        return {
            "passed": clean,
            "eval_success": status.get("eval_success"),
            "take_action_cnt": status.get("take_action_cnt"),
            "policy_actions": status.get("policy_actions"),
            "native_actions": status.get("native_actions"),
            "actual_seed": observed_seed,
            "task_language_matches": observed_instruction == job["instruction"],
        }
    except (OSError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
        return {"passed": False, "error": f"{type(error).__name__}: {error}"}


def classify(path: Path, returncode: int, job: dict[str, Any]) -> dict[str, Any]:
    audit = initial_state_audit(path, job)
    result: dict[str, Any] = {
        "complete": False,
        "success": None,
        "kind": "infra_failure",
        "returncode": returncode,
        "initial_state_audit": audit,
    }
    try:
        episode = json.loads((path / "robotwin_episode_result.json").read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return result
    if not audit["passed"]:
        result["kind"] = "anti_cheat_violation"
        return result
    if episode.get("finish_called") is True:
        success = bool(episode.get("native_success") and episode.get("accepted_episode_success"))
        failure_class = episode.get("failure_class")
        if success:
            result.update(complete=True, success=True, kind="success")
        elif failure_class in (None, "task_failure"):
            result.update(complete=True, success=False, kind="task_failure")
        else:
            result.update(kind=failure_class or "infra_failure")
    return result


def atomic_json(path: Path, value: Any) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def create_or_validate_manifest(path: Path, snapshot: dict[str, Any]) -> None:
    """Create one immutable experiment manifest or reject configuration drift."""
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        existing_snapshot = {
            key: value for key, value in existing.items() if key != "created_at"
        }
        if existing_snapshot != snapshot:
            raise RuntimeError(
                "experiment manifest mismatch: prompt, resources, source, or "
                "runtime configuration changed inside an existing result root"
            )
        return
    atomic_json(path, {"created_at": now(), **snapshot})


def update_summary() -> None:
    counts: dict[str, int] = {}
    for record in RECORDS.values():
        kind = record.get("kind", "pending")
        counts[kind] = counts.get(kind, 0) + 1
    atomic_json(
        OUTPUT / "summary.json",
        {"updated_at": now(), "counts": counts, "jobs": RECORDS},
    )


def append_manifest(value: dict[str, Any]) -> None:
    with (OUTPUT / "run_manifest.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + "\n")


def record(job: dict[str, Any], **fields: Any) -> None:
    with LOCK:
        key = job_key(job)
        RECORDS[key] = {**RECORDS.get(key, job), **fields, "updated_at": now()}
        append_manifest({"job": key, **fields, "timestamp": now()})
        update_summary()


def archive_attempt(path: Path, attempt: int) -> None:
    attempt_root = path / "_attempts" / f"attempt_{attempt:02d}"
    attempt_root.mkdir(parents=True, exist_ok=False)
    for child in list(path.iterdir()):
        if child.name == "_attempts":
            continue
        shutil.move(str(child), str(attempt_root / child.name))


def terminate_all(except_gpu: int | None = None) -> None:
    with LOCK:
        active = list(ACTIVE.items())
    for gpu, proc in active:
        if gpu == except_gpu or proc.poll() is not None:
            continue
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass


def run_one(job: dict[str, Any], gpu: int) -> dict[str, Any]:
    path = output_dir(job)
    path.mkdir(parents=True, exist_ok=True)
    existing = classify(path, 0, job)
    if existing["complete"]:
        skipped = {**existing, "kind": "skipped_existing_" + existing["kind"]}
        record(job, gpu=gpu, **skipped)
        print(f"[{now()}] SKIP gpu={gpu} {job_key(job)} {existing['kind']}", flush=True)
        return existing
    if any(path.iterdir()):
        archive_attempt(path, 0)

    argv = command(job, gpu)
    atomic_json(path / "orchestrator_command.json", {"argv": argv, "instruction": job["instruction"]})
    env = os.environ.copy()
    for name in (
        "VIRTUAL_ENV", "CONDA_PREFIX", "PYTHONPATH", "PYTHONHOME",
        "RPENT_RLINF_ROOT", "RLINF_REPO_PATH",
    ):
        env.pop(name, None)
    env.update(
        {
            "PATH": f"{V3 / '.venv-robotwin/bin'}:/usr/local/cuda-12.4/bin:/usr/local/bin:/usr/bin:/bin",
            "CUDA_HOME": "/usr/local/cuda-12.4",
            "HF_HUB_OFFLINE": "1",
            "ROBOTWIN_ASSETS_ROOT": str(ASSETS),
            "PYTHONUNBUFFERED": "1",
        }
    )

    final: dict[str, Any] = existing
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if STOP.is_set():
            return {"complete": False, "kind": "cancelled"}
        started = time.time()
        log_path = path / f"orchestrator_attempt_{attempt:02d}.log"
        record(job, gpu=gpu, attempt=attempt, kind="running", started_at=now(), log=str(log_path))
        print(f"[{now()}] START gpu={gpu} {job_key(job)} attempt={attempt}", flush=True)
        with log_path.open("w", encoding="utf-8") as log:
            proc = subprocess.Popen(
                argv,
                cwd=RPENT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            with LOCK:
                ACTIVE[gpu] = proc
            try:
                returncode = proc.wait(timeout=PROCESS_TIMEOUT_S)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
                returncode = 124
            finally:
                with LOCK:
                    ACTIVE.pop(gpu, None)
        final = classify(path, returncode, job)
        duration = round(time.time() - started, 2)
        record(job, gpu=gpu, attempt=attempt, duration_s=duration, **final)
        print(
            f"[{now()}] END gpu={gpu} {job_key(job)} attempt={attempt} "
            f"kind={final['kind']} duration={duration}s",
            flush=True,
        )
        if final["kind"] == "anti_cheat_violation":
            STOP.set()
            terminate_all(except_gpu=gpu)
            return final
        if final["complete"]:
            return final
        if attempt < MAX_ATTEMPTS:
            archive_attempt(path, attempt)
            atomic_json(path / "orchestrator_command.json", {"argv": argv, "instruction": job["instruction"]})
            time.sleep((10, 30)[min(attempt - 1, 1)])
    return final


def worker(gpu: int, jobs: list[dict[str, Any]]) -> None:
    for job in jobs:
        if STOP.is_set():
            break
        run_one(job, gpu)


def handle_signal(signum, _frame) -> None:
    print(f"[{now()}] received signal {signum}; stopping scheduler", flush=True)
    STOP.set()
    terminate_all()


def main() -> int:
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    preflight = source_preflight()
    jobs = load_jobs()
    prompt_files = [
        RPENT / "robots/robotwin/prompts/system.py",
        RPENT / "robots/robotwin/prompts/user.py",
        RPENT / "robots/robotwin/prompt_bundle.py",
    ]
    guide_files = [RPENT / "resources/robotwin/GUIDE_RPENT.md"]
    runtime_override_files = [
        RPENT / "robots/robotwin/__init__.py",
        RPENT / "robots/robotwin/env_server.py",
        RPENT / "rpent/cli/dashboard.py",
        RPENT / "rpent/cli/main.py",
        RPENT / "rpent/planner/base.py",
        RPENT / "rpent/planner/codex.py",
        RPENT / "scripts/run_robotwin_full_multiseed.py",
    ]
    memory_files = list((RPENT / "resources/robotwin/memory").glob("*"))
    recipe_files = list((RPENT / "resources/robotwin/recipe").glob("*"))
    create_or_validate_manifest(
        OUTPUT / "experiment_manifest.json",
        {
            "seed_table": str(SEED_TABLE),
            "seed_table_sha256": sha256(SEED_TABLE),
            "job_count": len(jobs),
            "parallel_workers": len(GPUS),
            "execution_policy": (
                "start all four workers immediately; one attempt per seed; "
                "record and skip ordinary infrastructure failures"
            ),
            "gpu_assignment": "one RPent process per physical GPU; Env and VLA share that GPU",
            "planner": {"type": "codex", "model": "gpt-5.5", "reasoning_effort": "high"},
            "assets": str(ASSETS),
            "model_view": str(MODEL),
            "source_snapshot": {
                "RPent": EXPECTED_HEADS["RPent"],
                "RLinf_checkout": EXPECTED_HEADS["RLinf"],
                "RLinf_installed_pin": "55cdc0e0ea578a066d42d94aaeb0298c24da0150",
                "RoboTwin": EXPECTED_HEADS["RoboTwin"],
            },
            "frozen_files": {
                "prompt": snapshot_files(prompt_files),
                "guide": snapshot_files(guide_files),
                "runtime_overrides": snapshot_files(runtime_override_files),
                "memory": snapshot_files(
                    [path for path in memory_files if path.is_file()]
                ),
                "recipe": snapshot_files(
                    [path for path in recipe_files if path.is_file()]
                ),
            },
            "recipe_batch": "frozen_global_v1",
            "recipe_metadata_removed": [
                "recipe_origin",
                "regime",
                "semantic_recipe.version",
            ],
            "anti_cheat": preflight,
            "initial_state_gate": {
                "eval_success": False,
                "take_action_cnt": 0,
                "policy_actions": 0,
                "native_actions": 0,
                "exact_seed_and_task_language": True,
            },
        },
    )
    (OUTPUT / "scheduler.pid").write_text(f"{os.getpid()}\n", encoding="utf-8")
    for job in jobs:
        RECORDS[job_key(job)] = {**job, "kind": "pending"}
    update_summary()
    queues = [jobs[index::len(GPUS)] for index in range(len(GPUS))]
    threads = [
        threading.Thread(target=worker, args=(gpu, queue), name=f"gpu-{gpu}")
        for gpu, queue in zip(GPUS, queues, strict=True)
    ]
    print(
        f"[{now()}] START GRID jobs={len(jobs)} workers={len(threads)}",
        flush=True,
    )
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    update_summary()
    print(f"[{now()}] GRID STOP complete={not STOP.is_set()}", flush=True)
    return 1 if STOP.is_set() else 0


if __name__ == "__main__":
    raise SystemExit(main())
