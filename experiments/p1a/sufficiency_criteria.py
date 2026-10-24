"""Task B: sufficiency criteria for the P1-a sub-questions (MINIMAL validation).

对每个子问题定义**可观察的必要回答要点**（answer points），每个要点是一组
同义感知的词面模式。判据与词法/语义相关性不同：它检验的是"证据集合是否
覆盖了回答该子问题所必需的信息点"，而不是"文档与子问题有多相关"。

规则：
- 文档层：一篇文档对某要点"有点"= 其标题+摘要命中该要点的任一模式；
  文档对子问题"满足回答条件" = 覆盖该子问题的全部要点；
- 集合层：子问题充分 = 全部要点被覆盖 **且** 提供覆盖的来源域 ≥2
  （独立信息贡献；同源/同域重复只计一次，并作为冗余单独报告）；
- 输出每次判断的证据（命中片段）、缺口（未覆盖要点）与可解释理由。

**重要限定**：判据模式参考了本轮案例集草拟，存在过拟合风险；本模块
**未接入** P0 生产检索控制器，仅用于固定快照上的判据验证（任务书要求）。
"""

from __future__ import annotations

import re

# 每个要点：模式为 regex（IGNORECASE），任一命中即覆盖
CRITERIA: dict[str, dict[str, list[str]]] = {
    "definition": {
        "P1-缓存对象": [
            r"kv[- ]cache", r"key[- ]value", r"keys and values",
            r"cache[sd]? (the )?(key|past|attention)",
            r"past attention states", r"intermediate (projections|states|tensors)", r"memoiz",
        ],
        "P2-机制与目的": [
            r"without recomput", r"avoid recomput", r"instead of recomput", r"reus",
            r"trades? memory for", r"faster", r"speed", r"latency",
            r"make[s]? (llm|inference|transformer)\w* fast",
        ],
        "P3-场景": [
            r"inference", r"generation", r"decod", r"autoregressive", r"prefill",
            r"serving", r"\bllm\b", r"language model",
        ],
    },
    "cost": {
        "P1-增长关系（机制）": [
            r"linear", r"scales? with", r"grows? (linearly|with)", r"growth",
            r"accumulat", r"per[- ]token", r"each token",
            r"as (the )?(context|sequence|batch)",
            r"(context|sequence|batch)[^.;]{0,40}(exhaust|increas)",
            r"long context[^.;]{0,40}(exhaust|can)",
        ],
        "P2-量级与占用": [
            r"\d+\s*(gb|mb|tb)", r"memory (usage|footprint|consum\w+|require\w+)",
            r"vram", r"hbm", r"bottleneck", r"exhaust", r"out of memory", r"\boom\b",
            r"consum\w+ (so )?much", r"dominat",
        ],
    },
    "techniques": {
        "P1-具体技术（名称或类别）": [
            r"\bgqa\b", r"\bmqa\b", r"multi[- ]query", r"grouped[- ]query",
            r"pagedattention", r"paged attention", r"quantiz", r"\bint8\b", r"\bint4\b",
            r"compress", r"shar\w+ (attention|query|\w* heads)", r"evict",
            r"sliding window", r"sparsif", r"low[- ]rank",
        ],
        "P2-作用方式（缩减/管理）": [
            r"reduce", r"cut", r"halv", r"manag", r"optimiz",
            r"serve (more|\d+x)", r"fit (long )?(context|\w+ contexts)",
            r"prevent oom", r"memory (bill|waste|saving)",
        ],
    },
}

_REQUIRED_POINTS = {sq: list(pts) for sq, pts in CRITERIA.items()}
_COMPILED = {
    sq: {pid: [re.compile(p, re.IGNORECASE) for p in pats]
         for pid, pats in pts.items()}
    for sq, pts in CRITERIA.items()
}


