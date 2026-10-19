RoboDojo 跨机器验证交接
=======================

更新时间：2026-10-19。读者是继续本分支工作的开发者或新 Codex 会话。
本文是迁移记录，不是完整 benchmark 通过报告；代码优先于历史讨论，
如发现本文与实现不符，应指出差异，不能为迎合记录而悄悄改动语义。

此分支保存解析式 Primitive 迁移和 VPP2 接入，基于 RPent
``58844d554e8a62797d7f4a1cd52e30eaf82d91a7``，不是 PR #219，
尚未合并后续 upstream/main。提交用于继续验证，不代表可发布或刷榜验收完成。

.. contents:: 目录
   :local:
   :depth: 2

新会话先看这里
--------------

* Fork：``https://github.com/huanming99/RPent``。
* 分支：``feat/robodojo-primitives-vpp2``，不要直接切回 main 丢失本分支功能。
* 功能快照提交：``1ff1ceea42bd7675d1b6a2579ecfdca17a09dda9``。
  后续交接文档提交叠加在其上；这不是一个独立的旧 PR219 环境。
* 本地代码、测试和双语使用指南已提交。未提交的 ``AGENTS.md`` 修改只是
  旧机器路径和共享资源约定，不适用于新机器，故没有随分支上传。
* 用户希望在另一台有 RTX 3090 的机器继续验证。卡的数量、驱动、可用显存、
  是否还能连接旧 A800 模型服务器，均需在新会话核实，不能从显卡型号推断。
* 本轮授权是提交和迁移交接，不是自动下载数十 GB 权重、修改驱动、启动训练、
  大规模评测或提交上游 PR 的授权。操作共享 GPU 前重新协调；只管理自己的进程。
* 不修改旧 release 项目、其他项目环境或共享 IsaacLab／资产。重用资产时先确认
  版本和完整性；路径配置应在目标机器自己的副本中生成。

建议阅读顺序：根目录 ``AGENTS.md`` 和 ``CONTRIBUTING.md`` → 本文件 →
相关任务技能 → ``tests/README.md`` → 双语 RoboDojo 使用指南 → 下列实现文件。
若新机器另有工作区指引，应先遵守当地约定；不要照搬旧机器的绝对路径。

用户已确认的目标和边界
----------------------

目标是 RPent 的 Agent harness：Agent 观察、分解任务、选择解析式工具或学习式
策略、检查反馈，再决定下一步。不是直接复刻 VPP2 官方整套评测驱动，
也不是让 Agent 一次写好程序后完全退出控制循环。

已明确的架构约束：

* RoboTwin 和 RoboDojo 是平级的 ``robots/<robot>/`` 集成。
  复用已有 RPent 公共注册、RPC、运行时、状态和记忆接口，
  不让 RoboDojo 导入 RoboTwin 机器人专属实现。
* 参考 RoboTwin 的文件组织、函数接口及可观察行为。
  尚未抽成公共模块的能力在 RoboDojo 目录内独立实现；
  本任务不抽取新的跨机器人公共框架，不做仓库级重构。
* 若发现 RoboTwin 的行为有缺陷或不适用于 Isaac，先说明证据和后果，
  不为追求表面一致复制问题，不悄悄改变已确认的接口。
* Primitive 是由 Toolkit 注册给 Agent 的工具。
  策略、控制器和相机实现位于注册层下面，模型不直接操作服务进程或绕过 RPC。
* 保留看图、SAM3 分割和反投影。使用 SAM3 是有意保留的能力，
  不要求为了与 RoboTwin 一致而删除；提示词参考了 RoboTwin 与 LIBERO。
* 只完整移除了旧 ``move_to``、``set_gripper`` 的工具实现，随后以相同名称
  注册新接口。``pi0_pick`` 保留源码但不注册；``stabilize``、``place_in_bin``
  保留为禁用的旧入口，不能因同名新动作出现就重新启用。
* 不额外建设完整场景障碍物重建系统，不接入其他学习模型，不训练 VPP2。
  简洁代码、清晰职责和针对行为的测试优先，不堆叠无实际消费者的兼容逻辑。

当前分层及文件索引
------------------

.. code-block:: text

   RPent Planner / Session / Memory
                  |
   robot_spec.py -> RoboDojoToolkit (注册工具、探索限制、记录状态)
                  |
          +-------+-------------------------+
          |                                 |
   tools.py 感知工具                 primitives.py 动作工具
   读取 EnvState                      |                  |
   segment -> SAM3 RPC           解析式动作          vpp2_act
          |                           |                  |
          |                   RoboDojoEnvClient <--- VPP2Client
          |                     有界 RGB 历史         | 请求历史/状态/子任务
          |                           |              | 返回 EE16
          |                      Env RPC        VPP2Facade RPC
          |                           |              |
          +--------------------> env_facade      官方 VPP2 模型
                                      |
                               RoboDojoAgentEnv
                                      |
                          RLinf / RoboDojo / IsaacLab
                         解析式路径规划使用原生 cuRobo

