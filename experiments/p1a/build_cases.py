"""Build the P1-a case set (v3) from real search-result titles+snippets + constructed cases.

v3 (2026-10-24, PR #4 整改):
- 四级标注标准: irrelevant / topic_only / partial / sufficient_support
  (区分"主题相关 / 提供部分回答信息 / 充分支持子问题"，低于主题相关为 irrelevant);
- 争议标签复核并记录 revision_log（含修改依据）;
- 同源去重: e012（与 e011 同一论文的 pdf 版本）并入 e011，不再作为独立案例;
- 措辞修正: 真实案例是"真实搜索结果的标题与摘要"，不是完整文档;
- 快照 S2 成员修订（e009 复核为充分支持后不再构成伪覆盖场景）。

Real evidence text = 标题+摘要 of DuckDuckGo results recorded in the demo
trace; recovered from the local search cache by URL match (cache is
machine-local; cases.json carries source URLs so the experiment is
reproducible without it).

Annotations are CANDIDATE annotations drafted by GLM, pending GPT/human
verification — NOT a verified gold standard.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

SCALE = ["irrelevant", "topic_only", "partial", "sufficient_support"]

# candidate document-level annotations: case_id -> {subq: (level, basis)}
DOC = {
    "e001": {"definition": ("sufficient_support", "专门解释 KV cache 的入门文（真实搜索结果的标题与摘要）"),
             "cost": ("topic_only", "同域主题，摘要未涉及显存占用原因"),
             "techniques": ("topic_only", "同域主题，未提及缩减技术")},
    "e002": {"definition": ("sufficient_support", "矩阵级解释 prefill/decode 与缓存原因"),
             "cost": ("topic_only", "摘要无显存内容"),
             "techniques": ("topic_only", "无")},
    "e003": {"definition": ("partial", "解释 KV cache 使推理加速，但页面主题宽泛"),
             "cost": ("partial", "含 memory math 要点，提供部分量化信息，未给增长机制",
                      "不确定：摘要仅列要点名（memory math）而无展开，partial 与 topic_only 边界依赖全文，人工核查优先"),
             "techniques": ("sufficient_support", "明确点名 GQA/MQA/PagedAttention")},
    "e004": {"definition": ("sufficient_support", "plain words 解释 KV caching 含义"),
             "cost": ("topic_only", "无"), "techniques": ("topic_only", "无")},
    "e005": {"definition": ("sufficient_support", "完整讲解 KV caching 工作原理"),
             "cost": ("topic_only", "无"), "techniques": ("topic_only", "无")},
    "e006": {"definition": ("partial", "提及 what KV cache is，但页面为多主题"),
             "cost": ("sufficient_support", "说明如何计算 GPU 显存占用，且点名长上下文/并发两个增长驱动因素"),
             "techniques": ("topic_only", "未点名具体技术")},
    "e007": {"definition": ("partial", "以存储张量换计算解释机制，未展开定义"),
             "cost": ("sufficient_support", "明确给出『随上下文线性增长』关键机制"),
             "techniques": ("topic_only", "无")},
    "e008": {"definition": ("topic_only", "同域主题，摘要只讲用量不讲定义"),
             "cost": ("sufficient_support", "per-token 估算与精确公式，量化了占用为何大"),
             "techniques": ("topic_only", "无")},
    "e009": {"definition": ("topic_only", "未解释定义"),
             "cost": ("sufficient_support", "直接回答『为何消耗大量 VRAM』并给出管理手段"),
             "techniques": ("topic_only", "仅说 practical techniques 未点名任何技术——不构成部分回答信息")},
    "e010": {"definition": ("topic_only", "无定义内容"),
             "cost": ("partial", "给出 Llama3 70B@128K 真实用量量级，提供量级佐证但无增长机制"),
             "techniques": ("topic_only", "无")},
    "e011": {"definition": ("topic_only", "综述不提供入门定义"),
             "cost": ("topic_only", "摘要未涉及显存增长原因"),
             "techniques": ("sufficient_support", "系统综述各类 KV cache 管理技术；注：同一论文的 html/pdf 双版本曾被系统同时接受（去重未命中），案例集按单一来源计")},
    "e013": {"definition": ("topic_only", "无定义解释"),
             "cost": ("topic_only", "仅提 VRAM 瓶颈现象"),
             "techniques": ("sufficient_support", "点名 PagedAttention/quantization/vLLM")},
    "e014": {"definition": ("topic_only", "无定义内容"),
             "cost": ("partial", "参数 14GB vs 缓存 72GB 的对比量化了占用之巨，但无增长机制"),
             "techniques": ("sufficient_support", "Top 10 压缩技术清单")},
    "e015": {"definition": ("topic_only", "无"),
             "cost": ("topic_only", "无"),
             "techniques": ("sufficient_support", "quantization 等压缩方法")},
    "B-syn-def": {"definition": ("sufficient_support", "构造：同义改写完整解释缓存机制（memoize past states）"),
                  "cost": ("topic_only", "同域主题"), "techniques": ("topic_only", "无")},
    "C-topic-cost": {"definition": ("irrelevant", "游戏显卡内容，非 KV cache 域"),
                     "cost": ("topic_only", "构造：GPU memory 主题词重叠，但对『KV cache 为何耗显存』无任何回答信息"),
                     "techniques": ("irrelevant", "非同域")},
    "E-jargon-cost": {"definition": ("partial", "构造：以行话描述逐 token 状态累积现象，隐含机制但未命名 KV cache",
                                     "不确定：『隐含机制』是否构成 definition 的部分回答依赖解读，人工核查优先"),
                      "cost": ("sufficient_support", "构造：HBM 耗尽 + 随上下文累积的机制表述，真实相关但词法难命中"),
                      "techniques": ("topic_only", "无具体技术")},
    "H-syn-tech": {"definition": ("topic_only", "同域主题"),
                   "cost": ("topic_only", "无增长机制"),
                   "techniques": ("sufficient_support", "构造：同义表述（sharing heads / compressing cached states）概括两类缩减手段")},
    "CALC-missing-why": {"definition": ("topic_only", "同域主题，无定义"),
                         "cost": ("partial", "构造：给出决定因子（layers/heads/context length），提供部分回答信息，但无逐 token 累积机制——覆盖主题缺关键回答条件",
                                  "不确定：决定因子列表是否算『部分回答信息』存在解释空间（也可视作仅主题命中），人工核查优先"),
                         "techniques": ("topic_only", "计算器非缩减技术")},
}

CONSTRUCTED = [
    {"id": "B-syn-def", "intent": "fn_paraphrase(同义改写漏检)",
     "title": "Memoizing past attention states in decoder-only models",
     "snippet": "Instead of recomputing intermediate projections at every generation step, serving engines memoize them, trading extra accelerator memory for lower latency.",
     "domain": "constructed.example"},
    {"id": "C-topic-cost", "intent": "fp_topic_overlap(主题词重叠伪相关)",
     "title": "Best gaming GPUs by memory size: the 2024 VRAM tier list",
     "snippet": "We compare GPU memory across graphics cards and explain why GPU memory matters for gaming and which card to buy.",
     "domain": "constructed.example"},
    {"id": "E-jargon-cost", "intent": "fn_jargon(行话表述漏检)",
     "title": "The hidden memory wall of autoregressive serving",
     "snippet": "Per-token intermediate states accumulate with context length and quickly exhaust HBM on accelerator cards during long-generation workloads.",
     "domain": "constructed.example"},
    {"id": "H-syn-tech", "intent": "fn_paraphrase(同义改写漏检)",
     "title": "Cutting the memory bill of large-model serving",
     "snippet": "Sharing attention heads and compressing cached token states are the two main levers providers use to fit long contexts on one card.",
     "domain": "constructed.example"},
    {"id": "CALC-missing-why", "intent": "missing_condition(覆盖主题缺关键条件)",
     "title": "KV cache memory calculator: plug in your model size",
     "snippet": "Enter layers, heads and context length to compute KV cache GPU memory usage for popular models. Numbers update instantly.",
     "domain": "constructed.example"},
]

SNAPSHOTS = [
    {"id": "S1-homogeneous-definition",
     "members": ["e001", "e002", "e004"],
     "purpose": "同质冗余观察：三条入门解释内容高度重复（真实搜索结果标题与摘要）",
     "sufficiency": {
         "definition": {"sufficient": True, "basis": "e001/e002/e004 均为充分支持级，信息上足够（三条互为冗余）"},
         "cost": {"sufficient": False, "basis": "集合内无 cost 相关文档"},
         "techniques": {"sufficient": False, "basis": "集合内无 techniques 相关文档"},
     }},
    {"id": "S2-pseudo-coverage-wrong-stop",
     "members": ["e001", "e005", "e010", "e013", "e015", "C-topic-cost", "CALC-missing-why"],
     "purpose": "伪覆盖错误停止（修订版）：cost 仅有 e010(部分) 与 CALC(部分)、C(仅主题)，无任何充分支持级文档——主题命中推高覆盖但关键回答条件（增长机制）缺失",
     "sufficiency": {
         "definition": {"sufficient": True, "basis": "e001/e005 充分支持"},
         "cost": {"sufficient": False, "basis": "仅 e010/CALC 部分回答 + C 仅主题相关；无任何文档给出增长机制——主题覆盖≠回答条件满足"},
         "techniques": {"sufficient": True, "basis": "e013/e015 充分支持"},
     }},
    {"id": "S3-real-after-round2",
     "members": ["e001", "e002", "e003", "e004", "e005", "e006", "e007", "e008", "e009", "e010"],
     "purpose": "真实对照：demo 运行第 2 轮后的实际证据状态（标题与摘要）",
     "sufficiency": {
         "definition": {"sufficient": True, "basis": "多条充分支持级（含冗余）"},
         "cost": {"sufficient": True, "basis": "e006/e007/e008/e009 中多条充分支持级（含线性增长机制）"},
         "techniques": {"sufficient": False, "basis": "仅 e003 一条充分支持级，缺第二条",
                        "uncertain": True,
                        "uncertainty": "判据复核发现：e001 完整摘要（标题与摘要全文）含『systems like vLLM, PagedAttention, and GQA manage it at scale』，自身即覆盖技术名与管理作用两要点——本标注起草于截断视图，techniques 是否应为『充分』待人工核查（2026-10-24 任务 B 发现）"},
     }},
    {"id": "S5-missing-condition",
     "members": ["e001", "e002", "e003", "e005", "CALC-missing-why", "C-topic-cost"],
     "purpose": "覆盖主题但缺关键回答条件：cost 主题命中（e003/CALC 部分 + C 仅主题）但无机制文档",
     "sufficiency": {
         "definition": {"sufficient": True, "basis": "e001/e002/e005 充分支持"},
         "cost": {"sufficient": False, "basis": "e003/CALC 均为部分回答、C 仅主题相关——无增长机制，回答条件未满足"},
         "techniques": {"sufficient": False, "basis": "仅 e003 一条充分支持级"},
     }},
    {"id": "S6-real-final-state",
     "members": ["e001", "e002", "e003", "e004", "e005", "e006", "e007", "e008",
                 "e009", "e010", "e011", "e013", "e014", "e015"],
     "purpose": "真实最终状态（demo 运行停止时，同源 pdf 已去重后 14 条标题与摘要）",
     "sufficiency": {
         "definition": {"sufficient": True, "basis": "多条充分支持级（冗余偏高）"},
         "cost": {"sufficient": True, "basis": "e006-e010 多条充分/部分支持"},
         "techniques": {"sufficient": True, "basis": "e011/e013/e014/e015 充分支持"},
     }},
]

REVISION_LOG = [
    {"item": "e012", "change": "删除独立案例，与 e011 同源（同一论文 html/pdf 双版本）合并为单一来源",
     "basis": "整改指令第 4 条（同源重复证据）；原案例集将其计为两条独立证据会重复计入覆盖"},
    {"item": "e009->cost", "change": "复核维持『充分支持』：摘要直接回答『为何消耗大量 VRAM』",
     "basis": "争议标签复核；据此 S2 成员修订——原 S2 中 e009 已构成充分支持，不再是伪覆盖场景"},
    {"item": "S2 members", "change": "以 e010 替换 e009，维持『主题命中但无机制文档』的检验目的",
     "basis": "e009 复核结论；不得人为保持原实验结论（整改指令第 5 条）"},
    {"item": "e006->definition", "change": "相关 → partial(部分回答)",
     "basis": "四级标准落地：多主题页对 definition 只提供部分信息"},
    {"item": "e010->cost", "change": "相关 → partial", "basis": "量级佐证但无增长机制，属部分回答而非充分支持"},
    {"item": "e014->cost", "change": "不相关 → partial",
     "basis": "复核发现摘要含 14GB/72GB 对比，量化了占用之巨，属部分回答信息（原判过严）"},
    {"item": "CALC->cost", "change": "不相关 → partial",
     "basis": "四级标准落地：给出决定因子（layers/heads/context）属部分回答信息；『缺关键条件』由快照层充分性标注表达，不再靠文档层二值标签表达"},
    {"item": "E->definition", "change": "不相关 → partial",
     "basis": "四级标准落地：行话描述隐含机制，对 definition 提供部分信息"},
    {"item": "e008~e015->definition（原判不相关）", "change": "不相关 → topic_only",
     "basis": "四级标准落地：同域主题但无定义信息，与『完全不相关』（如 C→definition=irrelevant）区分"},
    {"item": "e009->techniques", "change": "维持最低档（topic_only）",
     "basis": "争议复核：仅提『存在 practical techniques』未点名任何技术，不构成部分回答信息"},
    {"item": "e011->cost", "change": "维持 topic_only", "basis": "摘要未涉及显存增长原因"},
    {"item": "争议标注不确定性记录（2026-10-24 任务 A）",
     "change": "为 e003→cost、E→definition、CALC→cost 三条 partial 标注增加 uncertain/uncertainty 字段",
     "basis": "任务 A 第 5 条：仍有争议的候选标注记录不确定性；标签本身维持复核后的判定，重跑实验验证统计不变"},
    {"item": "S3/techniques 充分性标注（2026-10-24 任务 B 发现）",
     "change": "增加 uncertain 标记（判定暂维持『不充分』）",
     "basis": "判据评估读完整摘要发现 e001 含 vLLM/PagedAttention/GQA 及 manage 表述，与『仅 e003 支持』的起草依据冲突；标注是否应改为『充分』由人工核查裁决，不在本轮擅自改动"},
]


def _ann_dict(ann):
    """(level, basis[, uncertainty]) -> JSON annotation dict."""
    out = {"level": ann[0], "basis": ann[1]}
    if len(ann) > 2:
        out["uncertain"] = True
        out["uncertainty"] = ann[2]
    return out


def main() -> int:
    hits = {}
    for p in (REPO / "artifacts/cache").glob("*.json"):
        for h in json.loads(p.read_text(encoding="utf-8"))["hits"]:
            hits.setdefault(h["url"].rstrip("/").lower(), h)

    trace = json.loads((REPO / "artifacts/demo/kv_cache_llm.json").read_text(encoding="utf-8"))
    dropped = {"e012"}  # 同源去重
    cases = []
    for ev in trace["evidence"]:
        if ev["eid"] in dropped:
            continue
        h = hits[ev["url"].rstrip("/").lower()]
        ann = DOC[ev["eid"]]
        cases.append({
            "id": ev["eid"],
            "source": (f"demo-trace:kv_cache_llm:{ev['eid']} (round {ev['round_added']}, "
                       f"strategy {ev['strategy']}) — 真实搜索结果的标题与摘要（非完整文档）"),
            "url": ev["url"],
            "domain": ev["domain"],
            "title": h["title"],
            "snippet": h["snippet"],
            "intent": "real",
            "doc_annotation": {k: _ann_dict(v) for k, v in ann.items()},
        })
    for c in CONSTRUCTED:
        ann = DOC[c["id"]]
        cases.append({
            "id": c["id"],
            "source": f"constructed ({c['intent']})",
            "url": None,
            "domain": c["domain"],
            "title": c["title"],
            "snippet": c["snippet"],
            "intent": c["intent"],
            "doc_annotation": {k: _ann_dict(v) for k, v in ann.items()},
        })

    out = {
        "task": "examples/tasks/kv_cache_llm.yaml",
        "annotation_status": "CANDIDATE — 由 GLM 起草，尚未经 GPT/研究人员核查，不得称为人工金标准",
        "annotation_scale": {
            "irrelevant": "与子问题无主题关联",
            "topic_only": "主题相关，但未提供回答信息",
            "partial": "提供部分回答信息，不充分支持子问题",
            "sufficient_support": "充分支持该子问题",
        },
        "evidence_scope": "全部真实案例均为搜索结果的标题与摘要（title+snippet），非页面全文；实验为静态固定快照口径",
        "n_cases": len(cases),
        "cases": cases,
        "snapshots": SNAPSHOTS,
        "revision_log": REVISION_LOG,
    }
    path = REPO / "experiments/p1a/cases.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"cases.json written: {len(cases)} cases, {len(SNAPSHOTS)} snapshots ->", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
