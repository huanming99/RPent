Memory Management
=================

RPent memory splits into two layers, mapped to two read-only reference corpora under
``resources/<env>/``. The goal is to record when and under what conditions the VLA
is worth calling, and how to adapt a validated trajectory to a new seed or perturbed
scene — instead of rediscovering everything from scratch each run.

Two layers
----------

* **Per-task references.** After a successful
  fixed-seed exploration run, the planner writes an audit JSON (``strategy_notes``,
  qualitative target zones, and related fields) and the runner exports a
  ``recipe_*.jsonl`` at the end (primitive command sequences only — ``move_to``,
  ``pi0_pick``, and the like — not file reads or perception tool calls). After
  review, curated entries land in directories such as ``results_*_pert/`` for
  deployment on the same task at other seeds. The planner follows the step order and
  strategy from these references but must re-perceive and recompute coordinates from
  the current scene — never replay historical xyz values.
* **Cross-task know-how.** Markdown notes under
  ``resources/<env>/memory/`` (indexed by ``MEMORY.md``) capture operating tips,
  parameter ranges, and common failure modes across tasks. The planner reads them
  together with per-task references to understand why a sequence works and how to
  recover after a failure.

On LIBERO, the prompt tells the planner to scan ``MEMORY.md`` and read the relevant
notes first, then check ``results_*_pert/`` for a seed-0 reference on the same task
(if present). The recipe supplies command order; adapting to a new scene relies on
the techniques, parameter ranges, and failure modes in the memory notes.

Hosting
-------

``resources/`` is not vendored in git. It is hosted on the Hugging Face dataset
``RLinf/RPent-memory`` (laid out per environment, e.g. ``libero/memory/`` and
``libero/results_*_pert/``). ``rpent.utils.resources.ensure_resources`` syncs the
env's subtree from the dataset on each run (incremental: only changed files are
downloaded), so the local copy stays up to date. The dataset is public, so a
fresh clone downloads it without a token. Set ``HF_HUB_OFFLINE=1`` to skip the
sync. The run continues without memory or task references when no local copy is
available, and RPent logs a warning. To retain the references offline, download
the environment's subtree first. For example, prepare RoboTwin resources with:

.. code-block:: bash

   hf download RLinf/RPent-memory \
     --repo-type dataset \
     --include "robotwin/**" \
     --local-dir /path/to/RPent/resources

Do not set ``HF_HUB_OFFLINE=1`` merely because model checkpoints are already
local: it disables the memory sync as well. Memory is optional, so the run also
continues if an environment has no published memory or an online sync fails.

Updating the memory
-------------------

After a successful exploration run, the audit and recipe land in that run's
``output_dir`` first. Entering ``results_*_pert/`` or ``memory/`` requires
review. Publishing is gated to maintainers with write access to the ``RLinf``
organisation; the repository ships no self-serve upload path. To contribute a
better reference trajectory or memory note, open an issue with the proposed
content and a maintainer will review and publish it.
