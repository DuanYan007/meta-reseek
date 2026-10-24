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
# 采集与溯源（2026-10-24）：经项目搜索缓存（artifacts/cache）真实抓取，cache_key 可回放核查。
#   query A: "why does KV cache use so much VRAM in LLM serving"  -> cache_key a9dfdc010fa5...
#   query B: "key value cache memory reduction methods survey"   -> cache_key 31406b1933a...
# 同源核查（PR #8 整改①）：f03 与旧案例 e011 为同一论文（arXiv 2603.20397 的 pdf/html 双版本，
#   e012 的 pdf URL 因先前同源去重已不在案例集，致 URL 过滤未拦住）；f05 与 f04 为同一论文的
#   ResearchGate/IEEE 双门户版本。同源或宣称级证据不计为独立新证据。
FRESH_KV = [
    {"id": "f01", "same_source": None, "same_source_with_old": None,
     "url": "https://www.narenvadapalli.com/blog/understanding-kv-cache/",
     "query": "why does KV cache use so much VRAM in LLM serving",
     "cache_key": "a9dfdc010fa50a694fbd6be062d1d61daf7292a9", "verifiable": True,
     "title": "Understanding the KV Cache: The VRAM Bottleneck of LLM Serving",
     "snippet": ("Why do LLM serving nodes run out of VRAM? Explore the mechanics, "
                 "calculations, and capacity bottlenecks of the Key-Value (KV) Cache."),
     "annotation": {"definition": ("topic_only", "未描述缓存机制本身（宣称 explore the mechanics）"),
                    "cost": ("partial", "标题宣称 mechanics/calculations，摘要未见增长关系表述",
                             "不确定：宣称会解释而摘要未实际给出解释，全文可能充分（整改②口径）"),
                    "techniques": ("topic_only", "无")}},
    {"id": "f02", "same_source": None, "same_source_with_old": None,
     "url": "https://insiderllm.com/guides/kv-cache-optimization-guide/",
     "query": "why does KV cache use so much VRAM in LLM serving",
     "cache_key": "a9dfdc010fa50a694fbd6be062d1d61daf7292a9", "verifiable": True,
     "title": "KV Cache: Why Context Length Eats Your VRAM (And How to Fix It)",
     "snippet": ("The KV cache did. The KV cache is the most common source of \"why doesn't "
                 "this fit?\" confusion in local AI. It's invisible in model specs, it doesn't show"),
     "annotation": {"definition": ("topic_only", "无机制描述"),
                    "cost": ("partial", "标题直接陈述驱动因素（context length 吃掉 VRAM），但摘要未展开机制",
                             "不确定：标题属断言级回答；按『宣称 vs 实际给出』口径由 sufficient_support 下调为 partial，全文若含机制则应恢复（整改②修订）"),
                    "techniques": ("topic_only", "And How to Fix It 仅暗示存在手段，未点名")}},
    {"id": "f03",  # 整改①排除：与旧案例 e011 同一论文（arXiv 2603.20397 html/pdf 双版本）
     "same_source": None, "same_source_with_old": "e011 (arXiv 2603.20397)",
     "url": "https://arxiv.org/pdf/2603.20397",
     "query": "key value cache memory reduction methods survey",
     "cache_key": "31406b1933aace66167eb133984f2b5e1125eb4f", "verifiable": True,
     "title": "KV Cache Optimization Strategies for Scalable and Efficient LLM Inference",
     "snippet": ("Mar 24, 2026 · ABSTRACT The key-value (KV) cache is a foundational "
                 "optimization in Transformer-based large language models, eliminating redunda"),
     "annotation": None},  # 与旧案例同源：不计为独立新证据，仅留溯源记录
    {"id": "f04", "same_source": None, "same_source_with_old": None,
     "url": "https://www.researchgate.net/publication/389917099_Key_Value_Compress_A_Systematic_Exploration_",
     "query": "key value cache memory reduction methods survey",
     "cache_key": "31406b1933aace66167eb133984f2b5e1125eb4f", "verifiable": True,
     "title": "Key, Value, Compress: A Systematic Exploration of KV Cache Compression",
     "snippet": ("Mar 14, 2025 · This paper presents an analysis of various Key-Value (KV) "
                 "cache compression strategies, offering a comprehensive taxonomy that categori"),
     "annotation": {"definition": ("topic_only", "无"),
                    "cost": ("topic_only", "无"),
                    "techniques": ("partial", "宣称系统分析/分类各种压缩策略，但摘要未点名任何具体技术",
                                   "不确定：按『宣称 vs 实际给出』口径由 sufficient_support 下调为 partial；正文含具体方法清单时显然应恢复（整改②修订）")}},
    {"id": "f05",  # 与 f04 同一论文（ResearchGate vs IEEE 双门户），去重不计独立证据
     "same_source": "f04 (IEEE 门户: ieeexplore.ieee.org/document/10983416)",
     "same_source_with_old": None,
     "url": "https://ieeexplore.ieee.org/document/10983416",
     "query": "key value cache memory reduction methods survey",
     "cache_key": "31406b1933aace66167eb133984f2b5e1125eb4f", "verifiable": True,
     "title": "Key, Value, Compress: A Systematic Exploration of KV Cache Compression",
     "snippet": ("This paper presents an analysis of various Key-Value (KV) cache compression "
                 "strategies, offering a comprehensive taxonomy that categori"),
     "annotation": None},
    {"id": "f06", "same_source": None, "same_source_with_old": None,
     "url": "https://openreview.net/pdf?id=ou0AsNbXVG",
     "query": "key value cache memory reduction methods survey",
     "cache_key": "31406b1933aace66167eb133984f2b5e1125eb4f", "verifiable": True,
     "title": "Rethinking Key-Value Cache Compression Techniques for Large Language Models",
     "snippet": ("The reduction of memory consumption brought by KV cache compression can "
                 "lead to decreased time for the first step. However, for quantization-based met"),
     "annotation": {"definition": ("topic_only", "无"),
                    "cost": ("partial", "占用话题（reduction of memory consumption）但无增长机制"),
                    "techniques": ("sufficient_support", "点名 quantization-based 方法并陈述其实际效果")}},
]

