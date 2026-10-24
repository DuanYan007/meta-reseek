"""Task 3 audit layer: the core criteria in sufficiency_criteria.py are FROZEN.

This module adds (audit-only, does not touch frozen rules):
1. fresh-evidence sets never used in rule development:
   - FRESH_KV: new-query results for the SAME task (frozen patterns apply directly);
   - FRESH_FW: new-task (python web frameworks) docs from unused real results;
2. FRAMEWORKS_POINTS: points drafted from the new task's sub-question TEXT and
   task-spec keywords ONLY, per freeze protocol (recorded before annotating the
   fresh docs; see protocol note in the generated report);
3. deep-mechanism patterns distinguishing 技术名称命中 from 作用机制解释;
4. annotation-sensitivity and coverage-structure analysis helpers.

All annotations here remain CANDIDATE (GLM-drafted, unverified).
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------- fresh KV --
# new queries (2026-10-24, cached under artifacts/cache for offline replay):
#   "why does KV cache use so much VRAM in LLM serving"
#   "key value cache memory reduction methods survey"
FRESH_KV = [
    {"id": "f01", "same_source": None,
     "title": "Understanding the KV Cache: The VRAM Bottleneck of LLM Serving",
     "snippet": ("Why do LLM serving nodes run out of VRAM? Explore the mechanics, "
                 "calculations, and capacity bottlenecks of the Key-Value (KV) Cache."),
     "annotation": {"definition": ("topic_only", "未描述缓存机制本身"),
                    "cost": ("partial", "标题宣称 mechanics/calculations，摘要未见增长关系表述"),
                    "techniques": ("topic_only", "无")}},
    {"id": "f02", "same_source": None,
     "title": "KV Cache: Why Context Length Eats Your VRAM (And How to Fix It)",
     "snippet": ("The KV cache did. The KV cache is the most common source of \"why doesn't "
                 "this fit?\" confusion in local AI. It's invisible in model specs, it doesn't show"),
     "annotation": {"definition": ("topic_only", "无机制描述"),
                    "cost": ("sufficient_support", "标题即直接陈述增长关系（Context Length 吃掉 VRAM）"),
                    "techniques": ("topic_only", "And How to Fix It 仅暗示存在手段，未点名")}},
    {"id": "f03", "same_source": None,
     "title": "KV Cache Optimization Strategies for Scalable and Efficient LLM Inference",
     "snippet": ("Mar 24, 2026 · ABSTRACT The key-value (KV) cache is a foundational "
                 "optimization in Transformer-based large language models, eliminating redunda"),
     "annotation": {"definition": ("partial", "foundational optimization/eliminating redundant 隐含机制"),
                    "cost": ("topic_only", "无占用/增长内容"),
                    "techniques": ("partial", "优化策略综述，但摘要未点名具体技术")}},
    {"id": "f04", "same_source": None,
     "title": "Key, Value, Compress: A Systematic Exploration of KV Cache Compression",
     "snippet": ("Mar 14, 2025 · This paper presents an analysis of various Key-Value (KV) "
                 "cache compression strategies, offering a comprehensive taxonomy that categori"),
     "annotation": {"definition": ("topic_only", "无"),
                    "cost": ("topic_only", "无"),
                    "techniques": ("sufficient_support", "系统化的压缩方法分类研究")}},
    {"id": "f05", "same_source": "f04",
     "title": "Key, Value, Compress: A Systematic Exploration of KV Cache Compression",
     "snippet": ("This paper presents an analysis of various Key-Value (KV) cache compression "
                 "strategies, offering a comprehensive taxonomy that categori"),
     "annotation": None},  # same paper as f04: dedup, not annotated separately
    {"id": "f06", "same_source": None,
     "title": "Rethinking Key-Value Cache Compression Techniques for Large Language Models",
     "snippet": ("The reduction of memory consumption brought by KV cache compression can "
                 "lead to decreased time for the first step. However, for quantization-based met"),
     "annotation": {"definition": ("topic_only", "无"),
                    "cost": ("partial", "占用话题（reduction of memory consumption）但无增长机制"),
                    "techniques": ("sufficient_support", "讨论 quantization-based 压缩方法")}},
]

# ------------------------------------------------------------ fresh new task --
# FRESH_FW: unused REAL search results (novel cache hits, never in cases.json):
#  n09-n13 framework comparisons (positives), n01-n05 architecture-adjacent,
#  n14-n18 biology "ecosystem" pages (cross-domain topic collision for the
#  ecosystem sub-question — the collision trap the frozen protocol should expose).
FRESH_FW = [
    {"id": "n09",
     "title": "Comparison of FastAPI with Django and Flask - GeeksforGeeks",
     "snippet": ("Aug 29, 2025 · In this article, we will compare Django, Flask and FastAPI "
                 "three Python web frameworks. By end, you’ll clearly unde"),
     "annotation": {"performance": ("partial", "三框架对比，但摘要未见性能/异步具体内容"),
                    "use_cases": ("partial", "对比文通常含选型指引，摘要未显式"),
                    "ecosystem": ("topic_only", "无生态内容")}},
    {"id": "n10",
     "title": "FastAPI vs Django vs Flask: A Comprehensive Framework Comparison",
     "snippet": ("Jul 28, 2025 · Compare FastAPI, Django, and Flask Python frameworks. "
                 "Learn which is best for APIs, web apps, and your specific pro"),
     "annotation": {"performance": ("partial", "同上"),
                    "use_cases": ("partial", "which is best for APIs/web apps 即选型指引"),
                    "ecosystem": ("topic_only", "无")}},
    {"id": "n11",
     "title": "Django vs Flask vs FastAPI: 106K vs 13K req/s [2026]",
     "snippet": ("Sep 12, 2026 · This comparison pulls live GitHub data, PyPI release "
                 "records, and independent benchmark results to show exactly whe"),
     "annotation": {"performance": ("sufficient_support", "独立基准数字（req/s）直接回答性能对比"),
                    "use_cases": ("topic_only", "基准数据非选型"),
                    "ecosystem": ("partial", "GitHub/PyPI 数据是生态规模的代理证据，非扩展组件本身")}},
    {"id": "n12",
     "title": "Which Is the Best Python Web Framework: Django, Flask, or FastAPI?",
     "snippet": ("Feb 17, 2026 · Read this blog to find the best Python web framework for "
                 "your project. Compare Django, Flask, and FastAPI – their s"),
     "annotation": {"performance": ("partial", "对比文，摘要无性能/异步 specifics"),
                    "use_cases": ("partial", "best for your project 选型导向"),
                    "ecosystem": ("topic_only", "无")}},
    {"id": "n13",
     "title": "Comparing Python Web Frameworks: Django, Flask, and FastAPI + FastAPI vs Django RES…",
     "snippet": ("Jan 9, 2024 · This table provides a comprehensive comparison of Django, "
                 "Flask, and FastAPI based on various features relevant to w"),
     "annotation": {"performance": ("partial", "特性表对比"),
                    "use_cases": ("partial", "特性对比含适用场景"),
                    "ecosystem": ("partial", "标题含 Django REST（具体组件），正文未见")}},
    {"id": "n01",
     "title": "Monolith vs Microservices Decision Framework 2026",
     "snippet": ("Feb 10, 2026 · Monolith vs Microservices Decision Framework 2026 About the "
                 "Author Nirmalraj R is a Full-Stack Developer at AgileSo"),
     "annotation": {"performance": ("topic_only", "架构决策文，非三框架"),
                    "use_cases": ("topic_only", "microservices 主题相邻但不含三框架选型信息"),
                    "ecosystem": ("irrelevant", "非同域")}},
    {"id": "n02",
     "title": "Microservices vs. Monolith in 2026: A Practical Decision",
     "snippet": ("Feb 14, 2026 · Microservices or monolith? Use this practical decision "
                 "framework based on team size, traffic patterns, and organiza"),
     "annotation": {"performance": ("topic_only", "同 n01"),
                    "use_cases": ("topic_only", "通用架构决策，无框架特定信息"),
                    "ecosystem": ("irrelevant", "非同域")}},
    {"id": "n14",
     "title": "Community Ecology and Ecosystem Ecology - Biology",
     "snippet": ("Ecosystem ecology is an extension of organismal, population, and community "
                 "ecology. The ecosystem is composed of all the biotic compo"),
     "annotation": {"performance": ("irrelevant", "生物学"),
                    "use_cases": ("irrelevant", "生物学"),
                    "ecosystem": ("irrelevant", "生物学 ecosystem——跨域主题碰撞，与框架生态无关")}},
    {"id": "n15",
     "title": "Lesson 3: Comparing Ecosystems",
     "snippet": ("A Limiting Factor is a resource in an ecosystem that is needed for an "
                "organisms' life, and which may be in limited supply, thus ke"),
     "annotation": {"performance": ("irrelevant", "生物学"),
                    "use_cases": ("irrelevant", "生物学"),
                    "ecosystem": ("irrelevant", "跨域主题碰撞")}},
    {"id": "n17",
     "title": "Biomes vs. Ecosystems – Key Differences Explained",
     "snippet": ("The primary difference is scale and scope - biomes are vast regions with "
                "distinct climate and vegetation patterns, while ecosystem"),
     "annotation": {"performance": ("irrelevant", "生物学"),
                    "use_cases": ("irrelevant", "生物学"),
                    "ecosystem": ("irrelevant", "跨域主题碰撞")}},
]

# 新任务必要回答要点：仅依据 python_web_frameworks.yaml 的子问题文本与 keywords 起草
# （冻结协议：先定要点、后标注新证据；两点已知弱点按协议如实保留裸词）
FRAMEWORKS_POINTS = {
    "performance": {
        "P1-性能对比": [r"faster", r"benchmark", r"performance", r"req/s", r"requests per second",
                    r"compar\w+ (django|flask|fastapi)", r"(django|flask|fastapi).{0,30}vs.{0,30}(django|flask|fastapi)"],
        "P2-异步支持": [r"\basync\b", r"asynchron", r"\basgi\b", r"uvicorn", r"concurr"],
    },
    "use_cases": {
        "P1-选型指引": [r"use case", r"choose", r"when to", r"best for", r"suited for",
                    r"which (framework|one)", r"ideal for"],
        "P2-场景类别": [r"microservic", r"prototype", r"full[- ]featured", r"\badmin\b",
                    r"\borm\b", r"\bcms\b", r"\bmvc\b", r"\bapi\b|\bapis\b"],
    },
    "ecosystem": {
        "P1-扩展与包生态": [r"extension", r"plugin", r"package", r"librar", r"ecosystem",
                       r"built[- ]in"],
        "P2-具体组件或社区": [r"sqlalchemy", r"pydantic", r"django rest", r"community",
                        r"documentation", r"\borm\b"],
    },
}

# 技术名称命中 vs 作用机制解释（audit 层，不改变冻结规则）
DEEP_MECHANISM_PATTERNS = [
    r"shar\w+ (key[- ]value |attention |query )?\w*heads",       # GQA/MQA 的机制
    r"pages?\b[^.;]{0,40}blocks",                                  # PagedAttention 的机制
    r"quantiz\w+[^.;]{0,40}(int8|int4|\d[- ]bit)",                 # 量化到低位宽
    r"compress\w+[^.;]{0,40}(states|cache|token)",                 # 压缩缓存状态
    r"grouped[- ]query[^.;]{0,60}share",                           # GQA 显式机制
    r"reduces? (the )?(number of )?(kv |key[- ]value )?heads",
]

deep_re = [re.compile(p, re.IGNORECASE) for p in DEEP_MECHANISM_PATTERNS]


def has_mechanism_explanation(text: str) -> bool:
    return any(p.search(text) for p in deep_re)