文件职责：

* ``robot_spec.py``：RobotSpec、参数解析、服务启动／接入、工具包工厂、原生结果。
* ``toolkit.py``：注册白名单、观察记录、探索 reset／finish 限制、成功动作配方导出。
* ``primitives.py``：新位姿／夹爪工具、VPP2 分块执行、预算／取消／执行反馈。
* ``tools.py``：保存 RGB-D／世界点图、看图、分割、反投影、多点／区域查询；
  文件中仍有未注册的旧策略代码，不代表这些旧工具正在对 Agent 开放。
* ``agent_support.py``：读取实际末端状态和保持中的控制目标，调用原生位姿规划。
* ``env_client.py``：Env RPC 及按实际动作反馈更新的 VPP2 历史；不是模型服务缓存。
* ``env_facade.py``、``env_server.py``、``rlinf_env.py``：服务边界、参数、
  原生动作类型转换、单环境执行、真实观测及执行计数。
* ``vpp2_client.py``：VLA RPC、检查完整预测为有限 ``(32,16)``、选前 24 步。
* ``vpp2_server.py``：定位资源，复用官方预处理／归一化／模型推理，返回动作。
* ``prompt_bundle.py``、``prompts/``：一般观察行动循环、子任务语言和探索规范。
* ``flash/plan.py``：仅保留旧计划的数据 schema 兼容；不代表 Flash 已可运行。

现有 RPent ``RobotSpec``、``Toolkit``、``EnvState``、``MemoryManager``、
``BaseEnvClient``、``BaseVLAClient``、``BaseVLAFacade``、运行时和 RPC 被复用。
这次未修改 ``rpent/`` 的生产实现；共有测试辅助代码有小幅扩展，
用于本地脚本规划器检查工具调用及前后图像。

已对齐的工具语义
----------------

观察与定位
~~~~~~~~~~

* ``view_env_state(step=-1)`` 读取已记录的三路 RGB 和机器人状态。
  它不是“每调用一次就执行一步”；需要新观测时显式 ``render``。
* ``render`` 通过工具完成后的记录流程刷新 RGB-D、标定和机器人状态，
  不发送机器人动作。它可以新增状态记录，但不会推进 VPP2 动作时间轴。
* ``sample_world_xyz(view, pixels, step=None, neighborhood=1)``：
  对同一已保存画面的多个 ``[row,col]`` 取世界点，默认半径 1 邻域取有效点中位数；
  ``neighborhood=0`` 是单像素。最多 256 个像素，半径范围 0～32。
* ``query_world_map(view, bbox, step=None, max_points=256)``：
  查询半开区域 ``[row_start,col_start,row_end,col_end]`` 内可见表面点，
  确定性采样，最多允许 4096 个返回点，并提供区域统计。
  它不是物体完整三维模型，也不能看到遮挡后的点。
* 上述 ``view`` 为 ``head``、``left_wrist``、``right_wrist``；
  ``segment``／``back_project`` 的 ``camera`` 则为
  ``cam_head``、``cam_left_wrist``、``cam_right_wrist``，不要混用。
* ``segment(text_prompt, camera, min_score=0.2, step=None)`` 使用同帧 SAM3。
  返回 mask 覆盖图、分数、框、质心和位于前景内的 ``point_rc``；
  凹形 mask 的质心可能在背景，故定位应优先使用 ``point_rc``。
  未识别到物体时允许 Agent 重新描述或在图上选像素，不会伪造世界坐标。
* ``back_project(row, col, camera, step=None)`` 使用相应记录的深度与标定。
  像素为行列顺序，世界坐标单位米；Isaac USD 相机的视线为 -Z、+Y 向上，
  使用光轴深度，不直接照搬其他仿真器的坐标符号。
* RGB、深度、标定必须来自同一 camera／step。非法深度不当作有效点，
  只读查询不能偷偷刷新成另一帧。可见表面点不是物体中心或可靠抓取位姿。

运动与结束
~~~~~~~~~~

* ``move_to(arm, xyz, quat=None, gripper=None, substeps=25)``：
  世界坐标米、四元数 wxyz；省略姿态保持调用时实测姿态，省略夹爪保持控制目标。
  使用原生 cuRobo 完整位姿规划，不走旧位置-only IK 工具。
* ``substeps`` 是规划轨迹的采样数量控制，不是秒、速度或物理仿真步数。
  0 保留整条路径，1 仅执行终点，至少 2 时最多保留该数量的采样点。
  轨迹抽稀不保证连续路径安全；不能只因规划成功就声称完整避障。
* 原生默认障碍物模型只有简化桌面及其配置中的机器人碰撞检查，
  不保证瓶子、碗、另一机械臂均已进入规划世界。
* ``rotate_wrist(arm, delta_yaw_deg, gripper=None, substeps=25)``：
  绕世界 Z 轴相对旋转，单位度，随后走相同位姿执行路径。
