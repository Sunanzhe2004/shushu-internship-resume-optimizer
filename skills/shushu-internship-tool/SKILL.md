---
name: shushu-internship-tool
description: "Use when an AI assistant helps users turn ongoing internship work into resume-ready and interview-ready material from code repos, project summaries, and business documents."
---

# Shushu Internship Tool
Default output is Chinese, while preserving English technical terms, commands, and repository names.

## Goal

Turn messy internship materials into:
- resume-ready achievements
- JD-oriented resume bullets
- evidence-backed project summaries
- business-context explanations
- interview-ready STAR and Q&A material

## Core Principle

Prefer `skill`-level reusable methodology over user-specific hard scripts.

This means:
- use model understanding first for project grouping, contribution extraction, value judgment, and title generation
- use scripts for stable work only: file loading, normalization, schema validation, deduplication, ranking, formatting, and output writing
- treat fixture materials as regression checks, not as the source of domain rules
- avoid growing keyword-to-title maps as the main extraction strategy
- if a rule is added, it should express a broad pattern such as structure, causality, evidence quality, or value filtering

## Preferred Workflow

### 1. Gather Inputs

Prefer collecting:
- target JD
- target role direction
- current internship scope
- available materials: `code_repo` / `project_summary` / `business_docs` / PR / notes / retrospectives
- known metrics or business outcomes
- confidentiality constraints

### 2. Normalize Into `sources.json`

Supported source types:
- `code_repo`
- `project_summary`
- `business_docs`

When possible, prefer adding model-structured extraction to textual sources via:
- `structured_extract_path`
- `structured_extract`

This is preferred over forcing long free-form notes through brittle fallback parsing.

### 3. Achievement Audit

Run:

```bash
python -m shushu_internship_tool.achievement_audit --sources sources.json --out reports/audit
```

Focus on:
- whether project blocks are split correctly
- whether each achievement has real business context
- whether value comes from outcomes rather than workload counts
- whether user-check flags expose weak claims, AI-ish wording, or missing evidence

### 4. Resume Ranking

Run:

```bash
python -m shushu_internship_tool.resume_rank --jd jd.txt --achievements reports/audit/achievement_audit.json --target-role backend --out reports/rank
```

Focus on:
- which achievements are worth keeping for the target role
- which bullets should stay separate vs. merge
- whether bullet ordering follows causal flow: setup -> mechanism -> result
- choose bullet density by project count instead of defaulting to a fixed 3 to 4 bullets
- if the user says the project is only one part of their work, merge same-mainline bullets first; but if the material is one complete project, 4 to 5 bullets can still be reasonable
- review the final resume summary for scanability before presenting it: repeated openings, overlong bullets, and over-splitting should be fixed first
- scripts may suggest merge candidates, but only the skill / prompt layer should decide whether two bullets or modules actually belong in one resume line

### 5. Interview Pack

Run:

```bash
python -m shushu_internship_tool.interview_pack --project-notes reports/rank/resume_rank.json --target-role backend --out reports/interview
```

Focus on:
- whether the one-minute intro sounds spoken rather than templated
- whether STAR is traceable back to evidence
- whether business follow-up questions can be answered cleanly

## Model-First Extraction Guidance

For semantic tasks, prefer model output in structured form.

Recommended model responsibilities:
- split raw materials into projects
- decide whether two modules belong to one project
- extract `background / task / actions / outcome / business_value`
- identify whether a bullet is worth keeping
- suggest merge candidates
- generate merged wording only after the prompt layer has decided that a merge is actually appropriate
- rewrite titles into concise, resume-usable wording
- make the final semantic judgment on whether similar-looking work should stay split because project boundary, audience, deliverable, or ownership is different

Recommended script responsibilities:
- accept structured extraction
- normalize fields into downstream schema
- attach evidence and warnings
- rank and format outputs
- provide fallback parsing only when structured extraction is absent
- enforce light guardrails such as bullet-count caps, scanability reminders, and readability review
- never hard-code semantic merge decisions that depend on project boundary understanding
- avoid role-track-specific writing templates when a generic structured summary is enough

See:
- [model-first-extraction.md](./references/model-first-extraction.md)

## Anti-Patterns

Avoid these unless there is no better option:
- adding project-specific keyword tables derived from one user's materials
- treating one fixture file as the canonical project structure
- using file counts, reading volume, or review volume as achievements without value linkage
- collapsing business background and achievements into a single bullet
- using fallback parsing output as if it were model-quality understanding

## Output Style

- optimize for reusable, editable outputs rather than flashy one-shot writing
- never fabricate metrics
- prefer evidence, action, outcome, and business value over buzzwords
- keep uncertainty explicit when evidence is incomplete
- prefer fewer, denser bullets over many thin bullets when several points belong to the same project mainline
- default compression strategy:
  - 1 project: 4 to 5 bullets is acceptable when the project is complete and each bullet carries a distinct main point
  - 2 projects: 2 to 3 bullets per project is usually reasonable
  - 3+ projects: usually 1 to 2 bullets per project in the resume-facing summary
- before returning the final artifact, do a readability review:
  - can a recruiter scan it in a few seconds
  - are same-project bullets repetitive enough to merge
  - is any bullet carrying background, action, and result in a bloated way
- if project boundary is ambiguous, stay conservative in the final artifact: keep modules split first, then let the prompt explain possible merge options
