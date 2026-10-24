"""Task 3 runner: sufficiency-criteria audit — frozen-rule validation on
fresh evidence + a fresh task, annotation sensitivity, deep-mechanism
distinction, independence analysis, three-layer evaluation. Fully OFFLINE.

Outputs results/freeze_validation.json + results/freeze_validation.md.
The frozen module sufficiency_criteria.py is imported, never modified.
"""

from __future__ import annotations

import json
from pathlib import Path

import criteria_audit as audit
import sufficiency_criteria as sc
from common import RELEVANT_LEVELS, load

HERE = Path(__file__).parent


# ---------------------------------------------------------------- helpers --
def _text(d):
    return f"{d['title']}\n{d['snippet']}"


def _fw_point_check(text, subq):
    """Point check for the new task using the frozen decision RULES with the
    pre-registered FRAMEWORKS_POINTS patterns (scoring logic reused)."""
    pts = audit.FRAMEWORKS_POINTS[subq]
    covered, evidence = {}, {}
    for pid, pats in pts.items():
        hit = None
        import re
        for p in pats:
            m = re.compile(p, re.IGNORECASE).search(text)
            if m:
                s, e = max(0, m.start() - 30), min(len(text), m.end() + 30)
                hit = "…" + text[s:e].replace("\n", " ") + "…"
                break
        covered[pid] = hit is not None
        if hit:
            evidence[pid] = hit
    return covered, evidence


# ------------------------------------------------------- 3.5 fresh validation --
def validate_fresh_kv():
    rows, agree_rel, agree_met = [], {"ok": 0, "bad": 0}, {"ok": 0, "bad": 0}
    for d in audit.FRESH_KV:
        if d["same_source"] or not d["annotation"]:
            continue  # dedup: same paper counted once
        text = _text(d)
        for subq, (level, basis) in d["annotation"].items():
            res = sc.doc_level(text, subq)
            gold_rel = level in RELEVANT_LEVELS
            pred_rel = res["class"] in {"partial_points", "condition_met"}
            gold_met = level == "sufficient_support"
            pred_met = res["class"] == "condition_met"
            agree_rel["ok" if gold_rel == pred_rel else "bad"] += 1
            agree_met["ok" if gold_met == pred_met else "bad"] += 1
            rows.append({
                "doc": d["id"], "subq": subq, "gold_level": level, "basis": basis,
                "pred_class": res["class"], "pred_points": res["covered_points"],
                "relevance_agree": gold_rel == pred_rel,
                "condition_met_agree": gold_met == pred_met,
                "evidence": res["evidence"],
            })
    return {"rows": rows, "relevance_agreement": agree_rel,
            "condition_met_agreement": agree_met}


def validate_fresh_task():
    rows, agree_rel = [], {"ok": 0, "bad": 0}
    for d in audit.FRESH_FW:
        text = _text(d)
        for subq, (level, basis) in d["annotation"].items():
            covered, evidence = _fw_point_check(text, subq)
            pred_rel = any(covered.values())
            gold_rel = level in RELEVANT_LEVELS
            agree_rel["ok" if gold_rel == pred_rel else "bad"] += 1
            rows.append({
                "doc": d["id"], "subq": subq, "gold_level": level, "basis": basis,
                "covered_points": [p for p, c in covered.items() if c],
                "relevance_agree": gold_rel == pred_rel,
                "evidence": evidence,
            })
    # mini-snapshot: does the biology collision trap produce a false sufficient?
    eco_docs = [
        {"id": d["id"], "domain": f"bio-{d['id']}", "text": _text(d)}
        for d in audit.FRESH_FW if d["id"] in {"n14", "n15", "n17"}
    ]
    eco_trap = []
    for d in eco_docs:
        covered, evidence = _fw_point_check(d["text"], "ecosystem")
        eco_trap.append({"doc": d["id"], "covered": [p for p, c in covered.items() if c],
                         "all_covered": all(covered.values()), "evidence": evidence})
    return {"rows": rows, "relevance_agreement": agree_rel, "eco_collision_trap": eco_trap}