* ``set_gripper(arm, val, steps=10)``：0 闭、1 开，0.5 是中间目标开度，
  不是二值命令；实际张口还受接触和物理控制影响。
  从当前实测开度分步向目标变化，其他双臂关节／夹爪控制目标保持不变。
  底层仍有插值，因此 10 次目标更新不等于 10 个物理仿真步或 10 秒。
* ``release(arm, val=1.0, steps=10)`` 复用夹爪控制。
  越界、非有限用户输入不静默裁剪；实测开度因物理超调越界时，
  仅插值起点可限幅，这不是改变用户目标。
* 动作反馈含 ``completed``、``executed_steps``／``executed_actions``、
  ``stop_reason`` 等。部分执行、中断、预算耗尽或未知执行状态不能报完整完成。
  ``completed`` 表示计划中的命令执行完，不表示物体已抓住或子任务成功。
* ``move_to`` 的 ``final_eef_xyz``、``final_dist_m`` 来自机器人自身末端反馈，
  不是物体特权位姿，不是新的“达到某精度才完成”判据。
* ``finish`` 结束运行，成功仍由原生环境判定并写入 ``result.json``。
  Agent 声称成功、工具返回成功、进程正常退出，均不能代替原生任务成功。

探索、场景与记忆
~~~~~~~~~~~~~~~~

* 场景身份保留 ``task + seed + layout``：seed 是官方布局组，layout 是组内编号。
  不把两者硬压成新 seed；默认均为 0，记录标签为 ``task_s<seed>_l<layout>``。
  普通 ``--seed`` 不等于承诺对所有 CUDA／物理随机性做全局确定性控制。
* ``reset`` 仅在探索模式注册，恢复同一 task／seed／layout，不能悄悄换场景。
  ``--explore --random`` 被拒绝。正式单次评测不因迁移而开放 reset。
* 默认每会话最多 5 次尝试：首次 + 最多 4 次 reset；默认 3 个探索会话。
  ``--explore-attempts-per-session 0`` 仅关闭尝试次数上限，不关闭其他预算。
* 有限尝试未用完且未成功时，探索 ``finish`` 会被拒绝；已原生成功时拒绝 reset。
  这些是 Toolkit 的执行限制，提示词另负责要求保存尝试记录、改变策略和复查观测。
  不是仅靠 prompt 提醒，也不是把“五次尝试”塞进单次运动控制器。
* 复用 RPent 的探索会话／记忆 inbox；Agent 不直接写已发布记忆。
  动作配方只导出最后一次成功尝试中的动作，不包含看图、分割、查询和 reset。
  因而 JSONL 没有某个感知工具不能证明 Agent 没调用过，应看 transcript。
* 默认不注册通用 ``execute_action``。Flash 在参数校验阶段明确拒绝，
  不要把旧 Flash 文件或 eval-fair 内部接口误当作已完成的正式评测入口。

VPP2 的接入决策
---------------

Agent 与模型分工
~~~~~~~~~~~~~~~~

用户已明确选择 ``vpp2_act(instruction, chunks=1)``，instruction 必须是 Agent
当前给出的子任务，不默认回退到环境原始整段指令。环境原始任务说明和成功标准不变。
子任务可描述物体、目标位置／关系、必要的手臂配合与操作方式，优先用清晰英文；
精确世界坐标和毫米精度控制仍用解析式工具。能传入文本不等于模型能理解或完成。

每次推理预测 32 步双臂绝对 EE16 动作，执行前 24 步；多 chunk 时用真实反馈重新推理。
EE16 的顺序为左臂 xyz + wxyz + 开度，随后右臂同样 8 维。
执行时使用原生 EE 控制，不能把它当成 RoboTwin 动作数组，
也不是为每个 VPP2 目标调用解析式 ``move_to`` 的 cuRobo 路径规划。
一块执行中 Agent 不逐物理步决策；块完成后获得观测再决定下一次调用。

RPent 替代的是官方外层评测调度中的任务分解／调用时机，
没有替换 VPP2 的视频模型、动作专家或声称移除了模型内部的高层模块。
新适配器复用官方模型和预处理，不调用官方完整 benchmark 脚本。

历史缓存与时序
~~~~~~~~~~~~~~

* Env 客户端在真实 reset 的初始观测建立第 0 帧和初始锚点；不等第一次调用 VPP2。
* 每执行一个原生动作并收到对应观测，加入三路 uint8 RGB。
  解析式动作和 VPP2 动作共用同一条时间轴；以反馈的实际执行计数为准。
* 推理时看到的是“截至当前”的历史，包含已完成动作后的观测，不是未来画面。
  初始未动作时只有初始观测；缺失的早期采样用初始锚点补齐。
* 缓存最多保留初始锚点及最近 177 个时刻。若当前动作编号为 t，
  请求包含锚点和 ``t-175, t-150, ..., t-25, t`` 共八个采样时刻。
  小于 0 的时刻用锚点，不是每次把全部缓存传给模型。
