"""Task B runner: compare sufficiency criteria vs lexical/semantic baselines
on the SAME fixed snapshots. Fully OFFLINE (criteria are lexical patterns).

Outputs results/sufficiency_comparison.json + results/sufficiency_report.md
(generated only from data; a consistency test re-generates the report).
The criteria are NOT wired into the P0 production controller.
"""

from __future__ import annotations

import json
from pathlib import Path

import sufficiency_criteria as sc
from common import load

HERE = Path(__file__).parent


def compute(task, cases, snapshots):
    cases_by_id = {c["id"]: c for c in cases}
    text_of = {c["id"]: f"{c['title']}\n{c['snippet']}" for c in cases}

    doc_rows = {}
    for case in cases:
        text = text_of[case["id"]]
        doc_rows[case["id"]] = {
            sq.id: sc.doc_level(text, sq.id) for sq in task.sub_questions
        }

    def run_variant(require_condition_met_doc):
        snap_rows = []
        for spec in snapshots:
            docs = [
                {"id": cid, "domain": cases_by_id[cid]["domain"], "text": text_of[cid]}
                for cid in spec["members"]
            ]
            subq_results = {
                sq.id: sc.snapshot_level(docs, sq.id,
                                         require_condition_met_doc=require_condition_met_doc)
                for sq in task.sub_questions
            }
            annotation_all = all(spec["sufficiency"][sq.id]["sufficient"]
                                 for sq in task.sub_questions)
            criteria_stop = all(r["sufficient"] for r in subq_results.values())
            snap_rows.append({
                "snapshot": spec["id"],
                "purpose": spec["purpose"],
                "criteria_stop_suggestion": "stop" if criteria_stop else "continue",
                "annotation_stop_should_be": "stop" if annotation_all else "continue",
                "stop_decision_correct": criteria_stop == annotation_all,
                "per_subq": {
                    sid: {
                        "sufficient": r["sufficient"],
                        "annotation_sufficient": spec["sufficiency"][sid]["sufficient"],
                        "match": r["sufficient"] == spec["sufficiency"][sid]["sufficient"],
                        "missing_points": r["missing_points"],
                        "condition_met_docs": r["condition_met_docs"],
                        "domains": r["domains"],
                        "redundant_docs": r["redundant_docs"],
                        "same_domain_redundancy": r["same_domain_redundancy"],
                        "reason": r["reason"],
                        "point_evidence": r["covered_points"],
                    }
                    for sid, r in subq_results.items()
                },
            })
        return snap_rows

    return {
        "doc_level": doc_rows,
        "v1_points_domains": run_variant(require_condition_met_doc=False),
        "v2_antisplit": run_variant(require_condition_met_doc=True),
        "snapshots": run_variant(require_condition_met_doc=True),
        "criteria_definition": sc.CRITERIA,
    }


