---
name: shushu-internship-tool
description: "Use when an AI assistant helps users turn ongoing internship work into resume-ready and interview-ready material from code repos, project summaries, and business documents."
---

# Shushu 实习材料整理工作流

默认输出中文，保留英文技术术语、命令和仓库名。

## 目标

把用户当前实习里的零散材料整理成：

- 可写进简历的成果项
- 面向 JD 的简历 bullet 改写
- 可追溯证据
- 业务背景说明
- 面试讲述包

## 输入信息

优先收集：

- 目标 JD
- 目标岗位方向
- 当前实习做了什么
- 可以提供哪些材料：代码库 / 周报总结 / 业务文档 / PR / 复盘
- 是否有量化指标
- 是否受保密限制

## Workflow

### 1. 多源材料整理

把材料整理成 `sources.json`，支持：

- `code_repo`
- `project_summary`
- `business_docs`

### 2. 成果审计

运行：

```bash
python -m shushu_internship_tool.achievement_audit --sources sources.json --out reports/audit
```

关注输出：

- `achievement_audit.json`
- `overview.md`
- `overview.html`

重点确认：

- 成果项是否合并合理
- 是否提到了业务背景
- 是否缺少量化和证据

### 3. 简历排序与写法

运行：

```bash
python -m shushu_internship_tool.resume_rank --jd jd.txt --achievements reports/audit/achievement_audit.json --target-role 后端开发 --out reports/rank
```

重点确认：

- 哪些成果适合写进简历
- 哪些成果证据不足
- 哪些写法更适合当前岗位方向

### 4. 业务文档知识层

如果用户有业务介绍文档，运行：

```bash
python -m shushu_internship_tool.doc_knowledge --docs business.md --mode basic_rag --query "这个流程为什么要做异常补偿" --out reports/knowledge
```

模式选择：

- `direct`：文档很少
- `basic_rag`：文档适中，默认推荐
- `knowledge_base`：文档很多，想长期沉淀

### 5. 面试包

运行：

```bash
python -m shushu_internship_tool.interview_pack --project-notes reports/rank/resume_rank.json --target-role 后端开发 --out reports/interview
```

重点确认：

- STAR 是否能讲顺
- 1 分钟介绍是否自然
- 业务追问是否能落回证据
- 指标口径是否稳妥

## 输出风格

- 优先产出可直接投递、可继续手改的内容
- 没有稳定指标时，不编造数字
- 对不同岗位方向使用不同表达风格
- 少写空泛 buzzword，多写职责、动作、结果、证据和业务价值
