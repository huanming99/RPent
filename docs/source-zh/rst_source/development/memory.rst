参考资料管理
============

RPent 的参考资料分为两类，都位于 ``resources/<env>/`` 且只读。
这些资料记录适合调用 VLA 的场景和条件，以及如何将已验证的操作流程
用于新 seed 或有扰动的场景，避免每次都从头尝试。

两层结构
--------

* **任务级参考。** 固定 seed 的探索成功后，本次运行会保存运行记录
  JSON（包含 ``strategy_notes``、目标区域等），并在结束时导出
  ``recipe_*.jsonl``。后者只记录 ``move_to``、``pi0_pick`` 等操作命令，
  不包含读取文件或调用感知工具的过程。经过筛选后，这些文件会放入
  ``results_*_pert/`` 等参考目录，供同一任务在其他 seed 下运行时参考。
  规划器可以参考其中的步骤和策略，但必须根据当前画面重新计算坐标，
  不能直接复用历史坐标。
* **全局经验。** ``resources/<env>/memory/`` 下的 Markdown 笔记
  （``MEMORY.md`` 索引及子笔记）记录跨任务的操作要点、参数范围与常见失败模式。
  规划器会将它们与任务级参考一起阅读，用于理解步骤安排和失败后如何
  调整。

在 LIBERO 中，规划器会先读取 ``MEMORY.md`` 索引及相关笔记，再查看
``results_*_pert/`` 中同一任务的 seed-0 参考（如果存在）。``recipe_*.jsonl``
只提供命令顺序；适配新场景时，还需要结合经验笔记中的操作技巧、
参数范围和常见失败原因。

托管方式
--------

``resources/`` 不随 git 仓库分发，而是托管在 Hugging Face 数据集 ``RLinf/RPent-memory``
上（按环境分层，例如 ``libero/memory/`` 与 ``libero/results_*_pert/``）。``rpent.utils.resources.ensure_resources``
会在每次运行时从数据集增量同步该环境的子目录（只下载有变化的文件），使本地副本保持最新。
数据集是公开的，无需 token 即可下载。设置 ``HF_HUB_OFFLINE=1`` 可以跳过同步；
即使本地没有对应内容，运行也会继续，但 RPent 会给出警告，并且不会提供任务参考。
若希望离线时继续使用这些内容，请先下载对应环境的子目录。例如：

.. code-block:: bash

   hf download RLinf/RPent-memory \
     --repo-type dataset \
     --include "robotwin/**" \
     --local-dir /path/to/RPent/resources

不要仅仅因为模型文件已在本地就设置 ``HF_HUB_OFFLINE=1``，因为它也会关闭任务参考
的同步。任务参考是可选内容；如果数据集尚未提供或在线同步失败，运行同样会继续。

更新参考资料
--------------

探索成功后，运行记录与 ``recipe_*.jsonl`` 会先保存到当次 ``output_dir``；
进入 ``results_*_pert/``
或 ``memory/`` 参考库须经过筛选。发布由维护者统一把关：只有拥有 ``RLinf`` 组织写权限的人能更新
Hugging Face 数据集；仓库本身不提供自助上传入口。如果你有效果更好的参考轨迹或
经验笔记，可以创建 issue 并附上内容，由维护者审阅后发布。
