# 更新说明

## 近期更新

### 公开示例与仓库可用性

- 新增 `examples/minimal_input/`，提供可公开提交的最小示例输入
- 新增 `assets/workflow-overview.svg`，帮助快速理解输入、主流程和输出结果
- README / README.en 首页补充了流程图、试跑说明、CLI 入口和本地检查说明

### 工作流修复

- 修复 `achievement_audit` 对无结构项目总结的 fallback 拆分逻辑
- 修复 `interview_pack` 中项目介绍开场和分块表达的回归问题
- 修复 `resume_rank` 的 JD 关键词提取与最终排序逻辑

### 当前公开仓库状态

- 仓库默认提供公开示例输入，不再默认包含私有测试材料
- 文档更明确地区分了“公开 demo”与“用户本地私有材料”
- 已补充安全提醒，强调不要提交未脱敏的内部资料、凭证和敏感业务信息

## 可直接复用的项目更新描述

### 版本说明

这次更新主要补了三部分：公开可运行的最小示例输入、更清晰的 README/CLI 使用说明，以及审计排序链路中的几个回归修复。现在新用户拿到仓库后，可以先用公开样例快速试跑，再替换成自己的本地材料。

### 适合发动态 / 发帖的短版

最近把 `shushu-internship-resume-optimizer` 又往开源可用的方向推了一步：

- 补了公开最小示例输入，别人 clone 下来可以直接试跑
- README 首页重构了一轮，流程和输出更容易看懂
- 修了 `achievement_audit`、`resume_rank`、`interview_pack` 里的几个回归问题
- 当前公开链路测试已通过

如果你也在整理实习项目、准备把经历写进简历，欢迎用脱敏材料试试，也欢迎提 issue 或建议。

### 适合发 release 的英文短版

This update improves the repository from both an open-source usability and workflow stability perspective:

- added a minimal public demo input set under `examples/minimal_input/`
- added a workflow overview diagram for faster onboarding
- improved README / README.en homepage structure and CLI guidance
- fixed regressions in `achievement_audit`, `resume_rank`, and `interview_pack`

The repository is now easier to try with public sample inputs before plugging in private local materials.

## 可直接复制的 release 模板

### 中文模板

标题：

`feat: add public demo inputs and polish resume-ranking workflow`

正文：

本次更新主要围绕“公开可用性”和“链路稳定性”做了一轮打磨：

- 新增 `examples/minimal_input/`，提供可公开提交的最小示例输入
- 新增流程图，帮助快速理解输入、主流程和输出结果
- 重构 README 首页结构，补充试跑说明、CLI 入口和本地检查说明
- 修复 `achievement_audit`、`resume_rank`、`interview_pack` 的若干回归问题

当前仓库更适合新用户先用公开样例快速试跑，再替换成自己的本地脱敏材料。

### English Template

Title:

`feat: add public demo inputs and polish resume-ranking workflow`

Body:

This release focuses on two things: public usability and workflow stability.

- added a minimal public demo input set under `examples/minimal_input/`
- added a workflow overview diagram for faster onboarding
- improved README / README.en structure and CLI guidance
- fixed regressions in `achievement_audit`, `resume_rank`, and `interview_pack`

The repository is now easier to try with public sample inputs before switching to private local materials.
