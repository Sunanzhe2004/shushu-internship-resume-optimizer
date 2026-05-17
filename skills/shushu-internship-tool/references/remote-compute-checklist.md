# Remote Compute Checklist

用于远程服务器、云数据库、对象存储、GPU/AutoDL、容器平台或 CI/CD 环境，把“能不能跑、要多少钱、多久能出结果”尽快搞清楚。

## 启动前

- 明确目标：smoke test、demo、API 联调、数据库初始化、压测、baseline、modified run、ablation。
- 估算资源：CPU、内存、磁盘、带宽、数据库、对象存储、GPU、预计时长和预算。
- 准备输出目录：命令、日志、配置、截图、指标、账单或租用时长。
- 确认数据、依赖、镜像、模型或 seed data 能正常下载、挂载或初始化。

## 连接和环境

- 使用平台提供的 SSH、密钥或 Web terminal。
- 记录镜像、OS、语言运行时、数据库、CUDA/PyTorch、驱动版本。
- 建虚拟环境或 conda env。
- 固定依赖版本；失败时记录冲突和修复。

## 数据、配置和状态

- 优先用公开镜像、官方下载、平台数据盘或用户已有合法数据。
- 记录下载命令和来源 URL。
- 大文件放数据盘或缓存目录，避免污染 repo。
- 数据库迁移、seed data、环境变量、secret placeholder 和 checkpoint 命名要能复现。

## 运行

- 先跑小样本 smoke test。
- 再跑 baseline、demo、接口联调或端到端流程。
- 最后跑 modified experiment、压测、部署演示或对比版本。
- 每次运行保存：命令、stdout/stderr、config、硬件信息。时间紧时至少保存最终命令和关键输出。

## 成本和失败恢复

- 设置最大运行时长和预算上限。
- 长任务前确认自动关机、预算提醒或手动停止策略。
- 失败时优先保存日志和环境信息，再删机器。
- 面试中如未完整跑完，把表达重点放到“已完成 smoke test / 跑通流程 / 设计了完整验证方案 / 知道卡点和资源预算”。
