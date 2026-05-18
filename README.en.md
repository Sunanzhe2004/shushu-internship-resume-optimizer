# Shushu Internship Resume Optimizer

Turn internship code repos, project notes, and business context into resume-ready bullets and interview-ready project narratives.

[简体中文](./README.md) · [English](./README.en.md) · [Contributing](./CONTRIBUTING.md)

## What This Project Is

This repository is for interns and early-career candidates who want to turn ongoing work into clearer application materials.

It is not a one-click resume generator. The main idea is to audit raw materials first, surface evidence and risks, rank what matters for a target JD, and then generate outputs that are easier to verify and rewrite manually.

## Core Capabilities

- audit multi-source internship materials: `code_repo`, `project_summary`, `business_docs`
- merge raw materials into achievement candidates with evidence, business context, metrics, and missing information
- rank achievements against a target JD and generate resume-facing bullet suggestions
- flag AI-heavy, repetitive, potentially overclaimed, or user-check-required phrasing
- separate long-form self-review notes from concise resume-facing project summaries
- generate STAR drafts, project intros, interview Q&A, risk answers, and an application checklist

## Workflow

`JD + multi-source internship materials -> achievement_audit -> resume_rank -> interview_pack`

Suggested order:

1. Prepare a `sources.json` file with repo paths, project notes, and business docs.
2. Run `achievement_audit` to inspect extracted achievements, evidence, and risk flags.
3. Run `resume_rank` to see which achievements best match the target role.
4. Run `interview_pack` to convert the results into interview material.

## Quick Start

```bash
cd shushu-internship-resume-optimizer
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

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

This stage also handles:

- splitting a long project summary into multiple achievement candidates
- extracting metrics, evidence, risks, and missing support
- adding `user_check_flags` for AI-heavy, unclear-boundary, or likely-overclaimed statements
- generating a cleaner business-context rewrite for self-review and interview prep

### 2. Resume Ranking

```bash
python -m shushu_internship_tool.resume_rank --jd tests/fixtures/intern_materials/target_jd.txt --achievements reports/audit/achievement_audit.json --target-role backend --out reports/rank
```

Outputs:

- `resume_rank.json`
- `resume_rank.md`
- `resume_project_summary.md`

This stage also suggests:

- more resume-like bullet wording
- which metrics are most worth adding
- what evidence or implementation detail is still missing
- which lines sound too mechanical, repetitive, or overly AI-generated

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

## Outputs

- `business_context_rewrite.md`: better for self-review and interview framing
- `resume_rank.md`: better for ranking, risks, and next-step strengthening
- `resume_project_summary.md`: better for concise resume-facing project descriptions
- `interview_qa.md`: better for fast interview review

In practice, it is usually better to feed the tool a longer raw project summary, then manually verify and compress the result, instead of pasting the long summary directly into a resume.

## Design Principles

- do not fabricate metrics
- make missing evidence explicit
- value business context, not just code
- calibrate writing style to the target role
- explicitly warn about AI-heavy or overclaimed phrasing
- optimize for material that is usable in applications, interviews, and follow-up questions

## Lineage

This repository is a focused reorganization of earlier capabilities already present in the original workflow, especially:

- `repo_audit`
- `candidate_score`

The current primary flow is:

`achievement_audit -> resume_rank -> doc_knowledge -> interview_pack`

Original project repository:

- `https://github.com/LiuMengxuan04/shushu-internship-tool`

## Current Status

This project is still under active development.

So far, parts of the workflow have been validated with real internship materials, especially the achievement audit, resume ranking, project intro, and interview Q&A flows. Some features, such as the knowledge-layer / knowledge-base related functions, still need broader testing.

Many rules and generation strategies in this repository would benefit from more real materials and broader edge-case coverage. Feel free to try it with your own sanitized materials and share suggestions.

## Contributing

Contributions are welcome.

If you want to improve extraction quality, resume rewriting, interview phrasing, testing coverage, or docs, please read [CONTRIBUTING.md](./CONTRIBUTING.md) first. Issues and PRs are both welcome.

## Security Reminder

When using this project with internship materials, project notes, or business documents, please follow your company's security and confidentiality rules carefully.

In particular, do not upload, commit, or publish:

- non-anonymized internal business data
- internal company documents, strategies, or workflow details
- materials containing user data, credentials, keys, or tokens
- any internship content that is explicitly not allowed to be shared externally

If you want to test the project, it is strongly recommended to use sanitized materials or manually rewritten summaries first.
