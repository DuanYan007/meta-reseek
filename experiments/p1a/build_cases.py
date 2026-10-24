"""Build the P1-a case set (v2) from REAL retrieval evidence + constructed cases.

Real evidence text is recovered from the local search cache by matching the
URLs recorded in artifacts/demo traces (cache is machine-local; this script
documents provenance — cases.json itself carries source URLs, so the
experiment is reproducible without the cache).

Annotations are CANDIDATE annotations drafted by GLM (document-level
relevance + snapshot-level sufficiency), pending human/GPT verification —
they must NOT be described as a verified gold standard.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# candidate document-level annotations: case_id -> {subq: (relevant?, basis)}
DOC_ANNOTATIONS = {
    "e001": {"definition": (True, "真实检索结果；snippet 解释 KV cache 避免重算的机制"),
             "cost": (False, "未涉及显存占用原因"),
             "techniques": (False, "未提及任何缩减技术")},
    "e002": {"definition": (True, "矩阵级解释 prefill/decode 与缓存原因"),
             "cost": (False, "无显存占用内容"),
             "techniques": (False, "无具体技术")},
    "e003": {"definition": (True, "解释 KV cache 使推理加速"),
             "cost": (True, "含 memory math（显存计算）"),
             "techniques": (True, "明确点名 GQA/MQA/PagedAttention")},
    "e004": {"definition": (True, "plain words 解释 KV caching 含义"),
             "cost": (False, "无"), "techniques": (False, "无")},
    "e005": {"definition": (True, "解释 KV caching 工作原理"),
             "cost": (False, "无"), "techniques": (False, "无")},
    "e006": {"definition": (True, "说明 what KV cache is"),
             "cost": (True, "如何计算 GPU 显存占用、长上下文/并发耗尽显存"),
             "techniques": (False, "无具体技术名")},
    "e007": {"definition": (True, "以存储张量换计算解释机制"),
             "cost": (True, "明确给出『随上下文线性增长』这一关键机制"),
             "techniques": (False, "无")},
    "e008": {"definition": (False, "只讲用量，不讲定义"),
             "cost": (True, "per-token 估算与精确公式"),
             "techniques": (False, "无")},
    "e009": {"definition": (False, "未解释定义"),
             "cost": (True, "解释为何消耗 VRAM"),
             "techniques": (False, "仅说 practical techniques 未点名任何具体技术——缺关键回答条件")},
    "e010": {"definition": (False, "无"),
             "cost": (True, "给出 Llama3 70B@128K 真实用量规模"),
             "techniques": (False, "无")},
    "e011": {"definition": (False, "综述不提供入门定义"),
             "cost": (False, "不以显存原因为主题"),
             "techniques": (True, "系统综述各类 KV cache 管理技术")},
    "e012": {"definition": (False, "同 e011"),
             "cost": (False, "同 e011"),
             "techniques": (True, "同 e011（与 e011 为同一论文 html/pdf 双版本——同质重复）")},
    "e013": {"definition": (False, "无定义解释"),
             "cost": (False, "仅提 VRAM 瓶颈现象"),
             "techniques": (True, "点名 PagedAttention/quantization/vLLM")},
    "e014": {"definition": (False, "无"),
             "cost": (False, "只给参数/缓存用量对比数字"),
             "techniques": (True, "Top 10 压缩技术清单")},
    "e015": {"definition": (False, "无"),
             "cost": (False, "无"),
             "techniques": (True, "quantization 等压缩方法")},
    # constructed cases (provenance = constructed, intent recorded)
    "B-syn-def": {"definition": (True, "构造：同义改写解释缓存机制（memoize past states），无词面重叠"),
                  "cost": (False, "无"), "techniques": (False, "无")},
    "C-topic-cost": {"definition": (False, "无"),
                     "cost": (False, "构造：游戏显卡 VRAM 选购，主题词重叠（GPU memory）但与 KV cache 增长原因无关"),
                     "techniques": (False, "无")},
    "E-jargon-cost": {"definition": (False, "无"),
                      "cost": (True, "构造：以行话（HBM/中间态累积/上下文长度）表述显存耗尽原因——真实相关但词法难命中"),
                      "techniques": (False, "无")},
    "H-syn-tech": {"definition": (False, "无"),
                   "cost": (False, "无"),
                   "techniques": (True, "构造：同义表述（sharing heads / compressing cached states）概括两类缩减手段，无 MQA/GQA 等术语")},
    "CALC-missing-why": {"definition": (False, "无"),
                         "cost": (False, "构造：用量计算器（数字/公式模板），主题高度相关但完全不含『为何增长』的机制信息——缺关键回答条件"),
                         "techniques": (False, "无")},
}

CONSTRUCTED = [
    {
        "id": "B-syn-def", "intent": "fn_paraphrase(同义改写漏检)",
        "title": "Memoizing past attention states in decoder-only models",
        "snippet": "Instead of recomputing intermediate projections at every generation step, serving engines memoize them, trading extra accelerator memory for lower latency.",
        "url": None, "domain": "constructed.example",
    },
    {
        "id": "C-topic-cost", "intent": "fp_topic_overlap(主题词重叠伪相关)",
        "title": "Best gaming GPUs by memory size: the 2024 VRAM tier list",
        "snippet": "We compare GPU memory across graphics cards and explain why GPU memory matters for gaming and which card to buy.",
        "url": None, "domain": "constructed.example",
    },
    {
        "id": "E-jargon-cost", "intent": "fn_jargon(行话表述漏检)",
        "title": "The hidden memory wall of autoregressive serving",
        "snippet": "Per-token intermediate states accumulate with context length and quickly exhaust HBM on accelerator cards during long-generation workloads.",
        "url": None, "domain": "constructed.example",
    },
    {
        "id": "H-syn-tech", "intent": "fn_paraphrase(同义改写漏检)",
        "title": "Cutting the memory bill of large-model serving",
        "snippet": "Sharing attention heads and compressing cached token states are the two main levers providers use to fit long contexts on one card.",
        "url": None, "domain": "constructed.example",
    },
    {
        "id": "CALC-missing-why", "intent": "missing_condition(覆盖主题缺关键条件)",
        "title": "KV cache memory calculator: plug in your model size",
        "snippet": "Enter layers, heads and context length to compute KV cache GPU memory usage for popular models. Numbers update instantly.",
        "url": None, "domain": "constructed.example",
    },
]

SNAPSHOTS = [
    {
        "id": "S1-homogeneous-definition",
        "members": ["e001", "e002", "e004"],
        "purpose": "同质冗余观察：三条入门解释内容高度重复",
        "sufficiency": {
            "definition": {"sufficient": True, "basis": "信息上足够（一条入门解释即可），三条互为冗余"},
            "cost": {"sufficient": False, "basis": "集合内无任何 cost 相关文档"},
            "techniques": {"sufficient": False, "basis": "集合内无任何 techniques 相关文档"},
        },
    },
    {
        "id": "S2-pseudo-coverage-wrong-stop",
        "members": ["e001", "e005", "e009", "e013", "e015", "C-topic-cost", "CALC-missing-why"],
        "purpose": "伪相关推高覆盖 → 构造错误停止建议场景：cost 仅有 e009 真正回答 why，C/CALC 为伪相关",
        "sufficiency": {
            "definition": {"sufficient": True, "basis": "e001/e005 真相关"},
            "cost": {"sufficient": False, "basis": "仅 e009 真正解释原因；C（游戏选购）与 CALC（只有数字无机制）为伪相关，关键信息不足"},
            "techniques": {"sufficient": True, "basis": "e013/e015 点名具体技术"},
        },
    },
    {
        "id": "S3-real-after-round2",
        "members": ["e001", "e002", "e003", "e004", "e005", "e006", "e007", "e008", "e009", "e010"],
        "purpose": "真实对照：demo 运行第 2 轮后的实际证据状态（正确继续决策的对照）",
        "sufficiency": {
            "definition": {"sufficient": True, "basis": "多条真相关（含冗余）"},
            "cost": {"sufficient": True, "basis": "e006-e010 中至少两条真相关（e007 含线性增长机制）"},
            "techniques": {"sufficient": False, "basis": "仅 e003 一条真相关，缺第二条"},
        },
    },
    {
        "id": "S5-missing-condition",
        "members": ["e001", "e002", "e003", "e005", "CALC-missing-why", "C-topic-cost"],
        "purpose": "覆盖主题但缺关键回答条件：cost 子问题主题命中但无任何机制信息",
        "sufficiency": {
            "definition": {"sufficient": True, "basis": "e001/e002/e005 真相关"},
            "cost": {"sufficient": False, "basis": "CALC 只有数字、C 是游戏页——无任何『为何增长』信息，主题覆盖≠回答条件满足"},
            "techniques": {"sufficient": False, "basis": "仅 e003 一条"},
        },
    },
    {
        "id": "S6-real-final-state",
        "members": [f"e{i:03d}" for i in range(1, 16)],
        "purpose": "真实最终状态（demo 运行停止时）：全子问题充分，但含同质冗余",
        "sufficiency": {
            "definition": {"sufficient": True, "basis": "多条真相关（冗余偏高）"},
            "cost": {"sufficient": True, "basis": "e006-e010 多条真相关"},
            "techniques": {"sufficient": True, "basis": "e013/e014/e015 真相关（e014 词法仅 0.149 漏检）"},
        },
    },
]


def main() -> int:
    # recover real evidence text from the local search cache
    hits = {}
    for p in (REPO / "artifacts/cache").glob("*.json"):
        for h in json.loads(p.read_text(encoding="utf-8"))["hits"]:
            hits.setdefault(h["url"].rstrip("/").lower(), h)

    trace = json.loads((REPO / "artifacts/demo/kv_cache_llm.json").read_text(encoding="utf-8"))
    cases = []
    for ev in trace["evidence"]:
        h = hits[ev["url"].rstrip("/").lower()]
        ann = DOC_ANNOTATIONS[ev["eid"]]
        cases.append({
            "id": ev["eid"],
            "source": f"demo-trace:kv_cache_llm:{ev['eid']} (round {ev['round_added']}, strategy {ev['strategy']})",
            "url": ev["url"],
            "domain": ev["domain"],
            "title": h["title"],
            "snippet": h["snippet"],
            "intent": "real",
            "doc_annotation": {k: {"relevant": v[0], "basis": v[1]} for k, v in ann.items()},
        })
    for c in CONSTRUCTED:
        ann = DOC_ANNOTATIONS[c["id"]]
        cases.append({
            "id": c["id"],
            "source": f"constructed ({c['intent']})",
            "url": c["url"],
            "domain": c["domain"],
            "title": c["title"],
            "snippet": c["snippet"],
            "intent": c["intent"],
            "doc_annotation": {k: {"relevant": v[0], "basis": v[1]} for k, v in ann.items()},
        })

    out = {
        "task": "examples/tasks/kv_cache_llm.yaml",
        "annotation_status": "CANDIDATE — 由 GLM 起草，尚未经 GPT/研究人员核查，不得称为人工金标准",
        "n_cases": len(cases),
        "cases": cases,
        "snapshots": SNAPSHOTS,
    }
    path = REPO / "experiments/p1a/cases.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"cases.json written: {len(cases)} cases, {len(SNAPSHOTS)} snapshots ->", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
