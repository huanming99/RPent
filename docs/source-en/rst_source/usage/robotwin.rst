RoboTwin
========

RPent uses RLinf's ``RoboTwinEnv`` as the sole owner of the RoboTwin native
task. The RPent process only talks to the environment through a thin RPC
bridge:

.. code-block:: text

   RPent Toolkit -> RPent EnvServer -> RLinf RoboTwinEnv
   -> RoboTwin VectorEnv/SubEnv -> native task

Installation
------------

Create a Python 3.11 environment and install the RoboTwin extra. The extra
combines the generic RLinf bridge, the packaged RoboTwin runtime, and the
pinned LingBot inference runtime:

.. code-block:: bash

   cd /path/to/RPent
   uv venv --python 3.11
   source .venv/bin/activate
   uv pip install -e ".[robotwin]"

During the pre-release transition, ``.[robotwin]`` resolves the RLinf bridge,
RoboTwin runtime, and LingBot runtime from public repositories at immutable Git
commits. Users still install them through the single command above; the pins
will be replaced by normal version requirements after the distributions are
released.

The distributions selected by ``.[robotwin]`` own the Python dependency
contract. ``rlinf-robotwin-runtime`` contains the supported RoboTwin Python
runtime, task modules, and small configuration/description resources, but not
the large simulator assets. ``rlinf-lingbotvla`` contains the LingBot inference
runtime but not a checkpoint. Installation never edits SAPIEN or MPLib files
in ``site-packages``. The runtime distribution pins SAPIEN 3.0.0b1 to match
the RoboTwin and LingBot inference contract.

The RoboTwin runtime wheel includes the pinned cuRobo v0.7.8 Python package,
content files, and CUDA extensions built against Torch 2.8. Users do not clone
or compile cuRobo during the RPent install.

Before installing, provide the OS-level prerequisites that Python packaging
cannot supply: a Linux compiler/build toolchain, CUDA/NVCC compatible with the
installed PyTorch build, and the GL/EGL/Vulkan libraries needed for headless
SAPIEN rendering. The old RLinf installer is not part of the RPent user flow.

Download the pinned RoboTwin assets into a relocatable directory:

.. code-block:: bash

   rlinf-robotwin-download-assets --output /path/to/robotwin-assets
   export ROBOTWIN_ASSETS_ROOT=/path/to/robotwin-assets

Download the pinned LingBot checkpoint and keep its path in the shell
environment, as with the model path used by the RoboCasa integration:

.. code-block:: bash

   hf download RLinf/LingBot-VLA-RoboTwin-EEF-ckpt1500 \
      --revision e727b46cd220b66981ea4d2fd9ba84adc189e2cc \
      --local-dir /path/to/LingBot-VLA-RoboTwin-EEF-ckpt1500
   export LINGBOT_MODEL_PATH=/path/to/LingBot-VLA-RoboTwin-EEF-ckpt1500

The model snapshot contains
``configs/robot_configs/robotwin_eef.yaml``. Use
``--lingbot-robot-config`` only to override that checkpoint-relative default.

Run
---

Launch one hybrid episode from the activated environment:

.. code-block:: bash

   rpent --env robotwin \
      --task-name beat_block_hammer \
      --task-config demo_randomized \
      --seed 100000 \
      --env-cuda-device 0 \
      --vla-cuda-device 2 \
      --planner codex \
      --model gpt-5.5

``--task-config`` defaults to ``demo_randomized`` and ``--seed`` defaults to
``100002``. A minimal invocation is therefore:

.. code-block:: bash

   rpent --env robotwin --task-name beat_block_hammer

RoboTwin runs use strict exact-seed acceptance. RLinf delegates reset to the
native ``VectorEnv`` lifecycle, then verifies the actual native episode seed.
If RoboTwin silently advances to another seed, the Agent episode remains
invalid and the run fails instead of using the replacement episode.

``--env-endpoint`` and ``--vla-endpoint`` attach to existing
services. RPent requires the EnvServer metadata to match the requested
task, task config, exact seed, API version, and action layouts. It also
requires the LingBot server's initial WebSocket metadata to identify the
RoboTwin EEF16 policy, observation layout, camera order, and chunk length.
Mismatched external services fail before episode reset or action execution.
``--cuda-device`` keeps the legacy same-GPU behavior. Do not combine it with
``--env-cuda-device`` or ``--vla-cuda-device``. The latter two options allow
the environment and VLA server to run on different GPUs.

