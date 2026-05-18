# Contributing

Thanks for your interest in improving `shushu-internship-resume-optimizer`.

This project is still evolving, and feedback based on real internship materials is especially valuable.

## Before You Start

- Read [README.md](./README.md) or [README.en.md](./README.en.md) for the current workflow and scope.
- Make sure you do **not** commit personal internship materials, private resumes, company-sensitive docs, or generated outputs from private data.
- Please double-check any local notes, generated reports, or temporary evaluation folders before committing.

## Local Setup

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Run Tests

```bash
pytest
```

Please run the test suite before opening a PR.

## What Kind of Contributions Help Most

- better achievement extraction and grouping logic
- less mechanical resume / interview phrasing
- stronger AI-heavy / overclaim-heavy wording detection
- better support for real internship materials
- broader testing for `doc_knowledge` and other less-tested features
- documentation improvements and clearer examples

## Issue Suggestions

When opening an issue, it helps a lot if you include:

- what input material type you used
- what output felt wrong
- what you expected instead
- whether the issue is about extraction, ranking, rewriting, or interview prep

If possible, replace private content with anonymized examples.

## Pull Request Notes

- Keep changes scoped and explain the user-facing impact clearly.
- Add or update tests when behavior changes.
- Avoid committing generated files from private evaluation runs.
- If your change affects public-facing output format, mention it in the PR summary.

## Privacy Reminder

This repository is intended to be open source.

Please do not commit:

- personal resumes
- real company-internal documents
- raw internship notes containing sensitive information
- generated reports derived from private materials

Thanks for helping make the project more practical and more reliable.
