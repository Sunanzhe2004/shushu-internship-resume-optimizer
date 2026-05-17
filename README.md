# Shushu 实习简历优化工具

`shushu-internship-resume-optimizer` 面向正在实习、希望把当前工作整理成可投递简历内容和可面试表达材料的用户。

它保留了 `AI 工作流 + 本地脚本` 的使用方式，但主线已经从“找项目 / 看仓库”切换为“从多源实习材料中反推成果、压缩简历写法、补足面试素材”。

## 能做什么

- 审计多源实习材料：代码仓库、项目总结、业务背景文档
- 从材料中归并成果项，提取证据、业务背景、技术栈、指标、缺失信息
- 根据目标 JD 对成果排序，生成更适合写进简历的 bullet
- 识别 AI 总结味重、措辞可能夸大、需要和本人经历核对的表述
- 把偏长的项目总结拆成“自己复盘版”和“简历精简版”两个输出层
- 生成业务背景改写、STAR 草稿、项目介绍、追问题和投递前检查清单
- 为业务文档提供 `direct / basic_rag / knowledge_base` 三种知识层模式

## 推荐工作流

`JD + 多源实习材料 -> achievement_audit -> resume_rank -> interview_pack`

支持的材料类型：

- `code_repo`
- `project_summary`
- `business_docs`

更推荐的使用方式是：

1. 先把自己的项目总结、业务介绍、代码仓库路径整理到 `sources.json`
2. 先跑 `achievement_audit`，看成果抽取得是否合理、哪些地方缺证据
3. 再跑 `resume_rank`，看哪些成果最适合投目标岗位
4. 最后跑 `interview_pack`，把简历表述转成 STAR 和面试问答

## 安装

