# GUI Agent Evaluation Workflow

## One-line positioning

Built a lightweight evaluation workflow for a screen-based GUI Agent, aimed at judging task completion quality and organizing agent trajectories into reusable review material.

## Background

When an interactive GUI Agent executes user instructions, each run can generate screenshots, action traces, and intermediate states.

If these trajectories are reviewed entirely by hand, the process becomes slow, inconsistent, and hard to scale as data volume grows.

## Core work

### 1. Task-success evaluation design

- Defined a review workflow for deciding whether a GUI Agent task was actually completed instead of only checking whether a trajectory ended.
- Focused on structured review criteria so screenshots, action traces, and intermediate states could be judged in a more consistent way.
- This part is best explained as evaluation-logic design rather than benchmark optimization.

### 2. Invalid-sample filtering

- Added filtering logic so obvious collection or environment issues could be separated from genuine agent failures.
- Treated invalid samples as a different class from true task failures, which makes later review and reporting easier to explain.
- This part is best explained through rule design, failure boundaries, and example cases.

### 3. Output and review material generation

- Organized outputs into markdown and JSON reports so evaluation results could be reused as project notes, resume bullets, and interview-prep material.
- Kept the workflow focused on evidence collection, missing-information reminders, and user-check-required phrasing.
- This part is best explained through output structure and downstream usability rather than performance numbers.

## Metrics status

- This public example is intentionally metric-light and focuses on workflow structure rather than proprietary or sensitive results.
- Safer resume phrasing should stay close to what can be verified: evaluation logic, rule design, filtering strategy, and reporting workflow.

## Caution

- If this example is reused for resume writing, the user should still confirm ownership, implementation depth, and any claimed results before treating it as a personal project description.
