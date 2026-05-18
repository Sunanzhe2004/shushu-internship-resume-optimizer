# Shushu 实习简历优化器

把实习过程中的代码仓库、项目总结、业务背景材料，整理成更适合写进简历、用于面试复盘的内容。

[简体中文](./README.md) · [English](./README.en.md) · [贡献指南](./CONTRIBUTING.md)

## 项目定位

这个仓库面向正在实习、准备秋招 / 春招，或者想把手头项目沉淀成更清晰求职材料的同学。

它不是“直接帮你生成一份简历”的黑盒，而是先拆解原始材料，补证据、做风险提醒、排序成果，再产出更适合你自己二次确认和改写的内容。

## 核心能力

- 审计多源实习材料：支持 `code_repo`、`project_summary`、`business_docs`
- 从原始材料中归并成果项，抽取证据、业务背景、技术栈、指标和缺失信息
- 结合目标 JD 对成果排序，生成更适合写进简历的表述
- 识别 AI 总结味重、机械重复、疑似夸大、需要本人确认的内容
- 区分“自己复盘版”和“简历压缩版”项目总结，避免长文直接贴进简历
- 生成 STAR 草稿、项目介绍、追问问答、风险回答、投递前检查清单

## 工作流

`JD + 多源实习材料 -> achievement_audit -> resume_rank -> interview_pack`

可选增强：

`business_docs -> doc_knowledge`

建议按下面顺序使用：

1. 准备 `sources.json`，把代码仓库、项目总结、业务背景文档整理进去。
2. 先跑 `achievement_audit`，看成果提取、证据抽取、AI 风险提醒是否合理。
3. 再跑 `resume_rank`，看哪些成果最适合当前目标岗位。
4. 最后跑 `interview_pack`，把结果转成 STAR、项目介绍和面试问答。

## 快速开始

```bash
cd shushu-internship-resume-optimizer
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

## 命令

### 1. 成果审计

```bash
python -m shushu_internship_tool.achievement_audit --sources your_materials/sources.json --out reports/audit --name internship-materials
```

输出：

- `achievement_audit.json`
- `overview.md`
- `overview.html`
- `business_context_rewrite.md`

这一层会额外处理：

- 长项目总结拆分成多个成果项
- 指标、证据、风险点、待补信息抽取
- `user_check_flags` 标记，提示哪些表述 AI 味重、边界不清或可能夸大
- 生成更适合自己复盘和面试解释的业务背景改写

### 2. 简历成果排序

```bash
python -m shushu_internship_tool.resume_rank --jd your_materials/target_jd.txt --achievements reports/audit/achievement_audit.json --target-role backend --out reports/rank
```

输出：

- `resume_rank.json`
- `resume_rank.md`
- `resume_project_summary.md`

这一层会额外给出：

- 更像简历 bullet 的推荐写法
- 哪些指标最值得补
- 哪些证据或实现细节还不够支撑当前表述
- 哪些句子过于机械、重复或 AI 味偏重

### 3. 业务文档知识层

```bash
python -m shushu_internship_tool.doc_knowledge --docs your_materials/business_overview.md --mode basic_rag --query "How does the workflow recover failures?" --out reports/knowledge
```

支持模式：

- `direct`
- `basic_rag`
- `knowledge_base`

### 4. 面试包

```bash
python -m shushu_internship_tool.interview_pack --project-notes reports/rank/resume_rank.json --target-role backend --out reports/interview
```

输出：

- `interview_pack.json`
- `resume_star.md`
- `project_intro.md`
- `interview_qa.md`
- `risk_answers.md`
- `application_checklist.md`

## 输出文件

命令里的 `your_materials/` 是示例占位路径，仓库不会提供你的私有输入材料；使用时请替换成你自己本地准备的 `sources.json`、JD 和业务文档路径。

- `business_context_rewrite.md`：更适合自己梳理业务背景和项目价值
- `resume_rank.md`：更适合看成果排序、风险点和补强建议
- `resume_project_summary.md`：更适合压缩成正式简历中的项目描述
- `interview_qa.md`：更适合面试前快速复盘

更推荐的用法不是把长项目总结直接贴进简历，而是：

1. 先喂给工具做拆解和审计
2. 用 `resume_project_summary.md` 做压缩版底稿
3. 再手动确认数字、边界、职责范围和措辞

## 设计原则

- 不编造数字，没有稳定指标就明确标注“待补量化 / 待补证据”
- 不只看代码，也重视业务背景和上下游流程
- 简历表达按目标岗位校准，而不是统一套模板
- 对 AI 总结味重或可能夸大的内容做显式提醒
- 优先产出“可投、可讲、可追问展开”的材料

## 参考与演化

这个仓库不是从零起的一套新工具，而是在原有工作流基础上的定向重构，主要延续了以下两条旧能力链路：

- `repo_audit`
- `candidate_score`

当前主流程为：

`achievement_audit -> resume_rank -> interview_pack`

可选增强能力：

`doc_knowledge`

原始项目仓库：

- `https://github.com/LiuMengxuan04/shushu-internship-tool`

## 当前状态

项目仍在持续开发中。

目前主要基于真实实习材料对部分链路做过验证，例如成果审计、简历排序、项目介绍、面试问答；知识层和部分边界场景仍需要更多测试样本。

仓库里的不少规则和生成逻辑还需要更多真实材料来继续打磨，欢迎体验、测试和提建议，一起把项目做得更稳。

## 参与贡献

欢迎一起完善这个项目。

如果你想改进成果抽取、简历改写、面试表达、测试覆盖或文档内容，建议先阅读 [CONTRIBUTING.md](./CONTRIBUTING.md)，也欢迎直接提交 Issue 或 PR。

## 安全提醒

使用这个项目整理实习经历、项目材料或业务文档时，请优先遵守所在公司或团队的安全规范，不要触碰公司安全红线。

尤其不要上传、提交或公开以下内容：

- 未脱敏的内部业务数据
- 公司内部文档、策略、流程细节
- 含有用户信息、账号信息、密钥、访问凭证的材料
- 任何明确不能对外传播的实习内容

如果你想体验测试，建议优先使用脱敏后的材料，或者自己手动改写后的项目总结。

## 兼容性

为了降低迁移成本，旧命令仍然保留为兼容别名：

- `shushu-repo-audit` -> `achievement_audit`
- `shushu-candidate-score` -> `resume_rank`

## 开发

```bash
pytest
```