* 三路 640×480 RGB 的原始有界缓存约 469 MiB／回合，不保存所有历史深度。
  Python 对象、RPC 序列化、瞬时副本及模型处理还需额外内存；
  EnvState 的落盘观察记录／视频是另一套机制，磁盘占用仍随运行增长。
* 多次看图、分割或 render 不计成多个动作步。EnvState 的记录编号、
  原生动作计数、VPP2 推理序号是三种不同计数，不能混用。
* 子任务切换不清空历史或重置推理序号。实际 reset 清空两者；
  推理请求先预留序号，失败也不随意复用同一个序号／随机种子。
* RPC 超时或动作后观测缺失会使历史失效。不能假定动作没发生而自动重试，
  也不能靠重新看一帧伪造缺失历史；需要真实 reset，不能放宽评测限制。
* 模型服务只共享权重，不另外保存持续同步的回合图像历史。
  每个请求带自己的历史、当前 EE16 状态、子任务和推理序号，
  通过已有服务写锁串行推理。

与此前 UniWAM 接入的相同点是“会话／环境侧保留近期反馈，服务端做模型适配”；
不同点是这里使用三路视觉历史和官方时间采样，不是最近 16 条关节／夹爪目标。
不要直接复制 UniWAM 的缓存长度、动作表示或服务端输入格式。

代码和资源
----------

安装与服务启动见 ``docs/source-zh/rst_source/simulators/robodojo.rst``；
测试入口见 ``tests/README.md``。环境、权重、仿真资产、凭据和运行结果不在 Git 中。
在新机器上重建独立环境，不直接复制旧机器的虚拟环境。

旧机器的 ``.git/info/exclude`` 不随 clone 复制。开始安装前，用编辑器在新副本的
``.git/info/exclude`` 增加以下本地规则，并用 ``git check-ignore`` 核对：

.. code-block:: text

   /.venv-robodojo/
   /.venv-vpp2/
   /local/
   /results/
   /LOCAL_SETUP.txt

不要把模型、日志、视频、虚拟环境或认证文件放入暂存区。
已有全局 ``.gitignore`` 不覆盖上面所有目录，不能假设创建出来就会自动忽略。

* IsaacLab 固定版本：``afca7b09d60d8beb9c1cb28b43066499940b969b``。
* VPP2 官方代码固定版本：``72c17acf022494ff63617be86079bb92e92f5bf8``，
  仓库为 ``https://github.com/roboterax/video-prediction-policy-2``。
* VPP2 资源根目录须包含 ``policy/src/vpp2/policy.py``、
  ``checkpoints/joint2b_s100000/`` 完整配对权重（含 manifest）及
  ``checkpoints/Wan2.1-I2V-14B-480P/`` 共享编码器。
* 官方权重：``https://huggingface.co/Haodong082399/VPP2``；
  官方文档列出的国内源：``https://modelscope.cn/models/haodong123/VPP2``。
  2026-10-19 查询所需文件清单合计约 53.51 GB；这是磁盘大小，不是显存估计。
* 转移 RoboDojo Assets 后，按安装指南重新生成机器人配置中的绝对路径。
  SAM3 单独准备 ``sam3.pt``，设置 ``SAM3_CHECKPOINT_PATH``。
* 旧机器额外使用的兼容约束为 ``sse-starlette==2.3.6``、
  ``wrapt==1.17.3``、``pyarrow==21.0.0``。这些是复现线索，
  不是已验证的新机器锁文件；安装后核对依赖，不修改其他项目环境。

已验证环境的版本线索（读取已安装元数据，不代表已生成可移植 lock）：

.. code-block:: text

   Python: 3.11
   isaacsim: 5.1.0.0
   torch: 2.7.0; torchvision: 0.22.0
   transformers: 4.57.6; numpy: 1.26.0
   rlinf: 0.4.0
     Git commit: 91e0c6e361eff9371e2423a4183602481ae95ee5
   rlinf-robodojo-runtime: 0.3.0
     Git commit: 6d76a0c4a49a7a47bf5ee3924de2ccd7ecb8a8b7
   nvidia-curobo: 0.0.post1.dev101
     Git commit: 895c6517243f8cb091c73c018c8167192d39599a

``pyproject.toml`` 中部分 Git 依赖使用分支引用，未来安装可能解析到不同提交。
若需要重现这次运行，核对上述 commit；不要把新解析到的依赖自动当成同一个环境。
仓库的 ``requirements/robodojo-override.txt`` 是当前安装入口的一部分，
不能因依赖检查报告冲突就全盘升级 Torch、NumPy 或删除约束。

VPP2 只下载推理所需的 100k 配对权重和共享编码器，不需要训练数据、优化器状态、
initialization 或其他任务权重。获准下载后，可在独立下载环境执行官方国内源命令：

