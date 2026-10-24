"""P1-a node 1: lexical baseline on the fixed case set (fully OFFLINE).

Outputs experiments/p1a/results/lexical_baseline.json and
results/report_node1.md. The report is generated from data only
(build_report); a consistency test re-generates it and compares with the
committed file.
"""

from __future__ import annotations

import json
from pathlib import Path

from common import (ABS_THRESHOLD, accept_rule, compare_with_annotation,
                    doc_level_report, lexical_scores, load,
                    snapshot_verdict)

HERE = Path(__file__).parent


def compute(task, cases, snapshots):
    scores = lexical_scores(task, cases)
    accepted = {
        cid: accept_rule({sid: v["score"] for sid, v in per.items()}, ABS_THRESHOLD)
        for cid, per in scores.items()
    }
    confusion, errors, corrects, accepted_levels = doc_level_report(cases, accepted)
    assert sum(accepted_levels.values()) == confusion["TP"] + confusion["FP"]

    cases_by_id = {c["id"]: c for c in cases}
    snap_rows = []
    for snap_spec in snapshots:
        snap, assessment = snapshot_verdict(task, cases_by_id, snap_spec["members"], accepted)
        snap_rows.append(compare_with_annotation(task, snap, assessment, snap_spec))
    return scores, accepted, confusion, errors, corrects, accepted_levels, snap_rows


def build_report(task, cases, snapshots, scores, confusion, errors, accepted_levels, snap_rows) -> str:
    n_real = sum(1 for c in cases if c["intent"] == "real")
    lines = [
        "# P1-a 第一交付节点：词法基线在固定案例集上的误判记录（四级标注修订版）",
        "",
        f"- 案例集：{len(cases)} 案例（{n_real} 条真实搜索结果标题与摘要 + {len(cases) - n_real} 构造，"
        "同源 e012 已并入 e011），来源与候选标注见 cases.json",
        f"- 标注状态：CANDIDATE（GLM 起草，待核查）；四级标准，二值切点=partial 及以上",
        f"- 文档层混淆矩阵（相关性切点）：{confusion}"
        f"（共 {sum(len(c['doc_annotation']) for c in cases)} 对）",
        f"- 词法接受项的真实级别分布：{accepted_levels}（接受但仅 topic_only 的即伪相关）",
        "",
        "## 文档层误判明细（含词法命中/缺失词条，供误因分析）",
        "",
    ]
    for e in errors:
        detail = scores[e["case"]][e["subq"]]
        lines.append(
            f"- [{e['intent']}] {e['case']} → {e['subq']}：gold={e['gold_level']} pred={e['pred']}，"
            f"词法分 {round(detail['score'], 3)}；命中词条 {detail['matched']}；缺失 {detail['missing'][:6]}"
        )
        lines.append(f"  - 标注依据：{e['annotation_basis']}")
    uncertain = [
        (c["id"], sid, ann)
        for c in cases for sid, ann in c["doc_annotation"].items()
        if ann.get("uncertain")
    ]
    if uncertain:
        lines += ["", f"## 标注不确定性记录（{len(uncertain)} 条，人工核查优先项）", ""]
        for cid, sid, ann in uncertain:
            lines.append(f"- {cid}→{sid}（{ann['level']}）：{ann.get('uncertainty', '')}")
    lines += [
        "",
        "## 快照层停止建议 vs 候选充分性标注",
        "",
        "| 快照 | 评价器判定 | 停止建议 | 标注应为 | 判定正确 |",
        "|---|---|---|---|---|",
    ]
    for r in snap_rows:
        lines.append(
            f"| {r['snapshot']} | {r['arm_verdict']}({r['arm_score']}) | {r['arm_stop_suggestion']} "
            f"| {r['annotation_stop_should_be']} | {'✅' if r['stop_decision_correct'] else '❌'} |"
        )
    lines += ["", "## 子问题层覆盖误判（快照内）", ""]
    for r in snap_rows:
        for sid, row in r["per_subq"].items():
            if not row["match"]:
                lines.append(
                    f"- {r['snapshot']}/{sid}：评价器认为{'已覆盖' if row['arm_says_covered'] else '未覆盖'}"
                    f"（{row['accepted_count']} 条），标注={'充分' if row['annotation_sufficient'] else '不充分'}"
                    f"——{row['annotation_basis']}"
                )
    return "\n".join(lines)


def main() -> int:
    task, cases, snapshots = load()
    (scores, accepted, confusion, errors,
     corrects, accepted_levels, snap_rows) = compute(task, cases, snapshots)

    results = {
        "experiment": "p1a-node1-lexical-baseline",
        "date": "2026-10-24",
        "annotation_status": "CANDIDATE（GLM 起草，待核查）",
        "annotation_scale_note": "四级标准：irrelevant/topic_only/partial/sufficient_support；二值相关性切点=partial 及以上",
        "evidence_scope": "真实案例=搜索结果标题与摘要；静态固定快照口径",
        "n_cases": len(cases),
        "n_pairs": sum(len(c["doc_annotation"]) for c in cases),
        "confusion": confusion,
        "accepted_gold_level_distribution": accepted_levels,
        "errors": errors,
        "scores": {
            cid: {sid: {"score": round(v["score"], 3), "matched": v["matched"],
                        "missing_terms": v["missing"]}
                  for sid, v in per.items()}
            for cid, per in scores.items()
        },
        "snapshots": snap_rows,
    }
    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "lexical_baseline.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (out_dir / "report_node1.md").write_text(
        build_report(task, cases, snapshots, scores, confusion, errors,
                     accepted_levels, snap_rows),
        encoding="utf-8",
    )
    print("confusion:", confusion, "| accepted levels:", accepted_levels)
    for e in errors:
        kind = "FN" if e["gold_relevant"] else "FP"
        print(f"  [{e['intent']}:{kind}] {e['case']} -> {e['subq']} (gold={e['gold_level']})")
    for r in snap_rows:
        print(f"  snapshot {r['snapshot']}: verdict={r['arm_verdict']} stop_correct={r['stop_decision_correct']}")
    print("written: results/lexical_baseline.json, results/report_node1.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
