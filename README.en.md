# Shushu Internship Resume Optimizer

This repository is designed for interns who want to turn ongoing internship work into resume-ready and interview-ready material.

Recommended local directory name: `shushu-internship-resume-optimizer`

## What It Does

- audits multi-source internship materials: `code_repo`, `project_summary`, `business_docs`
- merges raw materials into achievement candidates with evidence, business context, metrics, gaps, and risks
- ranks achievements against a target JD and generates resume-style bullets
- flags AI-summary-heavy or potentially overclaimed phrasing that should be checked with the user
- separates long-form project notes from concise resume-facing project summaries
- generates interview assets such as STAR drafts, project intros, Q&A, risk answers, and an application checklist

## Recommended Workflow

`JD + multi-source internship materials -> achievement_audit -> resume_rank -> interview_pack`

Suggested order:

1. Prepare a `sources.json` file with your repo paths, project notes, and business docs.
2. Run `achievement_audit` to inspect extracted achievements and missing evidence.
3. Run `resume_rank` to see which achievements best fit the target role.
4. Run `interview_pack` to convert those results into interview material.

## Commands

### 1. Achievement Audit

```bash
python -m shushu_internship_tool.achievement_audit --sources tests/fixtures/intern_materials/sources.json --out reports/audit --name internship-materials
```

Outputs:

- `achievement_audit.json`
- `overview.md`
- `overview.html`
- `business_context_rewrite.md`

### 2. Resume Ranking

```bash
python -m shushu_internship_tool.resume_rank --jd tests/fixtures/intern_materials/target_jd.txt --achievements reports/audit/achievement_audit.json --target-role backend --out reports/rank
```

Outputs:

- `resume_rank.json`
- `resume_rank.md`
- `resume_project_summary.md`

This step now also provides project-specific follow-up suggestions, such as:

- which metrics are still worth adding
- what evidence or implementation proof is missing
- which AI-sounding or overclaimed statements should be verified

### 3. Business Doc Knowledge Layer

```bash
python -m shushu_internship_tool.doc_knowledge --docs tests/fixtures/intern_materials/business_overview.md --mode basic_rag --query "How does the workflow recover failures?" --out reports/knowledge
```

Supported modes:

- `direct`
- `basic_rag`
- `knowledge_base`

### 4. Interview Pack

```bash
python -m shushu_internship_tool.interview_pack --achievements reports/audit/achievement_audit.json --ranked reports/rank/resume_rank.json --target-role backend --out reports/interview
```

Outputs:

- `interview_pack.json`
- `resume_star.md`
- `project_intro.md`
- `interview_qa.md`
- `risk_answers.md`
- `application_checklist.md`

## Output Guidance

- `business_context_rewrite.md`: better for self-review and interview prep
- `resume_rank.md`: better for ranking, risks, and next-step strengthening
- `resume_project_summary.md`: better for concise resume-facing project descriptions

In practice, it is better to feed the tool a longer project summary, then manually review and compress the result, instead of pasting the long summary directly into a resume.

## Design Principles

- do not fabricate metrics
- make missing evidence explicit
- value business context, not just code
- calibrate writing style to the target role
- explicitly warn about AI-heavy or overclaimed phrasing

## Reference Lineage

This workflow is a focused reorganization of earlier capabilities already present in this repository:

- `repo_audit`
- `candidate_score`

The current primary flow is:

`achievement_audit -> resume_rank -> doc_knowledge -> interview_pack`

Original project repository:

- `https://github.com/LiuMengxuan04/shushu-internship-tool`

## Current Status

This project is still under active development.

At the moment, I have mainly tested part of the workflow with my own internship-related materials, especially the achievement audit, resume ranking, project intro, and interview Q&A flows. Some features, such as the knowledge-layer / knowledge-base related functions, have not been fully tested yet.

My own use cases, edge cases, and optimization ideas are also still limited, so many rules and generation strategies in this repository would benefit from more real materials and broader testing.

Feel free to try it out, test it with your own materials, and share useful suggestions for improving the project. If you have good ideas or feedback, you are welcome to contact me on QQ: `2715745003`

## Contributing

Contributions are welcome.

If you want to improve extraction quality, resume rewriting, interview phrasing, or testing coverage, please read [CONTRIBUTING.md](./CONTRIBUTING.md) first.

## Security Reminder

When using this project with internship materials, project notes, or business documents, please make sure you follow your company's security rules and do not cross any internal compliance or confidentiality red lines.

In particular, do not upload, commit, or publish:

- non-anonymized internal business data
- internal company documents, strategies, or workflow details
- materials containing user data, credentials, keys, or tokens
- any internship content that is explicitly not allowed to be shared externally

If you want to test the project, it is strongly recommended to use sanitized materials or manually rewritten summaries first.