.. code-block:: bash

   # 将目标改为自己有权写入的资源目录；不要覆盖他人资产。
   modelscope download --model haodong123/VPP2 \
     --local_dir /path/to/vpp2 \
     --include 'config.json' 'checkpoints/joint2b_s100000/**' \
               'checkpoints/Wan2.1-I2V-14B-480P/**'

再将固定版本的官方代码放在该目录的 ``policy/``，保留 bundle 的
``action.pt``、``video.pt``、``dataset_stats.json``、``manifest.json``。
下载前记录源 revision／文件清单，下载后核对大小和哈希。
国内源在旧机器上仅验证了文件列表可访问，未验证整包下载、带宽或模型加载。
同名编码器只有在内容哈希一致时才可复用，不要用 Wan2.2 VAE 替代 Wan2.1 VAE。

已验证与未验证
--------------

2026-10-19 在本项目独立 Python 3.11 环境中的历史验证：

* 聚焦测试：252 passed，5 项 GPU 测试跳过。
* 全量单元测试：1517 passed，11 skipped，1 failed。
  未修改的 Codex grounding 测试因 CLI 暴露 ``apply_patch`` 而失败；
  不能删掉断言或把它算作通过。
* 在 A800 80GB 上的 Env 与真实 SAM3 检查：2 passed，377.02 秒。
  覆盖 RGB-D、双臂夹爪 0/0.5/1、保持其他控制目标、位姿规划／旋转、
  原生 EE hold、动作历史／reset，以及 SAM3 分割和同帧反投影。
* 官方输入处理函数对照通过；未加载真实 VPP2 权重。
* VPP2 权重推理、完整 VPP2 策略链、任务成功率和 3090 运行均未验证。
  Sphinx 未安装，双语文档未做 HTML 构建验收。

原始证据保留在旧工作区 ``results/vpp2_integration_20261019/``，未上传。
历史 A800 运行不表示该硬件得到 Isaac Sim 官方支持，也不证明新机器兼容。

本分支提交前另跑 RoboDojo、工具 schema、planner API 和机器人注册契约：
323 passed，5 项 GPU 测试跳过；本次迁移未重新启动 GPU 或下载模型。

证据文件索引（相对于旧项目根目录，默认不会出现在新 clone）：

* ``results/vpp2_integration_20261019/validation.json``：历史验证汇总。
  其中 ``committed_or_pushed=false`` 是验证当时的快照，后续已提交到上述分支，
  不要把该历史字段当成今天的 Git 状态。
* 同目录 ``focused.xml``、``unit_no_proxy.xml``、``gpu.xml``：测试明细。
* 同目录 ``gpu/``：环境／SAM3 服务日志、RGB-D 状态和视频。
* 同目录 ``check_official_inputs.py``：一次性官方输入对照脚本，未作为产品源码上传。
  对照时刻为 0、24、26、175、200；比较官方图像拼接、历史 bf16→uint8 往返、
  锚点／采样、状态、prompt 及随机种子，张量相等不代表真实权重推理已通过。
* 同目录 ``pre_vpp2_sources.tar.gz`` 和 ``vpp2-only.patch``：当时用于将
  VPP2 修改与此前解析式工具修改分开审阅的本地材料。首次 Git 提交合并了这两部分。
* ``results/primitive_migration_20261018/``：此前解析式迁移检查，
  ``gpu_v2`` 环境冒烟 1 passed，239.27 秒；早期初始化曾触发 60 秒测试超时，
  后续已给独立 GPU 检查设置更长上限，不是通过删除动作断言解决。

新会话若读不到旧结果，只能引用这些历史记录，不能声称自己已在新机器复现。
需要原始证据时再与用户协调转移指定文件，不上传整批可能包含会话内容的运行日志。

此前出现的问题与不要误判的事项
------------------------------

* Codex grounding 失败属于独立视觉定位组件的 CLI 工具隔离约定：
  像素返回正常，但工具列表中仍有 ``apply_patch``。
  这不是 RoboDojo 的 SAM3 或机械臂失败，相关实现及断言未被本次迁移修改。
* 全量测试最初另有四项 localhost HTTP 502；配置 loopback 的 ``NO_PROXY``
  后消失。不要把本地 RPC 送进 VPN／HTTP 代理，也不要为通过测试删除断言。
* 环境中仍有仓库 override 对仿真包元数据约束的覆盖，以及 Requests 依赖警告。
  应区分已知元数据不一致与实际 import／执行失败；不能简单宣称依赖检查全绿。
* 旧 release 项目在 2026-10-15 跑过 ``put_bottles_into_dustbin`` layout 0，
  策略是 Pi0.5 而非 VPP2：看图／SAM3／反投影／动作／finish 完成，
  进程退出 0，但原生 ``success=false``，三路视频各有 720 帧解码记录。
  这是历史链路证据，不是当前 VPP2 的验收证据。
