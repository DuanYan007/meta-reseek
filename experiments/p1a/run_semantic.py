"""P1-a node 2: minimal semantic comparison on the SAME case set and criteria.

Cosine similarity (all-MiniLM-L6-v2, local HF cache) between the
sub-question TEXT and the document (title + snippet), fed into the SAME
accept-rule shape and the SAME production snapshot evaluator as the lexical
arm. Thresholds 0.4/0.5/0.6 are EXPLORATORY.

The report is generated fully from data (build_report); no hardcoded
statistics. A consistency test re-generates the report and compares it with
the committed file, so annotation changes cannot silently desync docs and
data.

Explicit limits: similarity is a relevance proxy; it must never be
presented as proof of evidence sufficiency.
"""

from __future__ import annotations

import json
from pathlib import Path

from common import (REL_MARGIN, RELEVANT_LEVELS, accept_rule,
                    compare_with_annotation, doc_level_report, load,
                    snapshot_verdict)

HERE = Path(__file__).parent
MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
PRIMARY_T = 0.5
THRESHOLDS = [0.4, 0.5, 0.6]


def semantic_scores(task, cases) -> dict[str, dict[str, float]]:
    """Cosine similarity (sub-question text vs document). Returns matrix."""
    import os

    os.environ.setdefault("HF_ENDPOINT", "https://huggingface.co")
    import torch
    from transformers import AutoModel, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModel.from_pretrained(MODEL_ID)
    model.eval()
    texts = [sq.text for sq in task.sub_questions] + [
        f"{c['title']}. {c['snippet']}" for c in cases
    ]
    enc = tok(texts, padding=True, truncation=True, max_length=256, return_tensors="pt")
    with torch.no_grad():
        hidden = model(**enc).last_hidden_state
    mask = enc["attention_mask"].unsqueeze(-1).to(hidden.dtype)
    emb = (hidden * mask).sum(1) / mask.sum(1)
    emb = torch.nn.functional.normalize(emb, dim=1)
    n = len(task.sub_questions)
    sims = (emb[n:] @ emb[:n].T).tolist()
    return {
        case["id"]: {sq.id: round(float(sims[i][j]), 4)
                     for j, sq in enumerate(task.sub_questions)}
        for i, case in enumerate(cases)
    }


def compute(task, cases, snapshots, sims, lex):
    """All statistics; pure function of (cases, snapshots, sims, lex)."""
    by_threshold = {}
    accepted_primary = None
    for t in THRESHOLDS:
        accepted = {cid: accept_rule(per, t) for cid, per in sims.items()}
        confusion, errors, _, accepted_levels = doc_level_report(cases, accepted)
        assert sum(accepted_levels.values()) == confusion["TP"] + confusion["FP"]
        by_threshold[str(t)] = {
            "confusion": confusion,
            "n_errors": len(errors),
            "accepted_gold_level_distribution": accepted_levels,
        }
        if t == PRIMARY_T:
            accepted_primary = accepted

    lex_errors = {(e["case"], e["subq"]) for e in lex["errors"]}
    sem_errors = {
        (e["case"], e["subq"])
        for e in doc_level_report(cases, accepted_primary)[1]
    }
    fixed, introduced = lex_errors - sem_errors, sem_errors - lex_errors

    pos, neg = [], []
    for case in cases:
        for sid, ann in case["doc_annotation"].items():
            (pos if ann["level"] in RELEVANT_LEVELS else neg).append(sims[case["id"]][sid])

    cases_by_id = {c["id"]: c for c in cases}
    snap_rows_by_t = {}
    for t in THRESHOLDS:
        accepted_t = {cid: accept_rule(per, t) for cid, per in sims.items()}
        snap_rows_by_t[str(t)] = [
            compare_with_annotation(
                task, *snapshot_verdict(task, cases_by_id, s["members"], accepted_t), s
            )
            for s in snapshots
        ]

    return {
        "model": MODEL_ID,
        "primary_threshold": PRIMARY_T,
        "threshold_note": "固定阈值均为探索性；仅用于同口径比较",
        "semantic_sims": sims,
        "separation": {
            "min_positive": min(pos), "max_negative": max(neg),
            "gap": round(min(pos) - max(neg), 4),
        },
        "by_threshold": by_threshold,
        "lex_confusion": lex["confusion"],
        "fixed_by_semantic": sorted(fixed),
        "new_errors_from_semantic": sorted(introduced),
        "snapshots_by_threshold": snap_rows_by_t,
        "snapshots": snap_rows_by_t[str(PRIMARY_T)],
    }