```bash
cd shushu-internship-resume-optimizer
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

如果你本地已有 Python 环境，也可以直接用自己的解释器运行。这个仓库最近测试使用的是 `pytorch_learn` 环境。

## 命令

### 1. 成果审计

```bash
python -m shushu_internship_tool.achievement_audit --sources tests/fixtures/intern_materials/sources.json --out reports/audit --name internship-materials
```

或使用命令行入口：

```bash
shushu-achievement-audit --sources tests/fixtures/intern_materials/sources.json --out reports/audit --name internship-materials
```

输出：

- `achievement_audit.json`
- `overview.md`
- `overview.html`
- `business_context_rewrite.md`

这里会额外做几件事：

- 尝试把长项目总结拆成多个成果项
- 自动提取可用指标、风险点、待补证据
- 标记 `user_check_flags`，提示哪些表述 AI 味较重或可能夸大
- 生成一版更适合自己复盘和面试解释的业务背景改写

### 2. 简历成果排序

```bash
python -m shushu_internship_tool.resume_rank --jd tests/fixtures/intern_materials/target_jd.txt --achievements reports/audit/achievement_audit.json --target-role 后端开发 --out reports/rank
```

输出：

- `resume_rank.json`
- `resume_rank.md`
- `resume_project_summary.md`

这一层除了排序，还会：

- 给出更像简历 bullet 的推荐写法
- 生成“下一步补强”，提示当前项目最值得补哪些数字、证据、边界说明
- 把“长版项目总结”和“简历可直接使用版”拆开

其中：

- `resume_rank.md` 更适合看排序、风险、补强建议
- `resume_project_summary.md` 更适合作为正式简历项目描述的压缩稿

### 3. 业务文档知识层

```bash
python -m shushu_internship_tool.doc_knowledge --docs tests/fixtures/intern_materials/business_overview.md --mode basic_rag --query "异常补偿和状态一致性怎么做" --out reports/knowledge
```

支持模式：

- `direct`
- `basic_rag`
- `knowledge_base`

### 4. 面试包

```bash
python -m shushu_internship_tool.interview_pack --achievements reports/audit/achievement_audit.json --ranked reports/rank/resume_rank.json --target-role 后端开发 --out reports/interview
```

输出：

- `interview_pack.json`
- `resume_star.md`
- `project_intro.md`
- `interview_qa.md`
- `risk_answers.md`
- `application_checklist.md`

## sources.json 示例

```json
{
  "sources": [
    {
      "source_type": "code_repo",
      "title": "ticket-service",
      "path_or_text": "/path/to/repo"
    },
    {
      "source_type": "project_summary",
      "title": "weekly-summary",
      "path_or_text": "/path/to/summary.md"
    },
    {
      "source_type": "business_docs",
      "title": "business-overview",
      "path_or_text": "/path/to/business.md",
      "knowledge_mode": "basic_rag"
    }
  ]
}
```

## 输出文件怎么用

- `business_context_rewrite.md`：适合自己整理业务背景、准备“这个项目为什么值得做”
- `resume_rank.md`：适合判断当前哪条成果最值得写进简历
- `resume_project_summary.md`：适合直接当作简历项目段落的初稿
- `interview_qa.md`：适合面试前快速复习

建议不要把长版项目总结直接贴进简历，而是：

1. 用长版材料喂工具
2. 用 `resume_project_summary.md` 做压缩版
3. 再手动确认数字、边界、职责范围

## 设计原则

- 不编造数字，没有稳定指标就明确标注“待补量化 / 待补证据”
- 不只看代码，也重视业务背景和上下游流程
- 简历风格按岗位方向校准，而不是只生成一套通用话术
- 对 AI 总结味重、可能夸大的表述做显式提醒，而不是默认当真
- 优先产出“可投、可面、可讲”的内容，而不是堆很多模板

## 参考与改造来源

这个项目不是从零另起的一套工具，而是在当前仓库原有工作流基础上做的定向重构，主要参考和延续了两条旧能力链路：

- `repo_audit`：原先偏向项目审视 / 仓库扫描的入口
- `candidate_score`：原先偏向候选材料打分的入口

这次改造是在保留兼容命令的前提下，把主流程重新整理为：

`achievement_audit -> resume_rank -> doc_knowledge -> interview_pack`

README 里提到的“参考项目”主要就是本仓库此前已有的 `repo_audit / candidate_score` 工作流及其兼容入口，而不是额外引用了一个已确认的外部上游仓库。

原始项目仓库链接：

- `https://github.com/LiuMengxuan04/shushu-internship-tool`

## 当前状态

目前项目仍然在持续开发中。

当前本人主要使用了自己的实习相关数据测试了部分功能，像成果审计、简历排序、项目介绍、面试问答这一类链路已经做过多轮本地验证；知识库等功能目前还没有经过充分测试。

另外，个人目前能想到的使用场景、边界问题和优化方向也比较有限，仓库里很多规则和生成逻辑仍然需要更多真实材料来打磨。

欢迎大家体验测试，并提出更多有用的建议来一起优化这个项目。如果你有好的建议，欢迎添加 QQ：`2715745003`

## 参与贡献

欢迎大家一起完善这个项目。

如果你想改进成果抽取、简历改写、面试表述、测试覆盖或文档内容，建议先阅读 [CONTRIBUTING.md](./CONTRIBUTING.md)。

## 安全提醒

在使用这个项目整理实习经历、项目材料或业务文档时，请务必优先遵守所在公司或团队的安全规范，不要触碰公司安全红线。

尤其不要上传、提交或公开以下内容：

- 未脱敏的内部业务数据
- 公司内部文档、策略、流程细节
- 含有用户信息、账号信息、接口密钥、访问凭证的材料
- 任何明确不能对外传播的实习内容

如果你希望体验测试，建议优先使用脱敏后的示例材料，或自己手动改写后的项目摘要。

## 兼容性

为了降低迁移成本，旧命令仍然保留为兼容别名：

- `shushu-repo-audit` -> `achievement_audit`
- `shushu-candidate-score` -> `resume_rank`

## 开发

```bash
pytest
```