* 旧 release 首次尝试被模型拒绝 ``reasoning_effort=none``；改成 medium 后运行。
  后续策略 14 个 50 步 chunk 对应 700 步预算，旧工具将耗尽标成 terminated，
  耗尽后仍允许恢复调用。新 ``_execute`` 在动作前检查预算，但仍需完整链路验证。
  不能把旧任务失败直接归咎于显卡，也不能由此断言 Pi0.5 的失败根因已查明。

硬件结论的边界
--------------

旧机器为 A800 80GB、驱动 570.172.08。本地 Env、相机和 SAM3 曾实际运行，
但没有证明全部渲染效果、所有任务、长时间并行稳定性或与 RTX 的画质／速度一致。
没有 RT Core 的硬件不在 Isaac Sim 官方支持范围内；
Omniverse 底层文档允许非 RTX 运行部分能力但不作支持保证。
我们没有确认这套驱动的具体底层渲染执行路径，不能擅自说是 CPU 渲染或某种降级。

官方说明：

* ``https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/requirements.html``
* ``https://docs.omniverse.nvidia.com/materials-and-rendering/latest/rtx-renderer_architecture_support.html``

3090 的 RT Core 不等于新机器已通过验收，也不等于满足所有版本推荐配置。
尤其要区分仿真和模型：Env／SAM3 可以先独立检查，
VPP2 Video + Action 权重本身约 36.85 GB，另有共享编码器和运行时显存。
不能从“3090 有 RT Core”推导出“单卡 24 GB 能运行整套 VPP2”。
当前服务调用官方默认 CUDA／bf16 路径，未增加量化、多卡分片或 CPU 卸载。
不能擅自缩小模型、历史或预测步数来换取运行，再声称保持官方策略语义。

新机器验收顺序
--------------

1. 核对实际 GPU 数量、显存、驱动及 CUDA/NVCC；先安装仿真环境和资产，
   按 ``tests/README.md`` 运行 ``test_environment_smoke.py``，再验收 SAM3。
   本分支尚未在 3090 上运行，不能把硬件型号当作验收结果。
2. 单独准备 VPP2 环境。官方参考安装使用 CUDA 13.0 的 PyTorch，
   必须核对目标驱动，不要直接覆盖仿真环境的 Torch 版本。
   单张 3090 的 24 GB 显存不能被视为足以容纳当前 VPP2 默认加载方式；
   此适配器没有新增量化、多卡切分或 CPU 卸载能力。
3. 可在另一台大显存机器上启动 ``robots.robodojo.vpp2_server``，
   仿真端通过 ``--vla-endpoint socket://127.0.0.1:9201`` 接入。
   跨机器使用受控 SSH 隧道，不把无认证 RPC 端口直接暴露到公网。
4. 先验证真实模型预测，再验证解析式动作与 VPP2 混合执行、图像历史、
   步数耗尽／中断、reset 和进程清理。正常 CLI 默认启动 Env、SAM3、VPP2，
   不是只安装仿真即可运行。现有模型 E2E 用 ``VPP2_MODEL_PATH`` 启动本地服务，
   没有仅靠环境变量选择远端 VPP2 的入口；跨机测试需显式传递 endpoint，
   不能把这些本地测试命令直接当作跨机测试。
5. 功能和资源验收通过后再评测任务成功率；本次迁移不自动启动 benchmark。

可复制的继续验证入口
--------------------

以下都是新机器准备步骤，不是本次已执行的操作。先获得对应资源和运行授权，
将示例路径改为自己的目录；每轮用新输出目录，失败证据不要覆盖。

拉取与环境准备
~~~~~~~~~~~~~~

.. code-block:: bash

   git clone --branch feat/robodojo-primitives-vpp2 \
     https://github.com/huanming99/RPent.git RPent-Robodojo
   cd RPent-Robodojo
   git status --short
   git log -3 --oneline
   # 先设置上文的 .git/info/exclude，再按使用指南安装。
   uv venv --python 3.11 .venv-robodojo
   source .venv-robodojo/bin/activate
   uv pip install -e '.[robodojo-sim,sam3,test]' \
     --extra-index-url https://pypi.nvidia.com \
     --override requirements/robodojo-override.txt

这只是 Python 依赖入口，之后仍需按指南安装固定版本 IsaacLab 的三个 editable
包、配置 RoboDojo Assets／cuRobo 路径、准备 SAM3，并核对驱动和 NVCC。
镜像或旧资产可复用，但不能省掉版本／路径检查。不要安装带旧 Pi0.5 的完整 extra
来代替 VPP2 的独立依赖准备。

进入已经准备好的仿真环境后，设置当前机器的路径：

.. code-block:: bash

   export PYTHONNOUSERSITE=1
   export ROBODOJO_ASSETS_ROOT=/path/to/robodojo
   export SAM3_CHECKPOINT_PATH=/path/to/sam3/sam3.pt
   export ROBODOJO_PLACEMENT_SETTLE_STEPS=1000
   # 避免工作区另一个 rlinf checkout 遮蔽已安装的适配器。
   export RPENT_RLINF_ROOT="$(python -c 'import sysconfig; print(sysconfig.get_path("purelib"))')"
   export NO_PROXY=127.0.0.1,localhost,::1
   export no_proxy="$NO_PROXY"