def build_report(task, cases, snapshots, results, lex, sem) -> str:
    lines = [
        "# P1-a 任务 B：充分性判据最小验证（固定快照，三臂对比）",
        "",
        f"- 案例集：{len(cases)} 案例；快照 {len(snapshots)} 个；判据定义见 `sufficiency_criteria.py`（每子问题的必要回答要点 + 同义模式）",
        "- 判据规则：子问题充分 = 全部必要要点被覆盖 **且** 覆盖来源域 ≥2（独立信息贡献；同域重复只计一次并报告为冗余）",
        "- 判据未接入 P0 生产控制器；全部比较为静态固定快照口径（证据=标题与摘要）",
        "",
        "## 一、停止建议三臂对比（重点指标：错误停止）",
        "",
        "| 快照 | 词法 | 语义@0.5 | 判据 | 标注应为 |",
        "|---|---|---|---|---|",
    ]
    lex_snap = {r["snapshot"]: r for r in lex["snapshots"]}
    sem_snap = {r["snapshot"]: r for r in sem["snapshots"]}
    for row in results["snapshots"]:
        lx = lex_snap[row["snapshot"]]
        sm = sem_snap[row["snapshot"]]
        lines.append(
            f"| {row['snapshot']} | {lx['arm_stop_suggestion']}({'✓' if lx['stop_decision_correct'] else '✗'}) "
            f"| {sm['arm_stop_suggestion']}({'✓' if sm['stop_decision_correct'] else '✗'}) "
            f"| {row['criteria_stop_suggestion']}({'✓' if row['stop_decision_correct'] else '✗'}) "
            f"| {row['annotation_stop_should_be']} |"
        )

    def _acc(rows):
        return sum(1 for r in rows if r["stop_decision_correct"])

    n = len(results["snapshots"])
    lines += [
        "",
        f"停止建议正确率：词法 {_acc(lex['snapshots'])}/{n}；"
        f"语义@0.5 {_acc(sem['snapshots'])}/{n}；"
        f"判据 v1（要点+独立域）{_acc(results['v1_points_domains'])}/{n}；"
        f"**判据 v2（+防拼接）{_acc(results['v2_antisplit'])}/{n}**",
        "",
        "## 一之二、判据 v1 → v2 迭代记录（基于观察到的失误）",
        "",
        "| 快照 | v1 | v2 |",
        "|---|---|---|",
    ]
    v1 = {r["snapshot"]: r for r in results["v1_points_domains"]}
    for row in results["v2_antisplit"]:
        r1 = v1[row["snapshot"]]
        lines.append(
            f"| {row['snapshot']} | {r1['criteria_stop_suggestion']}"
            f"({'✓' if r1['stop_decision_correct'] else '✗'}) "
            f"| {row['criteria_stop_suggestion']}({'✓' if row['stop_decision_correct'] else '✗'}) |"
        )
    lines += [
        "",
        "v1 失误假设与核查：S3 起初疑似『跨文档要点拼接』（不同要点由不同文档分别覆盖）而增设 v2 防拼接条件；"
        "随后核查证据发现，S3/techniques 的判定实际由 e001 的完整摘要驱动——其文本含"
        "『vLLM, PagedAttention, and GQA manage it at scale』，自身完整覆盖两个要点。"
        "即 v2 判定有真实证据支撑，冲突更可能出在候选标注（起草于截断视图，见下节标注疑点）。"
        "v1/v2 在本轮快照上结果一致（防拼接条件未改变任何判定，其作用留待新案例检验）。"
        "每次针对已见结果的迭代都会加剧过拟合风险（见口径与限定第 1 条）。",
        "",
        "## 一之三、判据发现的标注疑点（交人工核查，本轮不擅改标注）",
        "",
    ]
    snap_specs = {s["id"]: s for s in snapshots}
    disputes = []
    for row in results["snapshots"]:
        spec = snap_specs[row["snapshot"]]
        for sid, sub in row["per_subq"].items():
            if not sub["match"]:
                disputes.append((row["snapshot"], sid, sub))
    for snap_id, sid, sub in disputes:
        ann = snap_specs[snap_id]["sufficiency"][sid]
        lines.append(
            f"- **{snap_id}/{sid}**：判据={'充分' if sub['sufficient'] else '不充分'}，"
            f"标注={'充分' if ann['sufficient'] else '不充分'}"
            + ("（标注已带 uncertain 标记）" if ann.get("uncertain") else "（标注未标记不确定——需补记）")
        )
        lines.append(f"  - 判据理由：{sub['reason']}")
        lines.append(f"  - 完整覆盖文档：{sub['condition_met_docs']}")
        if ann.get("uncertainty"):
            lines.append(f"  - 标注不确定性记录：{ann['uncertainty']}")
    if not disputes:
        lines.append("- （本轮无判据与标注冲突项）")
    lines += [
        "",
        "## 二、案例级判据分析（证据 / 缺口 / 理由，v2）",
        "",
    ]
    for row in results["snapshots"]:
        lines.append(f"### {row['snapshot']}（{row['purpose']}）")
        lines.append(f"- 判据停止建议：{row['criteria_stop_suggestion']}｜标注应为：{row['annotation_stop_should_be']}")
        spec = snap_specs[row["snapshot"]]
        for sid, sub in row["per_subq"].items():
            flag = "✓" if sub["match"] else "✗"
            ann = spec["sufficiency"][sid]
            mark = "⚠️标注存疑" if ann.get("uncertain") else ""
            lines.append(
                f"- {flag} **{sid}**：判据={'充分' if sub['sufficient'] else '不充分'}，"
                f"标注={'充分' if sub['annotation_sufficient'] else '不充分'}{mark}——{sub['reason']}"
            )
            if sub["missing_points"]:
                lines.append(f"  - 缺口：{sub['missing_points']}")
            for pid, evs in sub["point_evidence"].items():
                for ev in evs:
                    span = (ev["evidence"] or "")[:90]
                    lines.append(f"  - 证据 {pid}：{ev['doc']}（{ev['domain']}）「{span}」")
            if sub["same_domain_redundancy"]:
                lines.append(f"  - 同域冗余：{sub['same_domain_redundancy']}（重复覆盖只计一次独立贡献）")
        lines.append("")

    lines += [
        "## 三、口径与限定",
        "",
        "1. **过拟合风险（最重要）**：判据模式参考本轮案例集草拟，且 v2 规则经一次已见结果迭代；在上表的结果**不能外推**为通用性能，需在新任务/新案例上盲测验证。",
        "2. 模式粒度弱点（实测观察）：裸词 `vram` 即命中『量级与占用』要点（游戏显卡页因此被判 partial_points）；充分性判定由机制要点把关而未受影响，但文档层分类对此类词敏感。",
        "3. 判据是词面模式（同义感知），与语义相似度互补而非替代；要点未命中不代表文档不含该信息（摘要截断即可能丢失）。",
        "4. 标注为候选（CANDIDATE）：判据与标注的一致性部分源于同源设计；本轮已发现一处标注疑点（S3/techniques，见一之三节），人工核查仍是前置条件。",
        "5. 判据未接入 P0 生产控制器（任务书要求）；动态检索闭环中的行为未验证。",
    ]
    return "\n".join(lines)


def main() -> int:
    task, cases, snapshots = load()
    lex = json.loads((HERE / "results/lexical_baseline.json").read_text(encoding="utf-8"))
    sem = json.loads((HERE / "results/semantic_comparison.json").read_text(encoding="utf-8"))

    results = compute(task, cases, snapshots)
    results["experiment"] = "p1a-taskB-sufficiency-criteria"
    results["date"] = "2026-10-24"

    out = HERE / "results"
    out.mkdir(exist_ok=True)
    (out / "sufficiency_comparison.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (out / "sufficiency_report.md").write_text(
        build_report(task, cases, snapshots, results, lex, sem), encoding="utf-8"
    )
    for row in results["snapshots"]:
        print(f"{row['snapshot']}: criteria stop={row['criteria_stop_suggestion']} "
              f"correct={row['stop_decision_correct']}")
    print("written: results/sufficiency_comparison.json, results/sufficiency_report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
