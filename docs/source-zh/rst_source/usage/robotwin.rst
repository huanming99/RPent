RoboTwin
========

RPent 通过 RLinf 的 ``RoboTwinEnv`` 运行 RoboTwin，并使用 LingBot-VLA 生成
末端执行器动作。请先安装 Python 依赖，再分别下载仿真资源和模型文件。

安装
----

请使用已完成完整验证的 Python 3.11。创建虚拟环境并安装 RoboTwin
所需依赖：

.. code-block:: bash

   cd /path/to/RPent
   uv venv --python 3.11
   source .venv/bin/activate
   uv pip install -e ".[robotwin]"

这条命令会安装 RPent 的 RLinf 集成、RoboTwin Python 运行环境和 LingBot 推理组件。
用户不需要运行 RLinf 安装器，也不需要单独克隆 RoboTwin。

大型 RoboTwin 仿真资源和 LingBot 模型不包含在 Python 包中，需要另外下载。正式
版本发布前，这些 Python 包暂时固定到相应 Git 仓库的特定提交；发布后将改用版本号依赖。

RoboTwin 需要 Linux、NVIDIA GPU、可用的编译工具链、与 Torch 2.8 匹配的
CUDA/NVCC，以及 SAPIEN 所需的 GL/EGL/Vulkan 库。安装过程会在本机编译随包
提供的 cuRobo v0.7.8 CUDA 扩展。用户无需单独下载或配置 cuRobo，但必须提前
准备好 NVCC 和编译工具链。

当前支持的运行环境固定使用 SAPIEN 3.0.0b1。更新或重建环境时请保留这一版本；
更换 SAPIEN 版本可能改变仿真观测，进而影响模型表现。

下载仿真资源
------------

下载 RPent 支持的 RoboTwin 仿真资源，并设置资源目录：

.. code-block:: bash

   robotwin-download-assets --output /path/to/robotwin-assets
   export ROBOTWIN_ASSETS_ROOT=/path/to/robotwin-assets

下载工具会先校验已有文件；如果指定版本的资源已经完整，则不会重复下载。

下载模型
--------

下载 LingBot 模型并设置模型目录：

.. code-block:: bash

   hf download RLinf/LingBot-VLA-RoboTwin-EEF-ckpt1500 \
      --revision e727b46cd220b66981ea4d2fd9ba84adc189e2cc \
      --local-dir /path/to/LingBot-VLA-RoboTwin-EEF-ckpt1500
   export LINGBOT_MODEL_PATH=/path/to/LingBot-VLA-RoboTwin-EEF-ckpt1500

模型目录中已经包含默认配置
``configs/robot_configs/robotwin_eef.yaml``。只有需要使用其他机器人配置时，
才需要传入 ``--lingbot-robot-config``。

运行任务
--------

激活虚拟环境后运行一个任务：

.. code-block:: bash

   rpent --env robotwin \
      --task-name beat_block_hammer \
      --task-config demo_randomized \
      --seed 100000 \
      --env-cuda-device 0 \
      --vla-cuda-device 2 \
      --planner codex \
      --model gpt-5.5

``--task-config`` 默认使用 ``demo_randomized``，``--seed`` 默认使用
``100002``，因此最简命令是：

.. code-block:: bash

   rpent --env robotwin --task-name beat_block_hammer

常用参数
--------

- ``--robotwin-assets-root``：覆盖 ``ROBOTWIN_ASSETS_ROOT`` 指定的资源目录。
- ``--vla-model-path``：覆盖 ``LINGBOT_MODEL_PATH`` 指定的模型目录。
- ``--env-cuda-device`` 和 ``--vla-cuda-device``：让仿真环境和 VLA 使用不同
  GPU。如果二者使用同一张 GPU，可以改用 ``--cuda-device``；两种写法不能混用。
- ``--env-endpoint`` 和 ``--vla-endpoint``：连接已经启动的环境或 VLA 服务。
  执行动作前，RPent 会检查服务是否与当前任务、种子和模型接口匹配。
- ``--dashboard``：启动 RPent Dashboard。通过
  ``/rpent-task <task_name> <task_config> <seed>`` 提交任务；运行期间可以查看头部
  和腕部相机画面。

``--dashboard`` 不能与 ``--env-endpoint`` 同时使用，因为 Dashboard 会为每个任务
启动独立的环境服务。

种子与成功判定
--------------

RPent 要求 RoboTwin 必须重置到用户指定的种子。如果仿真器实际选择了其他回合，
RPent 会终止本次运行，而不会继续使用被替换的回合。

动作工具会返回是否完成全部请求步骤，以及停止原因。单次动作或 VLA
动作序列执行完成，并不代表任务已经成功。

RPent 最终判定任务成功需要同时满足两个条件：RoboTwin 自身的成功判定通过，
并且规划器恰好调用一次 ``finish()``。如果动作报错前可能已经执行了一部分，RPent 会终止当前
回合，不会自动重试。

任务参考与离线运行
------------------

RPent 会从公开数据集 ``RLinf/RPent-memory`` 下载可选的 RoboTwin 任务参考。这些
内容只提供操作思路，不能直接复用其中的历史坐标；规划器仍需根据当前观测重新计算位置。

设置 ``HF_HUB_OFFLINE=1`` 可以跳过同步。即使本地没有任务参考，运行仍会继续，
但 RPent 会给出警告并在没有参考内容的情况下执行。若希望离线时继续使用这些参考，
请先按 :doc:`../development/memory` 中的说明下载。
