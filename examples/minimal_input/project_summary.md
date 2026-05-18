# Mobile GUI Agent Evaluation Workflow

## One-line positioning

Built a lightweight workflow to review mobile GUI Agent trajectories and turn raw evaluation work into reusable labeling rules and interview-ready project material.

## Background

The team needed a more stable way to judge whether a mobile GUI Agent completed a task successfully and why failed cases should be tagged.

Manual review was slow, inconsistent, and hard to scale when trajectory volume increased.

## What I worked on

- Improved task-success judgment quality through prompt iteration and invalid-sample handling rules.
- Organized failed cases into first-level and second-level error categories for later analysis.
- Added report outputs so the workflow could be reviewed as resume bullets and interview notes instead of scattered raw notes.

## Evidence I can explain

- Wrote rule logic for filtering clearly invalid samples before deeper review.
- Iterated on evaluation prompts and edge-case handling for search, sort, and form-like tasks.
- Collected example failure patterns and grouped them into reusable error-label buckets.
- Produced markdown and JSON outputs that make follow-up review easier.

## Metrics status

- Stable online metrics are not ready yet.
- What can be verified now: workflow scope, rule design, prompt iteration, and labeling structure.

## Caution

- Some phrases in earlier drafts were written by AI and should be checked against actual ownership, metrics, and implementation details before putting them into a resume.
