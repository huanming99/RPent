RoboTwin
========

RPent 复用 RLinf 的 ``RoboTwinEnv``，并由它唯一持有 RoboTwin native task。
RPent 进程只通过薄 RPC bridge 访问环境：

.. code-block:: text

   RPent Toolkit -> RPent EnvServer -> RLinf RoboTwinEnv
   -> RoboTwin VectorEnv/SubEnv -> native task

安装
----

创建 Python 3.11 环境并安装 RoboTwin extra。这个 extra 会组合通用 RLinf
bridge、package 化的 RoboTwin runtime 和固定的 LingBot inference runtime：

.. code-block:: bash

   cd /path/to/RPent
   uv venv --python 3.11
   source .venv/bin/activate
   uv pip install -e ".[robotwin]"

在正式发布前的过渡阶段，``.[robotwin]`` 会从公开仓库的不可变 Git commit
解析 RLinf bridge、RoboTwin runtime 和 LingBot runtime。用户仍只需要执行上面
这一条安装命令；对应 distributions 发布后会切换回普通版本号依赖。

``.[robotwin]`` 选择的 distributions 负责 Python dependency contract。
``rlinf-robotwin-runtime`` 包含受支持的 RoboTwin Python runtime、task modules
以及小型 config/description 资源，但不包含大型 simulator assets；
``rlinf-lingbotvla`` 包含 LingBot inference runtime，但不包含 checkpoint。安装
过程不会修改 ``site-packages`` 中的 SAPIEN/MPLib 文件。runtime distribution
固定使用 ``SAPIEN 3.0.0b1``，与 RoboTwin 和 LingBot 推理环境的版本契约保持一致。

RoboTwin runtime wheel 包含固定 cuRobo v0.7.8 的 Python package、content files，
以及基于 Torch 2.8 构建的 CUDA extensions；RPent 用户安装时不需要再单独 clone
或编译 cuRobo。

安装前仍需准备 Python packaging 无法提供的 OS prerequisites：Linux 编译工具链、
与 PyTorch 匹配的 CUDA/NVCC，以及 SAPIEN headless rendering 所需的
GL/EGL/Vulkan 库。旧的 RLinf installer 不再属于 RPent 用户安装流程。

下载固定版本的 RoboTwin assets 到可迁移目录：

.. code-block:: bash

   rlinf-robotwin-download-assets --output /path/to/robotwin-assets
   export ROBOTWIN_ASSETS_ROOT=/path/to/robotwin-assets

下载固定 LingBot checkpoint，并像 RoboCasa 的模型路径一样通过环境变量提供：

.. code-block:: bash

   hf download RLinf/LingBot-VLA-RoboTwin-EEF-ckpt1500 \
      --revision e727b46cd220b66981ea4d2fd9ba84adc189e2cc \
      --local-dir /path/to/LingBot-VLA-RoboTwin-EEF-ckpt1500
   export LINGBOT_MODEL_PATH=/path/to/LingBot-VLA-RoboTwin-EEF-ckpt1500

模型 snapshot 包含 ``configs/robot_configs/robotwin_eef.yaml``；只有需要覆盖
checkpoint 内默认配置时才使用 ``--lingbot-robot-config``。

运行
----

激活环境后启动单环境 hybrid episode：

.. code-block:: bash

   rpent --env robotwin \
      --task-name beat_block_hammer \
      --task-config demo_randomized \
      --seed 100000 \
      --env-cuda-device 0 \
      --vla-cuda-device 2 \
      --planner codex \
      --model gpt-5.5

``--task-config`` 默认是 ``demo_randomized``，``--seed`` 默认是
``100002``，因此最简命令是：

.. code-block:: bash

   rpent --env robotwin --task-name beat_block_hammer

RoboTwin 使用 strict exact-seed 验收。RLinf 复用 native
``VectorEnv`` reset lifecycle，再读取实际 episode seed；如果 RoboTwin
内部自动换成其他 seed，Agent episode 会保持 invalid 并 fail-fast，不会继续
使用替换后的 episode。

``--env-endpoint`` 和 ``--vla-endpoint`` 可以连接已有服务。RPent 要求
EnvServer metadata 与请求的 task、task config、exact seed、API 版本和动作布局
一致；同时要求 LingBot server 的 WebSocket 首帧 metadata 标明 RoboTwin EEF16
policy、观测布局、camera 顺序和 chunk 长度。外部服务不匹配时，会在 episode reset
或动作执行前 fail-fast。
``--cuda-device`` 保留 Env/VLA 共用一张 GPU 的兼容行为，不能与
``--env-cuda-device`` 或 ``--vla-cuda-device`` 同时使用。后两个参数可以
让环境和 VLA server 使用不同 GPU。