若已有 NO_PROXY 必须保留的条目，追加上述 loopback 而非覆盖。不要将代理账号、
token 或 SSH 私钥写进仓库。旧机器 ``local/activate.sh`` 含固定路径和旧策略变量，
不应直接 source 到新机器。CLI 不自动加载某个自建 runtime.env。

离线检查
~~~~~~~~

先确保当前 shell 没有启用 GPU 测试标志：

.. code-block:: bash

   unset RPENT_RUN_ROBODOJO_INTEGRATION
   CUDA_VISIBLE_DEVICES='' python -m pytest \
     tests/unit_tests/robots/robodojo \
     tests/unit_tests/robots/test_tool_schema_contracts.py \
     tests/unit_tests/rpent/planner/test_api_contracts.py \
     tests/unit_tests/rpent/robots/test_registry_contracts.py \
     tests/e2e_tests/robodojo -q --tb=short
   rpent --robot robodojo --help
   python -m robots.robodojo.vpp2_server --help

这些 help 命令不加载模型；离线契约通过不表示权重可推理。
提 PR 前按 CONTRIBUTING 运行全部单测和 pre-commit，不只跑上面子集。

Env 与 SAM3 的真实检查
~~~~~~~~~~~~~~~~~~~~~~

先用 ``nvidia-smi`` 核对并协调空闲设备、确认 NVIDIA 许可。
下面的 0 仅是例子，必须替换为实际预留的物理 GPU 编号。

.. code-block:: bash

   export CUDA_VISIBLE_DEVICES=0
   export OMNI_KIT_ACCEPT_EULA=YES
   export RPENT_RUN_ROBODOJO_INTEGRATION=1
   mkdir -p logs
   export RPENT_E2E_OUTPUT_DIR="$(mktemp -d "$PWD/logs/robodojo-env-check.XXXXXX")"
   python -m pytest tests/e2e_tests/robodojo/test_environment_smoke.py \
     -v -s --junitxml="$RPENT_E2E_OUTPUT_DIR/env.xml"

   export RPENT_E2E_OUTPUT_DIR="$(mktemp -d "$PWD/logs/robodojo-sam3-check.XXXXXX")"
   python -m pytest tests/e2e_tests/robodojo/test_components.py::test_sam3_component \
     -v -s --junitxml="$RPENT_E2E_OUTPUT_DIR/sam3.xml"

Env 检查不要求 VPP2 或 SAM3 权重；第二项要求真实 SAM3。
两项独立超时为 900 秒，包含 Isaac 初始化；检查服务退出和 GPU 释放。
不要使用 ``run_gpu_suite.sh robodojo``：RoboDojo 还不是该 runner 的支持目标。

模型在另一台机器运行
~~~~~~~~~~~~~~~~~~~~

在模型机的独立环境安装同一 RPent 分支核心包和固定 VPP2 代码的推理依赖，
根据驱动选择兼容 PyTorch 构建。先核对权重、加载和一次推理的显存，
不要因为官方命令使用 cu130 就给旧驱动机器盲装该构建。
模型服务的启动示例（模型机自己的已预留 GPU）：

.. code-block:: bash

   python -m robots.robodojo.vpp2_server \
     --model-path /path/to/vpp2 --host 127.0.0.1 --port 9201

在仿真机用自己的 SSH 配置建立隧道，``MODEL_HOST`` 为已配置的模型机别名：

.. code-block:: bash

   ssh -N -L 9201:127.0.0.1:9201 MODEL_HOST

模型保持监听远端 loopback；仿真机的 9201 通过隧道转发，不需要把 RPC 改成公网监听。
服务必须是本分支 ``VPP2Facade`` 的 socket 协议，不能直接填官方 XPolicyLab
服务地址。连接已有服务时 RPent 不拥有其生命周期，需由启动者负责结束。

在仿真机准备好 Planner 后，CLI 接入形式为：

.. code-block:: bash

   # PLANNER_MODEL 替换为当前账号可调用的模型；先验证 planner 连通性。
   rpent-check-llm --planner codex --model PLANNER_MODEL --json
   rpent --robot robodojo --task put_bottles_into_dustbin \
     --seed 0 --layout 0 --planner codex --model PLANNER_MODEL \
     --reasoning-effort medium --max-turns 40 --planner-timeout-s 1500 \
     --vla-endpoint socket://127.0.0.1:9201 \
     --output-dir /path/to/new-run-output

这是会实际运动的完整 CLI，不是只加载环境的探针。
``--sim-python`` 只选择仿真解释器；``--pi05-python`` 不能指定 VPP2 解释器。
本地自动启动 VPP2 使用 CLI 当前解释器，分离模型环境应显式接入 endpoint。

