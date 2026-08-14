RoboTwin
========

`RoboTwin <https://robotwin-platform.github.io/>`_ is a simulation benchmark
for dual-arm robot manipulation, with a range of tabletop tasks and randomized
scenes. RPent runs RoboTwin through RLinf and uses LingBot-VLA to generate robot
actions.

Installation
------------

Use Python 3.11, which is the version covered by the full runtime validation.
Create an environment and install the RoboTwin dependency set:

.. code-block:: bash

   cd /path/to/RPent
   uv venv --python 3.11
   source .venv/bin/activate
   uv pip install -e ".[robotwin]"

You do not need to run the RLinf installer or clone RoboTwin separately.

.. note::

   ``.[robotwin]`` uses SAPIEN 3.0.0b1. Other versions can change simulator
   observations and reduce model performance.

Download assets
---------------

Download the supported RoboTwin asset snapshot and set its location:

.. code-block:: bash

   robotwin-download-assets --output /path/to/robotwin-assets
   export ROBOTWIN_ASSETS_ROOT=/path/to/robotwin-assets

The downloader validates existing files and skips the download when the target
directory already contains a complete RoboTwin asset set.

Download the model
------------------

Download the LingBot checkpoint and set its location:

.. code-block:: bash

   hf download RLinf/LingBot-VLA-RoboTwin-EEF-ckpt1500 \
      --revision e727b46cd220b66981ea4d2fd9ba84adc189e2cc \
      --local-dir /path/to/LingBot-VLA-RoboTwin-EEF-ckpt1500
   export LINGBOT_MODEL_PATH=/path/to/LingBot-VLA-RoboTwin-EEF-ckpt1500

The checkpoint includes the default RoboTwin robot configuration.

Run a task
----------

Run one episode from the activated environment:

.. code-block:: bash

   rpent --env robotwin \
      --task-name beat_block_hammer \
      --task-config demo_randomized \
      --seed 100000 \
      --planner codex \
      --model gpt-5.5

Change ``--task-name`` or ``--seed`` to run a different task or episode. See
``rpent --env robotwin --help`` for the complete option list.

View the result
---------------

The terminal shows server startup, planner output, and tool calls. By default,
the run is saved under
``logs/<timestamp>_robotwin_<task-name>_s<seed>/``. Start with these files when
checking a run:

- ``run.log`` contains the RPent process log.
- ``robotwin_env_server.log`` and ``lingbot_vla_server.log`` contain simulator
  and model startup errors.
- ``transcript_*.json`` contains the planner conversation and final response.
- ``robotwin_episode_result.json`` contains the final RoboTwin result.

Add ``--dashboard`` to watch the planner and the head and wrist camera views in
a browser. The command prints the Dashboard URL after startup.

Common options
--------------

- ``--robotwin-assets-root`` overrides ``ROBOTWIN_ASSETS_ROOT``.
- ``--vla-model-path`` overrides ``LINGBOT_MODEL_PATH``.
- ``--cuda-device`` runs the simulator and VLA on the same GPU.
- ``--env-cuda-device`` and ``--vla-cuda-device`` place the simulator and VLA
  on different GPUs. Do not combine these options with ``--cuda-device``.

For planner setup, external service endpoints, and offline resources, see
:doc:`configure_planner`, :doc:`advanced_deployment`, and
:doc:`../development/memory`.

Before each run, RPent automatically syncs optional RoboTwin memory and task
references from the public ``RLinf/RPent-memory`` dataset. These references can
improve planning by providing previously verified techniques; the run still
starts if they are unavailable.