# ------------------------------------------------ 3.1 sensitivity analysis --
def sensitivity(task, cases, snapshots):
    """Same arms, alternative REASONABLE annotations for the disputed
    techniques labels (S1/S3/S5: insufficient vs sufficient-per-e001)."""
    import run_sufficiency
    from common import accept_rule, lexical_scores, ABS_THRESHOLD

    scores = lexical_scores(task, cases)
    lex_acc = {cid: accept_rule({s: v["score"] for s, v in per.items()}, ABS_THRESHOLD)
               for cid, per in scores.items()}
    sem = json.loads((HERE / "results/semantic_comparison.json").read_text(encoding="utf-8"))
    sem_acc = {cid: accept_rule(per, 0.5) for cid, per in sem["semantic_sims"].items()}

    out = {}
    for variant, flip in (("A-原标注", False), ("B-替代标注(e001 佐证下 techniques 充分)", True)):
        rows = []
        for spec in snapshots:
            suff = {sid: dict(v) for sid, v in spec["sufficiency"].items()}
            if flip and spec["id"] in {"S1-homogeneous-definition",
                                       "S3-real-after-round2", "S5-missing-condition"}:
                suff["techniques"]["sufficient"] = True
            ann_stop = all(v["sufficient"] for v in suff.values())
            arms = {}
            for name, acc in (("lexical", lex_acc), ("semantic", sem_acc)):
                stop = all(
                    sum(1 for cid in spec["members"] if acc[cid].get(sq.id)) >= task.min_relevant_per_subq
                    for sq in task.sub_questions
                )
                arms[name] = {"stop": "stop" if stop else "continue", "correct": stop == ann_stop}
            crit = next(r for r in run_sufficiency.compute(task, cases, snapshots)["v2_antisplit"]
                        if r["snapshot"] == spec["id"])
            crit_stop = crit["criteria_stop_suggestion"] == "stop"
            arms["criteria"] = {"stop": crit["criteria_stop_suggestion"],
                                "correct": crit_stop == ann_stop}
            rows.append({"snapshot": spec["id"], "annotation_stop": "stop" if ann_stop else "continue",
                         **arms})
        out[variant] = {
            "rows": rows,
            "accuracy": {arm: sum(1 for r in rows if r[arm]["correct"]) for arm in ("lexical", "semantic", "criteria")},
        }
    return out


# ---------------------------------------- 3.2/3.3/3.4 audit of frozen runs --
def layered_audit(task, cases, snapshots):
    """Three layers: doc-level point hits / subq sufficiency / task stop;
    plus name-hit vs mechanism-explanation and domain-diversity analysis."""
    results = json.loads((HERE / "results/sufficiency_comparison.json").read_text(encoding="utf-8"))
    cases_by_id = {c["id"]: c for c in cases}
    text_of = {c["id"]: _text(c) for c in cases}

    # 3.2 techniques: name hit vs mechanism explanation (doc level)
    mech_rows = []
    for cid, case in cases_by_id.items():
        if not cid.startswith("e") and cid not in {"H-syn-tech"}:
            continue
        text = text_of[cid]
        dl = sc.doc_level(text, "techniques")
        if dl["class"] in {"partial_points", "condition_met"}:
            mech_rows.append({
                "doc": cid, "criteria_class": dl["class"],
                "name_hit": True,  # in techniques P1 by construction
                "mechanism_explained": audit.has_mechanism_explanation(text),
                "annotation": case["doc_annotation"]["techniques"]["level"],
            })

    # 3.3 domain diversity vs independence, per snapshot/subq (S6 focus)
    indep_rows = []
    for spec in snapshots:
        docs = [{"id": c, "domain": cases_by_id[c]["domain"], "text": text_of[c]}
                for c in spec["members"]]
        for sq in task.sub_questions:
            r = sc.snapshot_level(docs, sq.id)
            if not r["covered_points"]:
                continue
            per_point_domains = {
                p: sorted({e["domain"] for e in evs})
                for p, evs in r["covered_points"].items()
            }
            all_points_same_domain_single = (
                len({tuple(v) for v in per_point_domains.values()}) == 1
                and len(next(iter(per_point_domains.values()))) == 1
            )
            complementary = len(per_point_domains) > 1 and any(
                set(per_point_domains[p1]) - set(per_point_domains[p2])
                for p1 in per_point_domains for p2 in per_point_domains if p1 != p2
            )
            indep_rows.append({
                "snapshot": spec["id"], "subq": sq.id, "sufficient": r["sufficient"],
                "domains": r["domains"], "per_point_domains": per_point_domains,
                "structure": ("single_source" if all_points_same_domain_single
                              else "complementary" if complementary else "corroborative"),
                "redundant_docs": r["redundant_docs"],
                "same_domain_redundancy": r["same_domain_redundancy"],
            })
    return {"mechanism_rows": mech_rows, "independence_rows": indep_rows,
            "three_layers": {
                "doc_level": "见 results/sufficiency_comparison.json 的 doc_level（逐文档逐子问题要点命中）",
                "subq_level": "见 snapshots[].per_subq（充分性 + 证据 + 缺口 + 理由）",
                "task_level": "见 snapshots[].criteria_stop_suggestion（三臂对比于 sufficiency_report.md）",
            }}


