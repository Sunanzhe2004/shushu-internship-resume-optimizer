# Shushu 实习简历优化器

**把你的实习材料，从“散乱记录”变成“可投简历 + 可讲项目故事”。**

Shushu 会先审计成果与证据，再按目标 JD 排序，最后生成简历 bullet、项目总结、STAR 草稿、面试 Q&A 和风险检查清单。

[简体中文](./README.md) · [English](./README.en.md) · [贡献指南](./CONTRIBUTING.md) · [更新说明](./RELEASE_NOTES.md)

![workflow overview](./assets/workflow-overview.png)

> ⚠️ 使用前请先脱敏：不要提交公司内部文档、真实用户数据、密钥、访问凭证，或任何不能公开传播的实习材料。

## 快速入口

- [先跑一遍 Demo](#3-分钟试跑)
- [先看最近更新](#最近更新)
- [先看输出示例](#输出长什么样)
- [接入自己的材料](#接入自己的材料)
- [命名说明](#命名说明)
- [先看安全提醒](#安全提醒)

## 最近更新

这一轮更新把主流程进一步收敛到 `model-first, script-second`：

- `achievement_audit` 优先读取 `sources.json` 里的 `structured_extract_path` 或 `structured_extract`
- 如果同一次运行已经提供结构化抽取结果，`business_docs` 默认主要补业务上下文，不再单独产生成果候选污染主线
- `resume_rank` 不再依赖样例标题映射，更依赖 `task`、`actions`、`metrics`、`business_value` 等结构字段
- `interview_pack` 现在可以直接读取 `resume_rank.json` 里的 `ranked_achievements`，端到端 handoff 更稳定

更推荐的使用顺序是：

1. 先准备干净的 `project_summary.md` 或等价原始项目材料。
2. 如果材料很长、语义很密，先补一份 `structured_extract.json`。
3. 在 `sources.json` 里通过 `structured_extract_path` 接入这份结构化结果。
4. 让 `business_docs` 主要承担业务背景和流程上下文补充，而不是主导成果抽取。

## 它解决什么问题

很多实习材料的问题不是“没有内容”，而是内容太散：

- 代码仓库里有实现，但简历里讲不清贡献边界
- 项目总结写得很长，但不适合直接压成简历 bullet
- 面试时能回忆细节，却很难稳定讲出一条完整项目故事
- 直接用 AI 总结，容易出现空泛、机械、夸大或证据不足的表述

这个项目的目标不是替你“直接编一份简历”，而是先把原始材料拆开审计，再把可验证的成果、证据、风险和缺口整理出来，最后生成更适合你自己二次确认和改写的求职材料。

## 为什么用它

- 不是直接“编简历”：先提取证据、指标、职责边界，再生成表达
- 不是统一模板：会结合目标 JD 对成果排序
- 不是只看代码：同时支持 `code_repo`、`project_summary`、`business_docs`
- 不鼓励吹牛：会标记 AI 味、夸大风险和待确认信息
- 不止写简历：同时生成项目介绍、STAR 草稿、追问 Q&A 和投递前检查清单

## 3 分钟试跑

环境要求：`Python >= 3.10`

仓库内自带一套可公开提交的最小示例输入，适合先验证命令、输出结构和工作流，再替换成你自己的本地材料。

示例文件：

- `examples/minimal_input/sources.json`
- `examples/minimal_input/project_summary.md`
- `examples/minimal_input/business_overview.md`
- `examples/minimal_input/target_jd.txt`

```bash
git clone https://github.com/Sunanzhe2004/shushu-internship-resume-optimizer.git
cd shushu-internship-resume-optimizer

python -m venv .venv
```

macOS / Linux:

```bash
source .venv/bin/activate
python -m pip install -e ".[dev]"

python -m shushu_internship_tool.achievement_audit \
  --sources examples/minimal_input/sources.json \
  --out demo_reports/audit \
  --name demo-materials

python -m shushu_internship_tool.resume_rank \
  --jd examples/minimal_input/target_jd.txt \
  --achievements demo_reports/audit/achievement_audit.json \
  --target-role llm-application-intern \
  --out demo_reports/rank

python -m shushu_internship_tool.interview_pack \
  --project-notes demo_reports/rank/resume_rank.json \
  --target-role llm-application-intern \
  --out demo_reports/interview
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"

python -m shushu_internship_tool.achievement_audit `
  --sources examples/minimal_input/sources.json `
  --out demo_reports/audit `
  --name demo-materials

python -m shushu_internship_tool.resume_rank `
  --jd examples/minimal_input/target_jd.txt `
  --achievements demo_reports/audit/achievement_audit.json `
  --target-role llm-application-intern `
  --out demo_reports/rank

python -m shushu_internship_tool.interview_pack `
  --project-notes demo_reports/rank/resume_rank.json `
  --target-role llm-application-intern `
  --out demo_reports/interview
```

跑完后优先看：

- `demo_reports/audit/overview.md`
- `demo_reports/rank/resume_project_summary.md`
- `demo_reports/interview/interview_qa.md`

## 输出长什么样

下面是 README 里直接给你看的示意片段，重点不是“自动生成一堆文件”，而是让你快速判断输出是否像你真的会拿来改、拿来讲。

### `resume_project_summary.md` 示意片段

```md
- 围绕多源实习材料设计成果审计链路，统一整理代码仓库、项目总结与业务背景文档，
  将零散记录压缩为可复用的成果项与证据清单。
- 结合目标 JD 对成果进行排序，优先保留更能体现业务理解、实现深度和可量化影响的内容，
  用于生成更适合简历投递的项目总结底稿。
- 对 AI 味重、证据不足或职责边界不清的表述增加显式风险提醒，
  降低“看起来像写得很好、但追问就露馅”的问题。
```

### `interview_qa.md` 示意片段

```md
Q: 这个项目里你最核心的贡献是什么？
A: 我做的不是直接生成一份简历，而是把原始材料先拆成成果、证据和风险三层，
   这样后面的简历表达和面试回答都能围绕可验证信息展开。

Q: 为什么要加风险提醒？
A: 因为很多 AI 生成表述在“读起来顺”之外，还会出现夸大、空泛和边界不清的问题。
   我希望它先提醒哪些内容需要本人确认，再决定哪些能写进简历。
```

### `overview.md` 你通常会看到什么

- 每个成果项对应的证据、指标、业务背景和待补信息
- `user_check_flags` 标记，提醒哪些表述需要你亲自确认
- 更适合先复盘、再人工压缩进简历的材料结构

## 工作流

主流程：

`JD + 多源实习材料 -> achievement_audit -> resume_rank -> interview_pack`

可选增强：

`business_docs -> doc_knowledge`

推荐顺序：

1. 先准备 `sources.json`，把代码仓库、项目总结和业务背景文档整理进去。
2. 先跑 `achievement_audit`，确认成果抽取、证据和风险提醒是否合理。
3. 再跑 `resume_rank`，判断哪些成果最适合当前目标岗位。
4. 最后跑 `interview_pack`，把结果转成 STAR、项目介绍和面试问答。

## 接入自己的材料

最常见的完整链路是：

```bash
python -m shushu_internship_tool.achievement_audit --sources your_materials/sources.json --out reports/audit --name internship-materials
python -m shushu_internship_tool.resume_rank --jd your_materials/target_jd.txt --achievements reports/audit/achievement_audit.json --target-role llm-application-intern --out reports/rank
python -m shushu_internship_tool.interview_pack --project-notes reports/rank/resume_rank.json --target-role llm-application-intern --out reports/interview
```

最小输入结构可以参考 [examples/minimal_input](./examples/minimal_input/)：

- `sources.json`：输入索引，串起 repo、总结和业务文档
- `project_summary.md`：长一点也没关系，适合先交给工具做拆解
- `business_overview.md`：帮助补足业务背景、上下游关系和问题场景
- `target_jd.txt`：目标岗位 JD，用来做成果排序和表达校准

如果你想让材料先走结构化抽取，`sources.json` 可以这样写：

```json
{
  "code_repo": [
    { "path": "./repo", "label": "main-repo" }
  ],
  "project_summary": [
    {
      "path": "./project_summary.md",
      "label": "internship-summary",
      "structured_extract_path": "./structured_extract.json"
    }
  ],
  "business_docs": [
    { "path": "./business_overview.md", "label": "business-context" }
  ]
}
```

如果你还想让工具辅助理解业务文档，可以额外运行：

```bash
python -m shushu_internship_tool.doc_knowledge --docs your_materials/business_overview.md --mode basic_rag --query "What are the main failure modes?" --out reports/knowledge
```

## 命名说明

- 仓库名：`shushu-internship-resume-optimizer`
- Python package：`shushu-internship-tool`
- 模块路径：`shushu_internship_tool`
- Console scripts：`shushu-achievement-audit`、`shushu-resume-rank`、`shushu-interview-pack`
- README 里当前推荐运行方式：`python -m shushu_internship_tool.xxx`

这样做是为了优先保持当前包结构稳定；如果后续统一命名，会在更新说明里明确写出。

## 命令说明

### 1. 成果审计

```bash
python -m shushu_internship_tool.achievement_audit --sources your_materials/sources.json --out reports/audit --name internship-materials
```

输出：

- `achievement_audit.json`
- `overview.md`
- `overview.html`
- `business_context_rewrite.md`

这一层额外会做：

- 长项目总结拆分成多个成果项
- 指标、证据、风险点、待补信息抽取
- `user_check_flags` 标记，提示哪些表述 AI 味重、边界不清或可能夸大
- 生成更适合自己复盘和面试解释的业务背景改写

### 2. 简历成果排序

```bash
python -m shushu_internship_tool.resume_rank --jd your_materials/target_jd.txt --achievements reports/audit/achievement_audit.json --target-role llm-application-intern --out reports/rank
```

输出：

- `resume_rank.json`
- `resume_rank.md`
- `resume_project_summary.md`

这一层额外会给出：

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
python -m shushu_internship_tool.interview_pack --project-notes reports/rank/resume_rank.json --target-role llm-application-intern --out reports/interview
```

输出：

- `interview_pack.json`
- `resume_star.md`
- `project_intro.md`
- `interview_qa.md`
- `risk_answers.md`
- `application_checklist.md`

## 当前状态

相对稳定：

- 多源材料成果审计
- JD-based 成果排序
- 简历项目总结生成
- 面试 Q&A / STAR 草稿生成

持续增强：

- `doc_knowledge` 知识层
- 更多行业 / 岗位样本
- 更细粒度的 AI 味和夸大检测
- 更完整的测试覆盖

## 设计原则

- 不编造数字，没有稳定指标就明确标注“待补量化 / 待补证据”
- 不只看代码，也重视业务背景和上下游流程
- 简历表达按目标岗位校准，而不是统一套模板
- 对 AI 味重或可能夸大的内容做显式提醒
- 优先产出“可投、可讲、可追问展开”的材料

## 致谢与来源

这个仓库基于原项目做了面向“实习简历整理 / 面试复盘”场景的二次开发与定向重构。

当前主流程聚焦于：

`achievement_audit -> resume_rank -> interview_pack`

可选增强能力：

`doc_knowledge`

感谢原项目开发者提供基础工作流与思路，原始项目：

- `https://github.com/LiuMengxuan04/shushu-internship-tool`

## 参与贡献

如果你想改进成果抽取、简历改写、面试表达、测试覆盖或文档内容，建议先阅读 [CONTRIBUTING.md](./CONTRIBUTING.md)，也欢迎直接提交 Issue 或 PR。

## 安全提醒

使用这个项目整理实习经历、项目材料或业务文档时，请优先遵守所在公司或团队的安全规范，不要触碰公司安全红线。

尤其不要上传、提交或公开以下内容：

- 未脱敏的内部业务数据
- 公司内部文档、策略、流程细节
- 含有用户信息、账号信息、密钥、访问凭证的材料
- 任何明确不能对外传播的实习内容

如果你想体验测试，建议优先使用脱敏后的材料，或者自己手动改写后的项目总结。
