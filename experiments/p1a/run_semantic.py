"""P1-a node 2: minimal semantic comparison on the SAME case set and criteria.

Cosine similarity (all-MiniLM-L6-v2, from local HF cache) between the
sub-question TEXT and the document (title + snippet), fed into the SAME
accept-rule shape and the SAME production snapshot evaluator as the lexical
arm. Primary threshold 0.5 is EXPLORATORY (also reported at 0.4/0.6).

Explicit limits (per task spec): similarity is a relevance proxy; it must
never be presented as proof of evidence sufficiency.
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


def main() -> int:
    task, cases, snapshots = load()
    lex_path = HERE / "results/lexical_baseline.json"
    if not lex_path.exists():
        raise SystemExit("run run_baseline.py first (node 1 results required)")
    lex = json.loads(lex_path.read_text(encoding="utf-8"))

    sims = semantic_scores(task, cases)

    # doc-level per threshold; primary = 0.5
    by_threshold = {}
    accepted_primary = None
    for t in THRESHOLDS:
        accepted = {
            cid: accept_rule(per, t) for cid, per in sims.items()
        }
        confusion, errors, _, accepted_levels = doc_level_report(cases, accepted)
        by_threshold[str(t)] = {
            "confusion": confusion, "n_errors": len(errors), "errors": errors,
            "accepted_gold_level_distribution": accepted_levels,
        }
        if t == PRIMARY_T:
            accepted_primary = accepted

    lex_errors = {(e["case"], e["subq"]) for e in lex["errors"]}
    sem_errors = {(e["case"], e["subq"]) for e in by_threshold[str(PRIMARY_T)]["errors"]}
    fixed = lex_errors - sem_errors
    introduced = sem_errors - lex_errors

    # separation (threshold-free), relevance cut
    pos, neg = [], []
    for case in cases:
        for sid, ann in case["doc_annotation"].items():
            if ann["level"] in RELEVANT_LEVELS:
                pos.append(sims[case["id"]][sid])
            else:
                neg.append(sims[case["id"]][sid])

    # snapshot-level at every exploratory threshold (robustness of the
    # stop-suggestion conclusion across thresholds)
    cases_by_id = {c["id"]: c for c in cases}
    snap_rows_by_t = {}
    for t in THRESHOLDS:
        accepted_t = {cid: accept_rule(per, t) for cid, per in sims.items()}
        rows = []
        for snap_spec in snapshots:
            snap, assessment = snapshot_verdict(task, cases_by_id, snap_spec["members"], accepted_t)
            rows.append(compare_with_annotation(task, snap, assessment, snap_spec))
        snap_rows_by_t[str(t)] = rows
    snap_rows = snap_rows_by_t[str(PRIMARY_T)]

    results = {
        "experiment": "p1a-node2-semantic-comparison",
        "date": "2026-10-24",
        "model": MODEL_ID,
        "primary_threshold": PRIMARY_T,
        "threshold_note": "固定阈值均为探索性；仅用于同口径比较，不构成生产建议",
        "annotation_status": "CANDIDATE（GLM 起草，待核查）",
        "semantic_sims": sims,
        "separation": {
            "min_positive": min(pos), "max_negative": max(neg),
            "gap": round(min(pos) - max(neg), 4),
        },
        "by_threshold": {t: {"confusion": v["confusion"], "n_errors": v["n_errors"]}
                         for t, v in by_threshold.items()},
        "lex_confusion": lex["confusion"],
        "sem_confusion_primary": by_threshold[str(PRIMARY_T)]["confusion"],
        "fixed_by_semantic": sorted(fixed),
        "new_errors_from_semantic": sorted(introduced),
        "snapshots": snap_rows,
        "snapshots_by_threshold": snap_rows_by_t,
    }
    (HERE / "results/semantic_comparison.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    # ---- combined report (node 1 + node 2) --------------------------------
    lines = [
        "# P1-a 最小实验报告（固定案例集：词法基线 vs 语义模块）",
        "",
        f"- 案例集：{len(cases)} 案例（15 真实 + 5 构造）×3 子问题；标注状态：CANDIDATE（GLM 起草，未经核查，非金标准）",
        f"- 词法臂（现行生产逻辑，阈值 0.15/边际 0.6）：{lex['confusion']}",
        f"- 语义臂（{MODEL_ID}，主阈值 {PRIMARY_T}，同一接受规则形状）：{results['sem_confusion_primary']}",
        f"- 免阈值分离度：min 正对 {min(pos)} − max 负对 {max(neg)} = {results['separation']['gap']}",
        f"- 探索性阈值对照：{results['by_threshold']}",
        "",
        "## 一、词法基线的具体误判（第一交付节点）",
        "",
        f"共 {len(lex['errors'])} 处（FN {lex['confusion']['FN']} / FP {lex['confusion']['FP']}），按模式归纳：",
        "",
        "1. **系统性跨子问题误归属（真实数据新发现，11 处 FP/FN）**：7 条真实证据（e008–e014）被误判为 definition 相关；其中 e011/e012（技术综述）同时漏判 techniques——definition 子问题词表最宽（kv cache/attention/inference 等），任何提及这些词的文档都能通过相对边际规则被归给 definition。",
        "2. **同义改写/行话漏检（B/E/H 构造复现 + 真实 e014）**：compression/sharing heads/memoize 等表述与关键词无词面重叠，词法分 0.02–0.15。",
        "3. **主题词重叠伪相关（C 构造复现 + 真实）**：游戏显卡 VRAM 页被判为 cost 相关（0.231）。",
        "4. **错误停止建议（快照 S2 复现）**：伪相关文档把 cost 覆盖推过 K=2，评价器输出 sufficient/stop，而候选标注为 cost 关键信息不足——即词法误判会传导为元认知层的错误停止。",
        "5. **覆盖计数无法区分冗余（快照 S1）**：5 篇同质入门文与同一论文 html/pdf 双版本均被计入覆盖。",
        "",
        "## 二、语义模块修正了哪些误判（第二交付节点）",
        "",
    ]
    fixed_rows = [f"- ✅ {c}/{s}" for c, s in sorted(fixed)]
    lines += fixed_rows or ["- （无）"]
    lines += [
        "",
        "## 三、语义模块引入的新错误",
        "",
    ]
    intro_rows = []
    for c, s in sorted(introduced):
        intro_rows.append(f"- ❌ {c}/{s}（词法判对，语义判错；相似度 {sims[c][s]}）")
    lines += intro_rows or ["- （无）"]
    lines += [
        "",
        "## 四、对搜索决策（继续/调整/停止）的影响",
        "",
        "| 快照 | 词法 | 语义@0.4 | 语义@0.5 | 语义@0.6 | 标注应为 |",
        "|---|---|---|---|---|---|",
    ]
    lex_snap = {r["snapshot"]: r for r in lex["snapshots"]}
    for i, r in enumerate(snap_rows):
        lx = lex_snap[r["snapshot"]]
        cells = []
        for t in THRESHOLDS:
            rt = snap_rows_by_t[str(t)][i]
            cells.append(f"{rt['arm_stop_suggestion']}({'✓' if rt['stop_decision_correct'] else '✗'})")
        lines.append(
            f"| {r['snapshot']} | {lx['arm_stop_suggestion']}({'✓' if lx['stop_decision_correct'] else '✗'}) "
            f"| {cells[0]} | {cells[1]} | {cells[2]} | {r['annotation_stop_should_be']} |"
        )

    def _acc(rows):
        return sum(1 for r in rows if r["stop_decision_correct"])

    lines += [
        "",
        f"停止建议正确率：词法 {_acc(lex['snapshots'])}/{len(snap_rows)}；"
        + "、".join(
            f"语义@{t} {_acc(snap_rows_by_t[str(t)])}/{len(snap_rows)}" for t in THRESHOLDS
        )
        + "。结论：在本案例集与全部测试阈值下，朴素语义臂的停止建议均不优于词法基线；"
        "S2（伪相关覆盖）与 S3（真实运行第 2 轮状态）在所有阈值下均被错误判为可停止。",
    ]
    lines += [
        "",
        "## 五、仅靠语义相关性仍无法解决的充分性问题",
        "",
        "1. **冗余≠覆盖（S1）**：同质文档与正确文档的相似度同样高，语义覆盖计数同样被冗余推高；集合层面的边际信息量不是成对相似度能表达的。",
        "2. **主题相似≠回答条件满足（S5/CALC）**：用量计算器与 cost 子问题主题高度相似，但『为何增长』的机制信息缺失——语义相关性无法检验集合是否包含关键回答条件。",
        "3. **相似度不构成充分性证明**：按任务规范，任何基于相似度/更高 score 的充分性宣称均不成立；充分性判断仍需结构性证据（覆盖、多样性、关键条件清单）。",
        "",
        "## 口径与限定",
        "",
        "- 全部比较基于固定证据快照（静态），未做动态检索实验；动态实验是否进行由 GPT 决定。",
        "- 案例集由 GLM 设计与标注（候选），未经人工核查，结论用于定位问题而非性能宣称。",
        "- 语义阈值为探索性；模型为通用小型嵌入模型，未针对本域微调。",
    ]
    (HERE / "results/report.md").write_text("\n".join(lines), encoding="utf-8")

    print("separation:", results["separation"])
    print("lex errors:", len(lex_errors), "| sem(0.5) errors:", len(sem_errors),
          "| fixed:", len(fixed), "| new:", len(introduced))
    print("fixed:", sorted(fixed))
    print("new:  ", sorted(introduced))
    for r in snap_rows:
        print(f"  snapshot {r['snapshot']}: semantic verdict={r['arm_verdict']} "
              f"stop={r['arm_stop_suggestion']} correct={r['stop_decision_correct']}")
    print("written: results/semantic_comparison.json, results/report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
