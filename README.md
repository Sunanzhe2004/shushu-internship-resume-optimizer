# Shushu 实习简历优化器

**把你的实习材料，从“散乱记录”变成“可投简历 + 可讲项目故事”。**

Shushu 会先审计成果与证据，再按目标 JD 排序，最后生成简历 bullet、项目总结、STAR 草稿、面试 Q&A 和风险检查清单。

最近更新：`2026-07-14`

[简体中文](./README.md) · [English](./README.en.md) · [贡献指南](./CONTRIBUTING.md) · [更新说明](./RELEASE_NOTES.md)

![workflow overview](./assets/workflow-overview.png)

> ⚠️ 使用前请先脱敏：不要提交公司内部文档、真实用户数据、密钥、访问凭证，或任何不能公开传播的实习材料。

## 快速入口

- [先跑一遍 Demo](#3-分钟试跑)
- [先看最近更新](#最近更新)
- [接入自己的材料](#接入自己的材料)
- [先看安全提醒](#安全提醒)

## 最近更新

这一轮更新把主流程进一步收敛到 `model-first, script-second`：

- `achievement_audit` 优先读取 `sources.json` 里的 `structured_extract_path` 或 `structured_extract`
- 结构化抽取存在时，`business_docs` 默认主要补业务上下文，不再单独产生成果候选污染主线
- `resume_rank` / `interview_pack` 进一步收回了脚本里的写法模板和项目类型硬编码，更偏向做结构化压缩、排序、提示与可读性复核
- 如果检测到强相关 bullet，脚本只给“可人工审阅的候选组合”和原因；项目边界、是否合并、最终语气优先交给 skill / prompt 层判断

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
- 脚本更像护栏：主要负责限额、排序、风险提醒和可读性检查，而不是替你拍板项目边界
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

## 工作流

主流程：

`JD + 多源实习材料 -> achievement_audit -> resume_rank -> interview_pack`

可选增强：

`business_docs -> doc_knowledge`

推荐顺序：

1. 先准备 `sources.json`，把代码仓库、项目总结和业务背景文档整理进去。
2. 先跑 `achievement_audit`，确认成果抽取、证据和风险提醒是否合理。
3. 再跑 `resume_rank`，判断哪些成果最适合当前目标岗位，并检查项目数、bullet 数和可读性提醒是否合理。
4. 如果输出里出现“强关联项目合并建议”，优先把它当成人工审阅线索，而不是默认接受。
5. 最后跑 `interview_pack`，把结果转成 STAR、项目介绍和面试问答，再由 skill / prompt 做最终口语化或风格整理。

## 接入自己的材料

把上面 Demo 里的 `examples/minimal_input/...` 替换成你自己的 `your_materials/...` 即可。最小输入结构可以参考 [examples/minimal_input](./examples/minimal_input/)：

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

## 输出文件

运行主流程后，通常会得到三组核心结果：

- `reports/audit/`：成果审计、证据、风险提醒、业务背景改写
- `reports/rank/`：按目标 JD 排序后的简历版项目总结，包含 bullet 数控制、可读性复核和可人工审阅的合并候选
- `reports/interview/`：项目介绍、STAR 草稿、面试 Q&A、风险回答；默认提供结构化骨架，最终语气和细化表达建议由 skill / prompt 再处理

如果需要业务文档问答或知识检索，可以额外运行 `doc_knowledge`。

## 致谢与来源

这个仓库基于原项目做了面向“实习简历整理 / 面试复盘”场景的二次开发与定向重构。
感谢原项目开发者提供基础工作流与思路，原始项目：

- [LiuMengxuan04/shushu-internship-tool](https://github.com/LiuMengxuan04/shushu-internship-tool)

## 参与贡献

如果你想改进成果抽取、简历改写、面试表达、测试覆盖或文档内容，建议先阅读 [CONTRIBUTING.md](./CONTRIBUTING.md)，也欢迎直接提交 Issue 或 PR。

## 安全提醒

使用这个项目整理实习经历、项目材料或业务文档时，请优先遵守所在公司或团队的安全规范，不要触碰公司安全红线。

尤其不要上传、提交或公开以下内容：

- 未脱敏的内部业务数据
- 公司内部文档、策略、流程细节
- 含有用户信息、账号信息、密钥、访问凭证的材料
- 任何明确不能对外传播的实习内容
