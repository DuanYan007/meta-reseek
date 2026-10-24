"""P1-a node 1: lexical baseline on the fixed case set (fully OFFLINE).

Outputs experiments/p1a/results/lexical_baseline.json and
results/report_node1.md. No model, no network.
"""

from __future__ import annotations

import json
from pathlib import Path

from common import (ABS_THRESHOLD, accept_rule, compare_with_annotation,
                    doc_level_report, lexical_scores, load,
                    snapshot_verdict)

HERE = Path(__file__).parent


def main() -> int:
    task, cases, snapshots = load()
    scores = lexical_scores(task, cases)
    accepted = {
        cid: accept_rule({sid: v["score"] for sid, v in per.items()}, ABS_THRESHOLD)
        for cid, per in scores.items()
    }
    confusion, errors, corrects = doc_level_report(cases, accepted)

    cases_by_id = {c["id"]: c for c in cases}
    snap_rows = []
    for snap_spec in snapshots:
        snap, assessment = snapshot_verdict(task, cases_by_id, snap_spec["members"], accepted)
        snap_rows.append(compare_with_annotation(task, snap, assessment, snap_spec))

    results = {
        "experiment": "p1a-node1-lexical-baseline",
        "date": "2026-10-24",
        "annotation_status": "CANDIDATE（GLM 起草，待核查）",
        "n_cases": len(cases),
        "n_pairs": sum(len(c["doc_annotation"]) for c in cases),
        "confusion": confusion,
        "errors": errors,
        "scores": {
            cid: {sid: {"score": round(v["score"], 3), "matched": v["matched"], "missing_terms": v["missing"]}
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

    lines = [
        "# P1-a 第一交付节点：词法基线在固定案例集上的误判记录",
        "",
        f"- 案例集：{len(cases)} 案例（15 真实检索结果 + 5 构造），来源与候选标注见 cases.json",
        f"- 标注状态：{results['annotation_status']}",
        f"- 文档层混淆矩阵：{confusion}（共 {results['n_pairs']} 对）",
        "",
        "## 文档层误判明细（含词法命中/缺失词条，供误因分析）",
        "",
    ]
    for e in errors:
        detail = results["scores"][e["case"]][e["subq"]]
        lines.append(
            f"- [{e['intent']}] {e['case']} → {e['subq']}：gold={e['gold']} pred={e['pred']}，"
            f"词法分 {detail['score']}；命中词条 {detail['matched']}；缺失 {detail['missing_terms'][:6]}"
        )
        lines.append(f"  - 标注依据：{e['annotation_basis']}")
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
                    f"（{row['accepted_count']} 条），标注={ '充分' if row['annotation_sufficient'] else '不充分'}——{row['annotation_basis']}"
                )
    (out_dir / "report_node1.md").write_text("\n".join(lines), encoding="utf-8")

    print("confusion:", confusion)
    for e in errors:
        print(f"  [{e['intent']}:{'FN' if e['gold'] else 'FP'}] {e['case']} -> {e['subq']}")
    for r in snap_rows:
        print(f"  snapshot {r['snapshot']}: verdict={r['arm_verdict']} stop_correct={r['stop_decision_correct']}")
    print("written: results/lexical_baseline.json, results/report_node1.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