def build_report(task, cases, snapshots, results, lex) -> str:
    """Report text generated ONLY from data — no hardcoded statistics."""
    sims = results["semantic_sims"]
    bt = results["by_threshold"]
    pri = str(results["primary_threshold"])
    lex_err_n = len(lex["errors"])
    uncertain = [
        (c["id"], sid, ann)
        for c in cases for sid, ann in c["doc_annotation"].items()
        if ann.get("uncertain")
    ]

    lines = [
        "# P1-a 最小实验报告（固定案例集：词法基线 vs 语义模块）",
        "",
        f"- 案例集：{len(cases)} 案例（{sum(1 for c in cases if c['intent'] == 'real')} 条真实搜索结果标题与摘要"
        f" + {sum(1 for c in cases if c['intent'] != 'real')} 构造）× {len(task.sub_questions)} 子问题；"
        f"快照 {len(snapshots)} 个；标注状态：CANDIDATE（GLM 起草，未经核查，非金标准）",
        f"- 词法臂（现行生产逻辑，阈值 0.15/边际 0.6）：{lex['confusion']}"
        f"（接受 {lex['confusion']['TP'] + lex['confusion']['FP']} 对，"
        f"成色 {lex['accepted_gold_level_distribution']}）",
        f"- 语义臂（{results['model']}，主阈值 {results['primary_threshold']}，同一接受规则形状）："
        f"{bt[pri]['confusion']}"
        f"（接受 {bt[pri]['confusion']['TP'] + bt[pri]['confusion']['FP']} 对，"
        f"成色 {bt[pri]['accepted_gold_level_distribution']}）",
        f"- 免阈值分离度：min 正对 {results['separation']['min_positive']} − "
        f"max 负对 {results['separation']['max_negative']} = {results['separation']['gap']}",
        "- 探索性阈值对照："
        + "；".join(
            f"@{t} 接受 {bt[t]['confusion']['TP'] + bt[t]['confusion']['FP']}"
            f"（{bt[t]['accepted_gold_level_distribution']}，错 {bt[t]['n_errors']}）"
            for t in map(str, THRESHOLDS)
        ),
        "",
        "## 一、词法基线的具体误判（第一交付节点，数据驱动重述）",
        "",
        f"词法臂共 {lex_err_n} 处误判（FN {lex['confusion']['FN']} / FP {lex['confusion']['FP']}），"
        "逐条明细见 `report_node1.md`（由 run_baseline.py 同口径生成）。",
        "",
    ]
    if uncertain:
        lines.append(f"标注不确定性记录（{len(uncertain)} 条，人工核查优先项）：")
        for cid, sid, ann in uncertain:
            lines.append(f"- {cid}→{sid}（{ann['level']}）：{ann.get('uncertainty', '')}")
        lines.append("")

    lines += [
        "## 二、语义模块修正了哪些误判（第二交付节点）",
        "",
    ]
    lines += [f"- ✅ {c}/{s}" for c, s in results["fixed_by_semantic"]] or ["- （无）"]
    lines += [
        "",
        "## 三、语义模块引入的新错误",
        "",
    ]
    lines += [
        f"- ❌ {c}/{s}（词法判对，语义判错；相似度 {sims[c][s]}）"
        for c, s in results["new_errors_from_semantic"]
    ] or ["- （无）"]
    lines += [
        "",
        "## 四、对搜索决策（继续/调整/停止）的影响",
        "",
        "| 快照 | 词法 | " + " | ".join(f"语义@{t}" for t in THRESHOLDS) + " | 标注应为 |",
        "|---|" + "---|" * (len(THRESHOLDS) + 2),
    ]
    lex_snap = {r["snapshot"]: r for r in lex["snapshots"]}
    rows = results["snapshots_by_threshold"]
    for i, s in enumerate(snapshots):
        sid = s["id"]
        lx = lex_snap[sid]
        cells = [
            f"{rows[str(t)][i]['arm_stop_suggestion']}"
            f"({'✓' if rows[str(t)][i]['stop_decision_correct'] else '✗'})"
            for t in THRESHOLDS
        ]
        lines.append(
            f"| {sid} | {lx['arm_stop_suggestion']}({'✓' if lx['stop_decision_correct'] else '✗'}) "
            + " | ".join(cells)
            + f" | {rows[str(results['primary_threshold'])][i]['annotation_stop_should_be']} |"
        )

    def _acc(rs):
        return sum(1 for r in rs if r["stop_decision_correct"])

    lines += [
        "",
        f"停止建议正确率：词法 {_acc(lex['snapshots'])}/{len(snapshots)}；"
        + "、".join(f"语义@{t} {_acc(rows[str(t)])}/{len(snapshots)}" for t in THRESHOLDS)
        + "。",
        "",
        "## 五、仅靠语义相关性仍无法解决的充分性问题",
        "",
        "1. **冗余≠覆盖**：同质文档相似度同样高，成对相似度表达不了集合的边际信息量；",
        "2. **主题相似≠回答条件满足**：主题高度相似的文档可能不含子问题的关键回答要点；",
        "3. **相似度不构成充分性证明**：充分性仍需结构性证据（覆盖、多样性、关键条件）。",
        "",
        "## 口径与限定",
        "",
        "- 全部比较基于固定证据快照（静态，证据=标题与摘要），未做动态检索实验；",
        "- 案例集由 GLM 设计与候选标注（未经核查），结论用于定位问题而非性能宣称；",
        "- 语义阈值为探索性；模型为通用小型嵌入模型，未微调。",
    ]
    return "\n".join(lines)


def main() -> int:
    task, cases, snapshots = load()
    lex_path = HERE / "results/lexical_baseline.json"
    if not lex_path.exists():
        raise SystemExit("run run_baseline.py first (node 1 results required)")
    lex = json.loads(lex_path.read_text(encoding="utf-8"))

    sims = semantic_scores(task, cases)
    results = compute(task, cases, snapshots, sims, lex)
    results["experiment"] = "p1a-node2-semantic-comparison"
    results["date"] = "2026-10-24"
    results["annotation_status"] = "CANDIDATE（GLM 起草，待核查）"

    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "semantic_comparison.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    report = build_report(task, cases, snapshots, results, lex)
    (out_dir / "report.md").write_text(report, encoding="utf-8")
    print("written: results/semantic_comparison.json, results/report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
