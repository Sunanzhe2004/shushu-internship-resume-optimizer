# Model-First Extraction

## Purpose

This reference defines the preferred extraction direction for `shushu-internship-tool`:
- model-first for semantics
- script-second for normalization and delivery

It exists to prevent the workflow from drifting toward sample-specific hardcoding.

## Design Rules

### 1. Prefer Semantics Over Keyword Maps

Use the model to decide:
- what the project is
- what the core contribution is
- whether a statement is background, action, result, or value
- whether two bullets should merge

Keyword rules can still exist, but only as:
- alias cleanup
- structural fallback
- weak heuristic backup

They should not be the primary source of meaning.

### 2. Prefer Structure Over Phrase Matching

When parsing raw material, prioritize:
- explicit project blocks
- section headings
- numbered bullets
- causal ordering
- evidence-bearing sentences

Only after structural cues fail should fallback heuristics run.

### 3. Keep Value Filtering Separate

A sentence is not worth keeping just because it has a number.

Keep only content that shows:
- impact
- improved accuracy or stability
- reduced cost or invalid work
- better observability or recoverability
- meaningful business or engineering value

Do not preserve workload counts alone, such as:
- read N files
- scanned N repos
- reviewed N documents

unless they clearly connect to a useful result.

### 4. Treat Fixtures As Regression, Not Ground Truth

Fixture files should answer:
- did we break a supported behavior?

They should not answer:
- what the product logic should be for all future users?

## Recommended Structured Schema

The preferred model output format is:

```json
{
  "projects": [
    {
      "title": "AutoEval 自动评估系统",
      "business_context": "面向 GUI Agent 评测流程，减少人工审核成本。",
      "highlights": [
        {
          "title": "无效数据过滤链路",
          "task": "搭建前置过滤链路识别异常样本",
          "actions": [
            "补充规则拦截截图缺失和环境异常样本",
            "将无效样本与失败样本拆开归因"
          ],
          "outcome": "将无效数据误判为成功的比例从 11.6% 降至 0%",
          "metrics": ["11.6% -> 0%"],
          "business_value": "减少错误样本进入下游训练和分析链路",
          "evidence": ["badcase record", "eval log"],
          "keep_for_resume": true,
          "user_check_flags": ["指标口径需本人确认"]
        }
      ]
    }
  ]
}
```

Current normalization code accepts:
- `projects[].highlights`
- `projects[].contributions`
- `projects[].achievements`
- top-level `achievements`

## Integration Rule

When structured extraction is present:
- `achievement_audit` should trust it first
- fallback parsing should not override it

When structured extraction is absent:
- fallback parsing may run
- but it should stay broad, structural, and conservative

## Review Checklist

Before adding a new script rule, ask:
1. Is this solving a broad pattern or one sample's wording?
2. Could this decision be made better by model output instead?
3. Is the rule about structure/value/evidence rather than one project name?
4. If a different user's project used different nouns, would this still help?

If the answer is mostly no, it should not become a core rule.
