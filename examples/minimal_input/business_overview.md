# Business Overview

## Team context

The team works on mobile GUI Agent data and evaluation workflows.

## Current workflow

The evaluation pipeline focuses on two linked goals:

1. decide whether a task was completed successfully
2. assign failure labels to unsuccessful cases

## Why this matters

If the evaluation result is unstable, downstream model comparison and data iteration become noisy.

If the failure-label system is vague, it is hard to learn what to fix in prompts, action design, or data collection.

## What usually needs follow-up evidence

- how invalid data is defined
- which failure labels are used most often
- how prompt changes affect precision or recall
- whether the workflow reduces manual review cost