# ---------------------------------------------------------------- report --
def build_report(kv_val, fw_val, sens, layered) -> str:
    kv_rel, kv_met = kv_val["relevance_agreement"], kv_val["condition_met_agreement"]
    fw_rel = fw_val["relevance_agreement"]
    lines = [
        "# P1-a 任务 3：充分性判据核查（冻结规则盲测 + 敏感性 + 分层审计）",
        "",
        "**冻结协议**：`sufficiency_criteria.py` 全程零修改；新任务要点仅依据其任务文件子问题文本与 keywords 起草并先行登记（`criteria_audit.py`），之后才对新证据做候选标注。",
        "",
        "## 1. 冻结规则 × 同任务新证据（2 个新查询、去同源后 5 篇，标注 CANDIDATE）",
        "",
        f"- 相关性层（partial 及以上算相关）一致性：{kv_rel['ok']}/{kv_rel['ok'] + kv_rel['bad']}",
        f"- 充分支持层（condition_met）一致性：{kv_met['ok']}/{kv_met['ok'] + kv_met['bad']}",
        "",
        "逐条：",
        "",
    ]
    for r in kv_val["rows"]:
        lines.append(
            f"- {r['doc']}/{r['subq']}：gold={r['gold_level']}，冻结判定={r['pred_class']}"
            f"（命中 {r['pred_points']}），相关层{'✓' if r['relevance_agree'] else '✗'}，"
            f"充分层{'✓' if r['condition_met_agree'] else '✗'}——{r['basis']}"
        )
    lines += [
        "",
        "## 2. 冻结方法 × 新任务（python_web_frameworks，10 篇未用真实结果，含跨域陷阱）",
        "",
        f"- 相关性层一致性：{fw_rel['ok']}/{fw_rel['ok'] + fw_rel['bad']}",
        "",
        "**跨域主题碰撞陷阱实测**：生物学 ecosystem 页面对 ecosystem 子问题——",
        "",
    ]
    for t in fw_val["eco_collision_trap"]:
        lines.append(f"- {t['doc']}：命中要点 {t['covered']}，全部要点命中={t['all_covered']}")
    lines += [
        "",
        "## 3. 敏感性分析（任务 3.1：S1/S3/S5 的 techniques 标注争议）",
        "",
        "S1/S3/S5 的 techniques 候选标注（不充分）与判据（充分，由 e001 完整摘要证据驱动）冲突，",
        "两种合理标注下各臂停止正确率（/5）：",
        "",
        "| 变体 | 词法 | 语义@0.5 | 判据 |",
        "|---|---|---|---|",
    ]
    for variant, data in sens.items():
        a = data["accuracy"]
        lines.append(f"| {variant} | {a['lexical']}/5 | {a['semantic']}/5 | {a['criteria']}/5 |")
    lines += [
        "",
        "## 4. 名称命中 vs 作用机制解释（任务 3.2，techniques 文档层）",
        "",
        "| 文档 | 判据分类 | 机制解释（audit 层） | 候选标注 |",
        "|---|---|---|---|",
    ]
    for m in layered["mechanism_rows"]:
        lines.append(f"| {m['doc']} | {m['criteria_class']} | {'✓' if m['mechanism_explained'] else '✗'} | {m['annotation']} |")
    lines += [
        "",
        "## 5. 来源域多样性 vs 独立佐证（任务 3.3，快照结构分类）",
        "",
        "结构分类：single_source（全部要点同一域）/ complementary（不同域覆盖不同要点）/ corroborative（多域重复覆盖同要点组合）。",
        "域名计数是独立性的弱代理——同域多文档只计一次，但不同域也可能内容抄袭（本轮无法检测）。",
        "",
        "| 快照/子问题 | 结构 | 域 | 判定 |",
        "|---|---|---|---|",
    ]
    for r in layered["independence_rows"]:
        lines.append(
            f"| {r['snapshot']}/{r['subq']} | {r['structure']} | {len(r['domains'])} | "
            f"{'充分' if r['sufficient'] else '不充分'} |"
        )
    lines += [
        "",
        "## 6. 三层评价分离（任务 3.4）",
        "",
        "- 文档层（要点命中）：`results/sufficiency_comparison.json` doc_level——逐文档逐子问题的要点命中与证据；",
        "- 子问题层（充分性）：snapshots[].per_subq——要点覆盖、缺口、独立域、理由；",
        "- 任务层（停止决策）：snapshots[].criteria_stop_suggestion——三臂对比见 `sufficiency_report.md`。",
        "三层错误可分别发生：文档层误命中（如裸词 vram）不必然传导为子问题层误判（机制要点把关），",
        "子问题层误判（如跨域碰撞）在任务层可能被其他子问题的缺口掩盖——分层报告使各层错误可归因。",
        "",
        "## 7. 结论与退化（如实）",
        "",
        "1. 同任务新证据：相关性层基本保持，充分层出现退化——新增长关系动词（eats）、",
        "   名词化表述（reduction 不含子串 reduce）未入冻结模式，f02/f06 判 partial 而候选标注为充分支持；",
        "2. 新任务：框架对比正例可用，但**裸词 ecosystem/community 的跨域碰撞陷阱实测成立**",
        "（生物学页面命中全部要点）——冻结协议从子问题文本起草要点时，主题词即碰撞源；",
        "3. 敏感性：判据与词法的相对优劣在不同合理标注下是否翻转见第 3 节表（如实呈现，不选边）；",
        "4. 机制解释层：名称命中≠机制解释（多数 techniques 文档无机制解释），该区分已可观测（第 4 节）。",
    ]
    return "\n".join(lines)


def main() -> int:
    task, cases, snapshots = load()
    kv_val = validate_fresh_kv()
    fw_val = validate_fresh_task()
    sens = sensitivity(task, cases, snapshots)
    layered = layered_audit(task, cases, snapshots)

    results = {
        "experiment": "p1a-task3-criteria-audit",
        "date": "2026-10-24",
        "frozen_module_untouched": True,
        "fresh_kv": kv_val,
        "fresh_task": fw_val,
        "sensitivity": sens,
        "layered": layered,
    }
    (HERE / "results/freeze_validation.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    (HERE / "results/freeze_validation.md").write_text(
        build_report(kv_val, fw_val, sens, layered), encoding="utf-8")

    print("fresh-kv relevance:", kv_val["relevance_agreement"],
          "| condition_met:", kv_val["condition_met_agreement"])
    print("fresh-task relevance:", fw_val["relevance_agreement"])
    print("eco trap:", [(t["doc"], t["all_covered"]) for t in fw_val["eco_collision_trap"]])
    for v, d in sens.items():
        print("sensitivity", v, d["accuracy"])
    print("written: results/freeze_validation.json, results/freeze_validation.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
