RoboDojo 跨机器验证交接
======================

此分支保存解析式 Primitive 迁移和 VPP2 接入，基于 RPent
``58844d554e8a62797d7f4a1cd52e30eaf82d91a7``，不是 PR #219，
尚未合并后续 upstream/main。提交用于继续验证，不代表可发布或刷榜验收完成。

代码和资源
----------

安装与服务启动见 ``docs/source-zh/rst_source/simulators/robodojo.rst``；
测试入口见 ``tests/README.md``。环境、权重、仿真资产、凭据和运行结果不在 Git 中。
在新机器上重建独立环境，不直接复制旧机器的虚拟环境。

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