FRESH_KV_REVISION_LOG = [
    {"item": "f03", "change": "从独立新证据中排除，改记溯源条目",
     "basis": "整改①专项核查：URL arxiv.org/pdf/2603.20397 与旧案例 e011（html/2603.20397v1）为同一论文；e012 的 pdf URL 因先前同源去重不在案例集，URL 过滤未拦住"},
    {"item": "f05", "change": "标注改为 None（同源去重）",
     "basis": "与 f04 为同一论文 ResearchGate/IEEE 双门户，此前已按 same_source 处理，本轮补全 URL 溯源"},
    {"item": "f02->cost", "change": "sufficient_support → partial（附不确定）",
     "basis": "整改②口径：标题为断言级驱动因素陈述，摘要未实际给出解释；全文未核查"},
    {"item": "f04->techniques", "change": "sufficient_support → partial（附不确定）",
     "basis": "整改②口径：宣称系统分析/分类，摘要未点名具体技术；全文未核查"},
    {"item": "f01->cost", "change": "维持 partial，补不确定说明",
     "basis": "同为宣称级（Explore the mechanics），与 f02 同口径"},
]

# ------------------------------------------------------------ fresh new task --
# FRESH_FW: unused REAL search results — python_web_frameworks 任务原始查询在
# artifacts/cache 中的未用命中（从未进入 cases.json）；URL 经标题反查恢复，可回放核查。
#  n09-n13 框架对比（正例），n01/n02 架构邻域文，n14/n15/n17 生物学 "ecosystem" 页面
#  （ecosystem 子问题的跨域主题碰撞陷阱）。
# 口径（整改③）：本组为**冻结方法的探索性跨任务审计**——新任务要点虽仅依据任务文件
# 子问题文本起草，但要点与标注落于同一提交，无可核查的事前登记证据，
# 不称为严格预登记验证。
FRESH_FW = [
    {"id": "n09",
     "url": "https://www.geeksforgeeks.org/python/comparison-of-fastapi-with-django-and-flask/",
     "title": "Comparison of FastAPI with Django and Flask - GeeksforGeeks",
     "snippet": ("Aug 29, 2025 · In this article, we will compare Django, Flask and FastAPI "
                 "three Python web frameworks. By end, you’ll clearly unde"),
     "annotation": {"performance": ("partial", "三框架对比，但摘要未见性能/异步具体内容"),
                    "use_cases": ("partial", "对比文通常含选型指引，摘要未显式"),
                    "ecosystem": ("topic_only", "无生态内容")}},
    {"id": "n10",
     "url": "https://betterstack.com/community/guides/scaling-nodejs/fastapi-vs-django-vs-flask/",
     "title": "FastAPI vs Django vs Flask: A Comprehensive Framework Comparison",
     "snippet": ("Jul 28, 2025 · Compare FastAPI, Django, and Flask Python frameworks. "
                 "Learn which is best for APIs, web apps, and your specific pro"),
     "annotation": {"performance": ("partial", "同上"),
                    "use_cases": ("partial", "which is best for APIs/web apps 即选型指引"),
                    "ecosystem": ("topic_only", "无")}},
    {"id": "n11",
     "url": "https://tech-insider.org/django-vs-flask-vs-fastapi-2026/",
     "title": "Django vs Flask vs FastAPI: 106K vs 13K req/s [2026]",
     "snippet": ("Sep 12, 2026 · This comparison pulls live GitHub data, PyPI release "
                 "records, and independent benchmark results to show exactly whe"),
     "annotation": {"performance": ("sufficient_support", "独立基准数字（req/s）直接回答性能对比"),
                    "use_cases": ("topic_only", "基准数据非选型"),
                    "ecosystem": ("partial", "GitHub/PyPI 数据是生态规模的代理证据，非扩展组件本身")}},
    {"id": "n12",
     "url": "https://blog.jetbrains.com/pycharm/2025/02/django-flask-fastapi/",
     "title": "Which Is the Best Python Web Framework: Django, Flask, or FastAPI?",
     "snippet": ("Feb 17, 2026 · Read this blog to find the best Python web framework for "
                 "your project. Compare Django, Flask, and FastAPI – their s"),
     "annotation": {"performance": ("partial", "对比文，摘要无性能/异步 specifics"),
                    "use_cases": ("partial", "best for your project 选型导向"),
                    "ecosystem": ("topic_only", "无")}},
    {"id": "n13",
     "url": "https://www.capitalnumbers.com/blog/django-vs-flask-vs-fastapi",
     "title": "Comparing Python Web Frameworks: Django, Flask, and FastAPI + FastAPI vs Django RES…",
     "snippet": ("Jan 9, 2024 · This table provides a comprehensive comparison of Django, "
                 "Flask, and FastAPI based on various features relevant to w"),
     "annotation": {"performance": ("partial", "特性表对比"),
                    "use_cases": ("partial", "特性对比含适用场景"),
                    "ecosystem": ("partial", "标题含 Django REST（具体组件），正文未见")}},
    {"id": "n01",
     "url": "https://www.agilesoftlabs.com/blog/2026/02/monolith-vs-microservices-decision",
     "title": "Monolith vs Microservices Decision Framework 2026",
     "snippet": ("Feb 10, 2026 · Monolith vs Microservices Decision Framework 2026 About the "
                 "Author Nirmalraj R is a Full-Stack Developer at AgileSo"),
     "annotation": {"performance": ("topic_only", "架构决策文，非三框架"),
                    "use_cases": ("topic_only", "microservices 主题相邻但不含三框架选型信息"),
                    "ecosystem": ("irrelevant", "非同域")}},
    {"id": "n02",
     "url": "https://outplane.com/blog/microservices-vs-monolith",
     "title": "Microservices vs. Monolith in 2026: A Practical Decision",
     "snippet": ("Feb 14, 2026 · Microservices or monolith? Use this practical decision "
                 "framework based on team size, traffic patterns, and organiza"),
     "annotation": {"performance": ("topic_only", "同 n01"),
                    "use_cases": ("topic_only", "通用架构决策，无框架特定信息"),
                    "ecosystem": ("irrelevant", "非同域")}},
    {"id": "n14",
     "url": "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/",
     "title": "Community Ecology and Ecosystem Ecology - Biology",
     "snippet": ("Ecosystem ecology is an extension of organismal, population, and community "
                 "ecology. The ecosystem is composed of all the biotic compo"),
     "annotation": {"performance": ("irrelevant", "生物学"),
                    "use_cases": ("irrelevant", "生物学"),
                    "ecosystem": ("irrelevant", "生物学 ecosystem——跨域主题碰撞，与框架生态无关")}},
    {"id": "n15",
     "url": "https://keep.konza.k-state.edu/education/Tallgrass+Prairie+Storyline-Lesson3-OutlineB.pdf",
     "title": "Lesson 3: Comparing Ecosystems",
     "snippet": ("A Limiting Factor is a resource in an ecosystem that is needed for an "
                "organisms' life, and which may be in limited supply, thus ke"),
     "annotation": {"performance": ("irrelevant", "生物学"),
                    "use_cases": ("irrelevant", "生物学"),
                    "ecosystem": ("irrelevant", "跨域主题碰撞")}},
    {"id": "n17",
     "url": "https://www.greenlivinganswers.com/ecosystem/biome-ecosystem-relationship",
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
