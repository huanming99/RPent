RoboTwin
========

RPent runs RoboTwin through RLinf's ``RoboTwinEnv`` and uses LingBot-VLA to
generate end-effector actions. Install the Python packages first, then download
the simulator assets and model checkpoint separately.

Installation
------------

Use Python 3.11, which is the version covered by the full runtime validation.
Create an environment and install the RoboTwin dependency set:

.. code-block:: bash

   cd /path/to/RPent
   uv venv --python 3.11
   source .venv/bin/activate
   uv pip install -e ".[robotwin]"

This command installs RPent's RLinf integration, the RoboTwin Python runtime,
and the LingBot inference package. You do not need to run the RLinf installer
or clone RoboTwin separately.

The large RoboTwin assets and LingBot checkpoint are not included. During the
current pre-release period, the Python packages are installed from immutable
Git revisions; they will use released version requirements after publication.

RoboTwin requires Linux with an NVIDIA GPU, a working compiler toolchain,
CUDA/NVCC compatible with Torch 2.8, and the GL/EGL/Vulkan libraries needed by
SAPIEN. The installation builds the bundled cuRobo v0.7.8 CUDA extensions on
the local machine. Users do not need to download or configure cuRobo
separately, but NVCC and the compiler toolchain must be available.

The supported runtime pins SAPIEN 3.0.0b1. Keep this version when updating or
recreating the environment; a different SAPIEN version can change simulator
observations and model behavior.

Download assets
---------------

Download the supported RoboTwin asset snapshot and set its location:

.. code-block:: bash

   robotwin-download-assets --output /path/to/robotwin-assets
   export ROBOTWIN_ASSETS_ROOT=/path/to/robotwin-assets

The downloader validates existing files and skips the download when the
requested snapshot is already complete.

Download the model
------------------

Download the LingBot checkpoint and set its location:

.. code-block:: bash

   hf download RLinf/LingBot-VLA-RoboTwin-EEF-ckpt1500 \
      --revision e727b46cd220b66981ea4d2fd9ba84adc189e2cc \
      --local-dir /path/to/LingBot-VLA-RoboTwin-EEF-ckpt1500
   export LINGBOT_MODEL_PATH=/path/to/LingBot-VLA-RoboTwin-EEF-ckpt1500

The checkpoint contains the default
``configs/robot_configs/robotwin_eef.yaml``. Use
``--lingbot-robot-config`` only when a different robot configuration is
required.

Run a task
----------

Run one episode from the activated environment:

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
``100002``. The shortest equivalent command is:

.. code-block:: bash

   rpent --env robotwin --task-name beat_block_hammer

Common options
--------------

- ``--robotwin-assets-root`` overrides ``ROBOTWIN_ASSETS_ROOT``.
- ``--vla-model-path`` overrides ``LINGBOT_MODEL_PATH``.
- ``--env-cuda-device`` and ``--vla-cuda-device`` place the simulator and VLA
  on different GPUs. Use ``--cuda-device`` instead when both should use the
  same GPU; do not combine these forms.
- ``--env-endpoint`` and ``--vla-endpoint`` connect to services that are
  already running. RPent checks that they match the requested task, seed, and
  model interface before executing actions.
- ``--dashboard`` starts the RPent Dashboard. Submit tasks with
  ``/rpent-task <task_name> <task_config> <seed>``; the Dashboard displays the
  head and wrist camera views while the task runs.

Do not use ``--env-endpoint`` with ``--dashboard`` because each Dashboard task
starts its own environment service.

Seeds and results
-----------------

RPent requires RoboTwin to reset to the exact requested seed. If the simulator
selects a different episode, the run stops instead of continuing with that
episode.

Action tools report whether all requested steps were completed and why they
stopped. Completion of an action or VLA chunk does not by itself mean that the
task succeeded.

A successful RPent result requires RoboTwin's own success check to pass and the
Planner to call ``finish()`` exactly once. When an action may have executed only
partially before an error, RPent stops the episode rather than retrying it.

Memory and offline runs
-----------------------

RPent downloads optional RoboTwin task references from the public
``RLinf/RPent-memory`` dataset. These references contain prior techniques, not
coordinates to replay; the Planner must calculate geometry again from the
current observation.

Set ``HF_HUB_OFFLINE=1`` to skip this synchronization. The run still starts
when no local references are available, but RPent logs a warning and continues
without them. To retain the references offline, download them before the run as
described in :doc:`../development/memory`.