模型 E2E 的现有范围与缺口
~~~~~~~~~~~~~~~~~~~~~~~~~

在依赖兼容、显存足够且可以本地启动模型的环境中，设置 ``VPP2_MODEL_PATH``
和前面的 GPU opt-in 变量，可运行：

.. code-block:: bash

   export VPP2_MODEL_PATH=/path/to/vpp2
   export RPENT_E2E_OUTPUT_DIR="$(mktemp -d "$PWD/logs/robodojo-vpp2-check.XXXXXX")"
   python -m pytest \
     tests/e2e_tests/robodojo/test_components.py::test_vpp2_component \
     tests/e2e_tests/robodojo/test_policy_chain.py \
     -v -s --junitxml="$RPENT_E2E_OUTPUT_DIR/vpp2.xml"

这三项的超时为 2400 秒。component 在解析式夹爪动作后预测并执行一个原生 EE
目标；policy-chain 的两个 case 分别执行夹爪动作或一个 VPP2 chunk，
使用本地 scripted planner，不需要外部 Planner 账号。
检查看图／分割／深度查询、动作、更新图像和 finish，不要求任务完成。

这些测试目前自己组装 argv，不从任意自建 VPP2_ENDPOINT 环境变量读取远端地址。
若采用跨机部署，应先确认并以最小改动让现有测试显式传递 ``--vla-endpoint``
和恰当的前置条件；不要另建一套测试框架、删掉已有断言，
也不要将手工 CLI 跑完等同于全部 E2E 已通过。

下一轮的通过条件与提交前检查
----------------------------

继续工作时按以下顺序记录证据：

1. 新机器安装、驱动、资源路径、Python／依赖版本与实际 GPU 身份。
2. 三路画面有有效内容且随动作变化；RGB-D 对齐、世界点有限；
   深度／反投影的一致性测试不等于对所有材质的绝对深度精度验收。
3. 左右夹爪 0／中间值／1 方向正确；其他控制目标保持；
   小位姿移动／旋转实测变化，不能让 no-op 通过。
4. 真实 VPP2 加载、完整预测为有限 ``(32,16)``，实际执行前缀遵守 24 步语义。
   记录加载／推理峰值显存与耗时，不用权重磁盘大小冒充显存测量。
5. 解析式干预后 VPP2 使用新历史；子任务切换不断档；读取不推进动作步；
   reset 清空历史／推理序号；中断／预算耗尽不误报完整执行。
6. CLI 到工具、模型、环境、finish 的调用链及原生 ``result.json`` 均留证据，
   有界测试即使任务未成功也可以验证链路，但必须同时报告原生成功标志。
7. 自己启动的服务退出、借用服务未被误杀、GPU 释放、原始日志可追溯。
8. 最后才决定是否扩大到多个 task／seed／layout 或 benchmark；
   未获用户确认不要自动扩容、批跑、训练或改变策略配置。

提交上游 PR 前还需：

* 用户审核完整实现；当前 fork 分支是迁移快照，不是已审核可合并 PR。
* 核对上游 main 的变化，再决定 rebase／合并；不要自动重写已推送历史。
* 运行 ``pre-commit run --all-files``、完整 ``pytest tests/unit_tests -v``，
  如仍有独立 grounding 失败，应保留证据并单独处理，不能隐藏。
* 安装文档依赖后按 ``docs-check`` 构建中英文 Sphinx，并检查实际渲染。
* 检查导入、CLI help、资源缺失错误及可选依赖边界；不要将 GPU／网络变成离线单测要求。
* 核对生产改动仍局限于 RoboDojo，通用测试辅助变更不破坏其他机器人。

给新 Codex 会话的启动消息
-------------------------

可复制下面这段，并补充新机器项目路径和当前允许使用的资源：

.. code-block:: text

   请继续 huanming99/RPent 的 feat/robodojo-primitives-vpp2 分支。
   先读取本机适用的 AGENTS.md、CONTRIBUTING.md，以及
   robots/robodojo/HANDOFF.rst；按任务读取 docs-check、verify-change
   或 add-robot 技能。先核对 Git 状态，不切回 main，不恢复 PR219。
   解析式 Primitive 与 VPP2 接入已提交，旧 A800 上 Env/SAM3 已有历史验证，
   真实 VPP2 推理、完整策略链和本机 3090 均未验收。
   保持已确认接口：0闭1开、世界米/wxyz、原生位姿规划、Agent 给子任务、
   horizon32/execute24、初始锚点+近期视觉历史，探索每会话默认5次尝试。
   不依赖 RoboTwin 专属代码，不抽新的公共框架，不修改旧 release 或其他环境。
   请先检查本机资源与现有资产，给出当前状态和下一步最小验证计划；
   3090 24GB 不代表足以运行 VPP2，必要时先讨论远端模型服务。
   不自动大规模下载、升级驱动、训练、刷榜或创建 PR；需要新决定先说明后果。
