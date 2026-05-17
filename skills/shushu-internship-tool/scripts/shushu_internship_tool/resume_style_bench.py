from __future__ import annotations

import re
from typing import Any


STYLE_BENCHMARKS: dict[str, dict[str, Any]] = {
    "backend": {
        "role_keywords": ["backend", "server", "api", "java", "spring", "go", "python", "微服务", "后端"],
        "metric_hints": ["接口成功率", "延迟", "吞吐", "稳定性", "发布效率"],
        "safe_without_metric": "优先写清接口、链路、稳定性改进和协作范围。",
        "risk_phrases": ["全权负责", "独立完成全部", "提升300%"],
    },
    "frontend": {
        "role_keywords": ["frontend", "react", "vue", "ui", "web", "小程序", "前端"],
        "metric_hints": ["首屏耗时", "交互成功率", "错误率", "转化", "页面性能"],
        "safe_without_metric": "优先写页面闭环、状态管理、跨端协作和体验改善。",
        "risk_phrases": ["重写整个前端", "完全主导产品设计"],
    },
    "fullstack": {
        "role_keywords": ["fullstack", "full-stack", "全栈"],
        "metric_hints": ["交付周期", "故障恢复", "运营效率", "用户反馈"],
        "safe_without_metric": "强调跨端闭环和多角色协作，不强行堆系统级指标。",
        "risk_phrases": ["从0到1主导整个平台"],
    },
    "ai": {
        "role_keywords": [
            "ai",
            "ml",
            "algorithm",
            "llm",
            "rag",
            "agent",
            "workflow",
            "prompt",
            "大模型",
            "模型",
            "算法",
            "智能体",
            "应用",
            "大模型应用",
            "大模型应用实习生",
            "llm应用",
            "agent应用",
            "模型应用",
            "ai应用",
        ],
        "metric_hints": ["F1", "Recall", "Precision", "AUC", "准确率", "召回率", "推理延迟", "成本"],
        "safe_without_metric": "没有稳定指标时写实验设计、评估方案、Prompt 策略和上线验证路径。",
        "risk_phrases": ["SOTA", "显著领先所有基线"],
    },
    "data": {
        "role_keywords": ["data", "etl", "warehouse", "spark", "airflow", "数据"],
        "metric_hints": ["时效", "覆盖率", "准确性", "稳定性", "人效"],
        "safe_without_metric": "优先写链路、调度、质量规则和业务支持结果。",
        "risk_phrases": ["打通公司全部数据"],
    },
    "qa": {
        "role_keywords": ["qa", "test", "testing", "测开", "测试"],
        "metric_hints": ["覆盖率", "缺陷率", "回归效率", "稳定性"],
        "safe_without_metric": "突出测试策略、自动化覆盖和缺陷定位能力。",
        "risk_phrases": ["保证零故障"],
    },
    "devops": {
        "role_keywords": ["devops", "sre", "cloud", "k8s", "docker", "运维", "云原生"],
        "metric_hints": ["可用性", "恢复时间", "告警噪音", "成本", "发布效率"],
        "safe_without_metric": "没有线上数字时写部署链路、监控闭环和故障处理流程。",
        "risk_phrases": ["保障100%可用"],
    },
}

DEFAULT_TRACK = "backend"
GENERIC_AI_OPENERS = ("独立设计并实现", "负责设计并实现", "围绕", "面向", "基于")
GENERIC_AI_MARKERS = ("独立设计并实现", "显著提升", "全面优化", "全链路闭环", "高效支撑", "深度参与")


def normalize_role_text(value: str) -> str:
    return value.strip().lower()


def detect_track(target_role: str) -> str:
    normalized = normalize_role_text(target_role)
    scores: list[tuple[int, str]] = []
    for track, benchmark in STYLE_BENCHMARKS.items():
        score = sum(1 for keyword in benchmark["role_keywords"] if keyword.lower() in normalized)
        scores.append((score, track))
    scores.sort(reverse=True)
    if scores and scores[0][0] > 0:
        return scores[0][1]
    return DEFAULT_TRACK


def get_style_benchmark(target_role: str) -> dict[str, Any]:
    track = detect_track(target_role)
    benchmark = dict(STYLE_BENCHMARKS[track])
    benchmark["track"] = track
    return benchmark


def evaluate_risk_phrases(text: str, benchmark: dict[str, Any]) -> list[str]:
    lowered = text.lower()
    hits = []
    for phrase in benchmark.get("risk_phrases", []):
        if phrase.lower() in lowered:
            hits.append(phrase)
    if re.search(r"\b\d{3,}%\b", text):
        hits.append("超大幅度提升")
    return hits


def detect_generated_style_issues(bullets: list[str]) -> list[str]:
    issues: list[str] = []
    clean_bullets = [" ".join(str(bullet).split()) for bullet in bullets if str(bullet).strip()]
    if not clean_bullets:
        return issues

    opener_counts: dict[str, int] = {}
    for bullet in clean_bullets:
        for opener in GENERIC_AI_OPENERS:
            if bullet.startswith(opener):
                opener_counts[opener] = opener_counts.get(opener, 0) + 1

    repeated_openers = [opener for opener, count in opener_counts.items() if count >= 2]
    if repeated_openers:
        issues.append(f"生成结果存在机械重复开头：{' / '.join(repeated_openers)}")

    generic_hits = set()
    for bullet in clean_bullets:
        for marker in GENERIC_AI_MARKERS:
            if marker in bullet:
                generic_hits.add(marker)
    if len(generic_hits) >= 2:
        issues.append(f"生成结果 AI 味较重，模板化表述偏多：{' / '.join(sorted(generic_hits))}")

    if len(set(clean_bullets)) < len(clean_bullets):
        issues.append("生成结果存在重复或近重复 bullet，建议人工合并和改写")

    return issues