与 LIBERO、RoboCasa 一致，本地启动的 Env/VLA subprocess 都使用
``sys.executable``。LingBot、cuRobo 和 RLinf 从当前 Python 环境导入；RPent
不扫描 sibling 目录，也不写入隐藏 runtime config。``RPENT_RLINF_ROOT`` 和
``RLINF_REPO_PATH`` 只用于显式开发 override，普通运行应保持未设置。EnvServer
启动时会记录实际的 ``rlinf.__file__``、``robotwin.__file__``、runtime
distribution versions 和 asset snapshot identity；它会拒绝从当前环境外加载的
模块，以及缺少 typed RoboTwin Agent API 的安装。

LingBot VLA 由 Session 持有：checkpoint 只加载一次，并在多个 TaskRun 之间复用
同一个 server。每个 TaskRun 都持有一个全新的 RoboTwin EnvServer；teardown 时
先停止 task Env，再停止 shared VLA。每个 episode 初始化时，先显式清理 shared
model history，再对新环境调用 ``reset_exact(seed)``。model client 不会隐式 reset
环境，因此两个 lifecycle owner 保持解耦。

RoboTwin 支持通过 ``--dashboard`` 使用 RPent 通用 Dashboard。LingBot VLA 在整个
Dashboard Session 内共享，每条 ``/rpent-task <task_name> <task_config> <seed>``
命令都会启动一个新的 exact-seed EnvServer。实时界面展示 head、left-wrist 和
right-wrist 三路相机画面。切换任务时，当前 primitive 会在下一个安全边界中断；
已经进入 native runtime 的单批动作会先执行完，再停止该 TaskRun 持有的 EnvServer。

路径覆盖
--------

``ROBOTWIN_ASSETS_ROOT`` 指向下载后的 simulator assets，
``LINGBOT_MODEL_PATH`` 指向 checkpoint；对应的 CLI 覆盖参数是
``--robotwin-assets-root`` 和 ``--lingbot-model-path``。
``--lingbot-robot-config`` 用于覆盖模型 snapshot 中的配置。RoboTwin、LingBot
和 cuRobo 源码路径都不是 RPent runtime 参数，它们属于 ``.[robotwin]`` 安装的
当前 Python 环境。

RPent 自己启动 LingBot server 时，只检查当前模型运行所需的文件是否存在，
并启用 parent-death watcher。

RPent 还会把公开 ``RLinf/RPent-memory`` 数据集中的 ``robotwin/`` 子目录
增量同步到 ``resources/robotwin/``。Planner 只能读取其中经过筛选的 memory
和成功任务参考，不能写入该目录或访问目录外文件。历史 recipe 只作为策略参考，
所有几何信息都必须从当前 episode 重新计算。
离线运行前须按 :doc:`../development/memory` 先下载该子目录；否则设置
``HF_HUB_OFFLINE=1`` 后，Planner 将无法读取 RoboTwin memory 以及参考 JSON/JSONL。

环境 API
--------

RPent 直接使用 RLinf 提供的 RoboTwin Agent 环境 API。RLinf 原有训练
``chunk_step()`` 保持不变；这些 API 包括：
``execute_action_chunk()``、``apply_qpos_updates()``、
``capture_observation()``、``get_robot_state()``、
``get_episode_status()`` 和 ``plan_arm_path()``。启动阶段使用
``reset_exact()`` 校验请求的 seed。
动作布局为 ``qpos14`` 和世界坐标系 ``eef16``，四元数顺序为 ``wxyz``。
机器人状态明确区分与动作兼容的 ``qpos_target14`` 和只包含实际机械臂关节的
``arm_qpos_real12``。观测采集在持有原生环境锁期间返回图像、几何信息、标定
信息、机器人状态和任务指令。episode status 同时包含原生任务状态和 Agent
有效性。动作结果不自行构造 RL 奖励、termination 或 truncation。

修改环境状态的 RPC 只尝试一次。任何异常（包括带 server traceback 的异常），
或任何未携带明确 valid ``episode_status`` 的响应，都会让 client fail-close。
RPent 会将该 run 分类为 runtime failure，并停止所有依赖该 episode 的后续请求；
不会重放或恢复无法排除 partial mutation 的动作。当 native EEF16 或 qpos14 在
action sequence 中途抛错时，RLinf 也会将 episode 标记为 invalid，并在原始异常上
保留 requested/executed action count。

所有修改状态的 primitive 都返回 ``completed``、``requested_steps``、
``executed_steps``，以及 ``completed``、``native_success``、
``budget_exhausted``、``runtime_failure`` 之一的 ``stop_reason``。为兼容已有调用方
保留的 ``success`` 只表示 primitive 层处理结果，不是 RoboTwin task-success
predicate。对于规划路径，``substeps=0`` 执行完整路径，``substeps=1`` 执行终点，
更大的取值会均匀采样且包含路径起点和终点。

任务成功要求 Agent episode valid 且 native ``TASK_ENV.eval_success`` 为真。
VLA chunk 或 primitive 执行完成不代表任务成功；accepted success 还要求
Planner 真实且仅调用一次 ``finish()``。

固定 LingBot 配置由 ``robots/robotwin/spec.py`` 中 frozen
``RoboTwinModelSpec`` 统一定义，只包含 EEF policy 所需的运行路径和
feature layout。