Like the LIBERO and RoboCasa integrations, locally spawned Env and VLA servers
use ``sys.executable``. LingBot, cuRobo, and RLinf are imported from that Python
environment. RPent does not scan sibling directories or write hidden runtime
configuration. ``RPENT_RLINF_ROOT`` and ``RLINF_REPO_PATH`` are explicit
development-only overrides; normal runs should leave both unset. EnvServer logs
the resolved ``rlinf.__file__``, ``robotwin.__file__``, runtime distribution
versions, and asset snapshot identity at startup. It rejects modules outside
the active environment and installations that lack the typed RoboTwin Agent
API.

The LingBot VLA is Session-owned: its checkpoint is loaded once and the same
server is reused across TaskRuns. Each TaskRun owns a fresh RoboTwin EnvServer,
which is stopped before the shared VLA during teardown. Episode initialization
explicitly resets the shared model history before calling
``reset_exact(seed)`` on the new environment. The model client never resets the
environment implicitly, so the two lifecycle owners remain independent.

RoboTwin supports the generic RPent Dashboard with ``--dashboard``. The
LingBot VLA is shared for the Dashboard Session, while each ``/rpent-task
<task_name> <task_config> <seed>`` command starts a fresh exact-seed EnvServer.
The live monitor displays the head, left-wrist, and right-wrist camera frames.
Task replacement interrupts an active primitive at its next safe boundary;
an in-flight native action batch completes before the task-owned EnvServer is
stopped.

Path overrides
--------------

``ROBOTWIN_ASSETS_ROOT`` selects the downloaded simulator assets and
``LINGBOT_MODEL_PATH`` selects the checkpoint. Their equivalent CLI overrides
are ``--robotwin-assets-root`` and ``--lingbot-model-path``.
``--lingbot-robot-config`` overrides the config contained in the model
snapshot. RoboTwin, LingBot, and cuRobo source paths are not RPent runtime
arguments; they belong to the active Python environment installed by
``.[robotwin]``.

When RPent launches the LingBot server, it checks that the files required by
the configured model are present and enables a parent-death watcher.

RPent also syncs the ``robotwin/`` subtree from the public
``RLinf/RPent-memory`` dataset into ``resources/robotwin/``. The Planner can
read curated memory and successful task references from that directory, but
cannot write to it or access files outside it. Historical recipes are technique
priors only; all geometry must be recomputed from the current episode.
For offline runs, download that subtree first as described in
:doc:`../development/memory`; otherwise ``HF_HUB_OFFLINE=1`` leaves the Planner
without RoboTwin memory or reference JSON/JSONL files.

Environment API
---------------

RPent directly uses RLinf's agent-facing RoboTwin environment APIs. RLinf's
existing training ``chunk_step()`` path remains unchanged. These APIs include:
``execute_action_chunk()``, ``apply_qpos_updates()``,
``capture_observation()``, ``get_robot_state()``,
``get_episode_status()``, and ``plan_arm_path()``. Startup uses
``reset_exact()`` to verify the requested seed. Native
action layouts are ``qpos14`` and world-frame ``eef16`` with ``wxyz``
quaternions. Robot state distinguishes action-compatible ``qpos_target14``
from measured arm-only ``arm_qpos_real12``. Observation capture returns images,
geometry, calibration, robot state, and task language from one lock-protected
capture. Episode status includes native task state and agent validity. Action
results do not fabricate RL rewards, terminations, or truncations.

State-changing RPCs are single-attempt operations. Any exception, including a
server exception with a traceback, or any response without an explicit valid
``episode_status`` fail-closes the client. RPent classifies the run as a runtime
failure and stops all further requests that depend on that episode; it does not
replay or recover an action whose mutation cannot be ruled out. RLinf also
invalidates the episode when native EEF16 or qpos14 execution raises after a
partial action sequence, and preserves the requested and executed action counts
on the original exception.

All state-changing primitives return ``completed``, ``requested_steps``,
``executed_steps``, and one of ``completed``, ``native_success``,
``budget_exhausted``, or ``runtime_failure`` in ``stop_reason``. The retained
``success`` field reports compatibility-level primitive handling only; it is
not the RoboTwin task-success predicate. For planned motion, ``substeps=0``
executes the full path, ``substeps=1`` executes its final waypoint, and larger
values sample a path that includes both endpoints.

Task success requires both a valid Agent episode and fresh native
``TASK_ENV.eval_success``. Completion of a VLA chunk or primitive does not imply
task success. Accepted success also requires the Planner to call ``finish()``
exactly once.

The fixed LingBot model contract is defined by the frozen
``RoboTwinModelSpec`` in ``robots/robotwin/spec.py``. It contains only the
runtime paths and feature-layout values needed by the EEF policy.