def check_points(text: str, subq_id: str) -> dict[str, str | None]:
    """Which answer points of a sub-question this text covers, with evidence
    spans (first match, ±40 chars of context)."""
    out: dict[str, str | None] = {}
    for pid, patterns in _COMPILED[subq_id].items():
        hit = None
        for pat in patterns:
            m = pat.search(text)
            if m:
                s, e = max(0, m.start() - 40), min(len(text), m.end() + 40)
                hit = "…" + text[s:e].replace("\n", " ") + "…"
                break
        out[pid] = hit
    return out


def doc_level(text: str, subq_id: str) -> dict:
    """Document-level judgement for one (doc, sub-question)."""
    covered = check_points(text, subq_id)
    points = _REQUIRED_POINTS[subq_id]
    covered_ids = [p for p in points if covered[p] is not None]
    if not covered_ids:
        klass = "topic_or_less"      # 未覆盖任何必要要点
    elif len(covered_ids) == len(points):
        klass = "condition_met"      # 覆盖全部必要要点
    else:
        klass = "partial_points"     # 覆盖部分要点
    return {
        "class": klass,
        "covered_points": covered_ids,
        "missing_points": [p for p in points if covered[p] is None],
        "evidence": {p: covered[p] for p in covered_ids},
    }


def snapshot_level(docs: list[dict], subq_id: str, min_domains: int = 2,
                   require_condition_met_doc: bool = True) -> dict:
    """Set-level sufficiency for one sub-question.

    docs: [{'id', 'domain', 'text'}] members of the snapshot.

    v1 (require_condition_met_doc=False): satisfied iff every required point
    is covered by >=1 doc AND covering domains >= min_domains.
    Observed failure (S3): point-splitting — different points covered by
    different docs, none of which individually constitutes an answer.

    v2 (default, anti-splitting): additionally require >=1 doc whose own
    coverage spans ALL required points (point-internal coherence), with the
    remaining docs providing independent corroboration.
    """
    points = _REQUIRED_POINTS[subq_id]
    point_docs: dict[str, list[dict]] = {p: [] for p in points}
    condition_met_docs: list[str] = []
    for d in docs:
        res = doc_level(d["text"], subq_id)
        if res["class"] == "condition_met":
            condition_met_docs.append(d["id"])
        for p in res["covered_points"]:
            point_docs[p].append({"id": d["id"], "domain": d["domain"],
                                  "evidence": res["evidence"][p]})
    covered_points = [p for p in points if point_docs[p]]
    missing = [p for p in points if not point_docs[p]]
    domains = sorted({e["domain"] for p in covered_points for e in point_docs[p]})
    sufficient = (not missing) and (len(domains) >= min_domains)
    if require_condition_met_doc:
        sufficient = sufficient and bool(condition_met_docs)

    contributors = sorted({e["id"] for p in covered_points for e in point_docs[p]})
    redundant = [d["id"] for d in docs if d["id"] not in contributors]
    same_domain_redundancy = {
        p: len(point_docs[p]) - len({e["domain"] for e in point_docs[p]})
        for p in covered_points
        if len(point_docs[p]) > len({e["domain"] for e in point_docs[p]})
    }

    if missing:
        reason = f"要点未覆盖：{missing}"
    elif len(domains) < min_domains:
        reason = f"全部要点已覆盖但独立来源域仅 {len(domains)} 个（要求 ≥{min_domains}），单一来源不足以确认"
    elif require_condition_met_doc and not condition_met_docs:
        reason = ("全部要点已由不同文档拼接覆盖，但没有任何一篇文档自身完整覆盖全部要点"
                  "（防跨文档碎片拼接条件不满足）")
    else:
        reason = (f"全部要点已覆盖，独立来源域 {len(domains)} 个，"
                  f"完整覆盖文档 {condition_met_docs}")

    return {
        "subq": subq_id,
        "sufficient": sufficient,
        "condition_met_docs": condition_met_docs,
        "covered_points": {
            p: [{"doc": e["id"], "domain": e["domain"], "evidence": e["evidence"]}
                for e in point_docs[p]]
            for p in covered_points
        },
        "missing_points": missing,
        "domains": domains,
        "redundant_docs": redundant,
        "same_domain_redundancy": same_domain_redundancy,
        "reason": reason,
    }
