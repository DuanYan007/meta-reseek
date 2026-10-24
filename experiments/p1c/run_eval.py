"""P1-c evaluation harness (frozen tasks -> run -> metrics -> report).

冻结协议：评测集（eval_tasks.json，含预期）先行提交；本脚本只读取该文件。
- mock 类：脚本化 Provider（支持 final_error/retries 模拟），完全离线确定性；
- cache-replay 类：真实任务的离线缓存回放（CachedProvider offline）；
  本机缓存缺失时该任务记 skipped-no-cache，不参与汇总，不与 mock 混算。

六类指标（任务书第三节）：
1. 停止决策与预期一致性；2. 检索轮数与查询去重；3. 证据采纳与覆盖变化；
4. 通道故障归因（error/retries 区分 + 停止理由归因）；5. 关键回答条件缺口
   （仅对声明 key_conditions 的任务，用 P1-a 冻结判据做**评测期分析**，不接入生产）；
6. 决策轨迹与三层 Memory 溯源（WorkingMemory 快照 / EpisodicMemory 投影 /
   LongTermMemory ingest+reconcile fully_verified）。

口径：全部一致性指标针对冻结预期（CANDIDATE）与控制器规则行为；
不将词法 score、helpful 代理或候选标签一致率称为真实答案质量。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "experiments/p1a"))

from meta_reseek.memory import EpisodicMemory, LongTermMemory, WorkingMemory
from meta_reseek.memory.episodic import episodes_from_log
from meta_reseek.metacog.controller import MetacognitiveController
from meta_reseek.search.base import SearchHit
from meta_reseek.search.cache import CachedProvider, FileCache
from meta_reseek.search.ddg import DdgProvider
from meta_reseek.task import SubQuestion, TaskSpec


class ScriptedProvider:
    """按 eval_tasks 的 script 声明返回命中，并模拟通道状态。"""

    name = "scripted"

    def __init__(self, script: list[dict]):
        self.script = script
        self.last_error = None
        self.last_retries = 0

    def search(self, query: str, max_results: int = 5):
        for entry in self.script:
            if entry["match"] == "*" or entry["match"].lower() in query.lower():
                self.last_error = "scripted final failure" if entry.get("final_error") else None
                self.last_retries = 0 if entry.get("final_error") else int(entry.get("retries", 0))
                hits = [SearchHit(h["title"], h["url"], h["snippet"])
                        for h in entry.get("hits", [])][:max_results]
                return hits
        return []


def _spec_task(spec: dict) -> TaskSpec:
    t = spec["task"]
    return TaskSpec(
        name=t["name"], question=t["question"], seed_query=t["seed_query"],
        sub_questions=[SubQuestion(s["id"], s["text"], s.get("keywords", []),
                                   s.get("alt_queries", []))
                       for s in t["sub_questions"]],
        min_relevant_per_subq=t.get("min_relevant_per_subq", 2),
        max_rounds=t.get("max_rounds", 5),
    )


def _run_scenario(spec: dict, cache_dir: Path | None = None):
    if spec["class"] == "mock":
        task = _spec_task(spec)
        provider = ScriptedProvider(spec["script"])
    else:
        task = TaskSpec.from_yaml(REPO / spec["task_file"])
        provider = CachedProvider(DdgProvider(),
                                  FileCache(cache_dir or (REPO / "artifacts/cache")),
                                  mode="offline")
    log = MetacognitiveController(task, provider).run()
    return task, log


def _evaluate(spec: dict, task: TaskSpec, log) -> dict:
    records = log.as_dict()
    search_rounds = [r for r in records["rounds"] if r["decision"] == "search"]
    queries = [r["action"]["query"] for r in search_rounds if r["action"]]
    stop_decision = records["summary"]["stop_decision"]
    stop_reason = next((r["decision_reason"] for r in reversed(records["rounds"])
                        if r["decision"].startswith("stop")), "")
    fb_rounds = [r for r in search_rounds if r["feedback"]]

    m = {
        "id": spec["id"], "class": spec["class"], "purpose": spec["purpose"],
        "conditions": spec["conditions"],
        # 1. 停止一致性
        "expected_stop": spec["expected_stop"], "actual_stop": stop_decision,
        "stop_consistent": stop_decision == spec["expected_stop"],
        "rounds_searched": len(search_rounds),
        "rounds_consistent": (len(search_rounds) == spec["expected_rounds"]
                              if "expected_rounds" in spec else None),
        # 2. 查询去重
        "queries": queries, "queries_unique": len(set(queries)) == len(queries),
        # 3. 证据采纳与覆盖
        "evidence_total": len(records["evidence"]),
        "duplicates_rejected": sum(r["ingest"]["duplicates"] for r in search_rounds if r["ingest"]),
        "irrelevant_rejected": sum(r["ingest"]["irrelevant"] for r in search_rounds if r["ingest"]),
        "final_coverage": {k: v["relevant_count"]
                           for k, v in records["summary"]["final_perception"]["per_subq"].items()},
        # 4. 通道状态与归因
        "channel_error_rounds": sum(1 for r in fb_rounds if r["feedback"].get("provider_error")),
        "retries_total": sum(int(r["feedback"].get("provider_retries", 0)) for r in fb_rounds),
        "attribution_mentions_channel": "通道故障" in stop_reason,
    }
    if "expected_channel_error_rounds" in spec:
        m["channel_errors_consistent"] = (m["channel_error_rounds"]
                                          == spec["expected_channel_error_rounds"])
    if "expected_retries_total" in spec:
        m["retries_consistent"] = m["retries_total"] == spec["expected_retries_total"]
    if "expected_attribution_mentions_channel" in spec:
        m["attribution_consistent"] = (m["attribution_mentions_channel"]
                                       == spec["expected_attribution_mentions_channel"])
    if "expected_duplicates_rejected_min" in spec:
        m["duplicates_consistent"] = (m["duplicates_rejected"]
                                      >= spec["expected_duplicates_rejected_min"])

    # 5. 关键回答条件缺口（仅声明任务；P1-a 冻结判据做评测期分析）
    if spec.get("key_conditions"):
        import sufficiency_criteria as sc

        text_by_url = {}
        if spec["class"] == "mock":
            for entry in spec["script"]:
                for h in entry.get("hits", []):
                    text_by_url[h["url"].rstrip("/").lower()] = f"{h['title']}\n{h['snippet']}"
        gaps = {}
        for subq, decl in spec["key_conditions"].items():
            missing = set(decl["required_points"])
            for ev in records["evidence"]:
                text = text_by_url.get(ev["url"].rstrip("/").lower())
                if not text:
                    continue
                res = sc.doc_level(text, decl["criteria_subq"])
                missing -= set(res["covered_points"])
            gaps[subq] = sorted(missing)
        m["key_condition_gaps"] = gaps
        m["key_condition_gap_found"] = any(gaps.values())
        # mock 类借用 KV 领域要点模式：跨领域候选诊断，非实际回答充分性结论
        m["key_condition_cross_domain"] = spec["class"] == "mock"

    # 6. 三层 Memory 溯源
    eps = episodes_from_log(log)
    wm = WorkingMemory(task, log)
    wm_snap = wm.snapshot()
    ltm = LongTermMemory()
    ltm.ingest(eps)
    rec = ltm.reconcile(eps)
    m["memory_trace"] = {
        "working_memory_fields": sorted(wm_snap),
        "episodes": len(eps),
        "ltm_cells": len(ltm.query()),
        "ltm_reconcile_ok": rec["ok"],
        "ltm_reconcile_fully_verified": rec["fully_verified"],
    }
    m["memory_traceable"] = (bool(wm_snap["coverage"]) and len(eps) > 0
                             and rec["ok"] and rec["fully_verified"])
    return m


def run_all(cache_dir: Path | None = None) -> dict:
    spec_all = json.loads((HERE / "eval_tasks.json").read_text(encoding="utf-8"))
    results = []
    cache_dir = cache_dir or (REPO / "artifacts/cache")
    for spec in spec_all["scenarios"]:
        if spec["class"] == "cache-replay":
            if not cache_dir.exists() or not list(cache_dir.glob("*.json")):
                results.append({"id": spec["id"], "class": spec["class"],
                                "status": "skipped-no-cache"})
                continue
        try:
            task, log = _run_scenario(spec, cache_dir)
            m = _evaluate(spec, task, log)
            m["status"] = "ok"
        except RuntimeError as exc:  # offline replay cache miss for a query
            results.append({"id": spec["id"], "class": spec["class"],
                            "status": "skipped-no-cache", "detail": str(exc)[:120]})
            continue
        results.append(m)

    summary = {"schema": spec_all["schema"], "date": "2026-10-24",
               "annotation_status": "CANDIDATE（冻结预期，未经理核查）",
               "stop_path_triggers": {}, "results": results}
    for r in results:
        if r.get("status") == "ok":
            summary["stop_path_triggers"][r["actual_stop"]] = (
                summary["stop_path_triggers"].get(r["actual_stop"], 0) + 1)
    return summary


def build_report(summary: dict) -> str:
    ok_rows = [r for r in summary["results"] if r.get("status") == "ok"]
    skipped = [r for r in summary["results"] if r.get("status") != "ok"]
    lines = [
        "# P1-c 评测汇总（冻结任务集，预期 CANDIDATE）",
        "",
        "**口径**：下述全部『一致性』指**模拟场景/冻结预期与控制器规则行为的一致**，"
        "**不等于真实回答充分性**；mock 类关键条件分析借用 KV 领域冻结模式，属跨领域候选诊断。",
        "",
        f"- 场景 {len(summary['results'])} 个（mock {sum(1 for r in summary['results'] if r.get('class') == 'mock')}"
        f" + cache-replay {sum(1 for r in summary['results'] if r.get('class') == 'cache-replay')}）",
        f"- 实际停止路径触发记录：{dict(sorted(summary['stop_path_triggers'].items()))}",
        f"- 回放缺缓存跳过：{[r['id'] for r in skipped] or '无'}",
        "",
        "## 分类别结果（mock 与 cache-replay 分列，不混算）",
        "",
    ]
    for cls in ("mock", "cache-replay"):
        rows = [r for r in ok_rows if r["class"] == cls]
        if not rows:
            continue
        lines += [f"### {cls}（{len(rows)} 个）", "",
                  "| 场景 | 停止(预期/实际) | 轮数 | 查询去重 | 证据/重复/离题 | 通道错误轮/重试 | 归因提通道 | 关键缺口 | 记忆溯源 |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            stop = f"{r['expected_stop']}/{r['actual_stop']}{'' if r['stop_consistent'] else ' ✗'}"
            rounds = f"{r['rounds_searched']}{'' if r['rounds_consistent'] is not False else ' ✗'}"
            if "key_conditions" not in r:
                gap = "—"
            elif r.get("key_condition_cross_domain"):
                gap = "有（跨领域候选诊断）" if r["key_condition_gap_found"] else "无（跨领域候选诊断）"
            else:
                gap = "有" if r["key_condition_gap_found"] else "无"
            lines.append(
                f"| {r['id']} | {stop} | {rounds} | {'✓' if r['queries_unique'] else '✗'} "
                f"| {r['evidence_total']}/{r['duplicates_rejected']}/{r['irrelevant_rejected']} "
                f"| {r['channel_error_rounds']}/{r['retries_total']} "
                f"| {'是' if r['attribution_mentions_channel'] else '否'} | {gap} "
                f"| {'✓' if r['memory_traceable'] else '✗'} |"
            )
        n = len(rows)
        acc = lambda key: sum(1 for r in rows if r.get(key) is True)
        lines += [
            "",
            f"- 停止一致性：{acc('stop_consistent')}/{n}；轮数一致：{acc('rounds_consistent')}/{sum(1 for r in rows if r['rounds_consistent'] is not None)}；"
            f"查询全唯一：{acc('queries_unique')}/{n}；记忆溯源：{acc('memory_traceable')}/{n}；"
            f"去重下限达成：{acc('duplicates_consistent')}/{sum(1 for r in rows if 'duplicates_consistent' in r)}（M8 未达成即去重阈值局限，保留为发现）",
            f"- 通道错误轮一致：{acc('channel_errors_consistent')}/{sum(1 for r in rows if 'channel_errors_consistent' in r)}；"
            f"重试一致：{acc('retries_consistent')}/{sum(1 for r in rows if 'retries_consistent' in r)}；"
            f"归因一致：{acc('attribution_consistent')}/{sum(1 for r in rows if 'attribution_consistent' in r)}",
            "",
        ]
    findings = [
        (r["id"], key, r[key])
        for r in ok_rows
        for key in ("stop_consistent", "rounds_consistent", "channel_errors_consistent",
                    "retries_consistent", "attribution_consistent",
                    "duplicates_consistent", "queries_unique", "memory_traceable")
        if r.get(key) is False
    ]
    lines += ["## 不一致项记录（冻结预期 vs 实际，如实呈现）", ""]
    if findings:
        for sid, key, val in findings:
            detail = next((r for r in ok_rows if r["id"] == sid), {})
            extra = ""
            if key == "duplicates_consistent":
                extra = (
                    f"（实际去重 {detail.get('duplicates_rejected')} 条，低于冻结下限——"
                    f"近似标题附加词较多时 jaccard<0.8 未被判重复，去重阈值局限的实证）"
                )
            lines.append(f"- {sid}.{key} = {val}{extra}")
    else:
        lines.append("- 无")

    lines += [
        "## 口径与限定",
        "",
        "- 全部一致性对照的是**冻结的候选预期**与控制器规则行为，不是真实答案质量；",
        "- 词法 score / helpful 代理 / 候选标签一致率均不解释为答案质量；",
        "- mock 类可精确离线重算；cache-replay 类依赖本机缓存，缺失即跳过并如实标注；",
        "- M7/M9 为诊断场景：按现行规则 stop_sufficient 属预期一致，其已知局限（伪覆盖/跨域碰撞）由关键条件缺口指标与用途字段记录。",
    ]
    return "\n".join(lines)


def main() -> int:
    summary = run_all()
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    for r in summary["results"]:
        (out / f"{r['id']}.json").write_text(
            json.dumps(r, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    (out / "summary.md").write_text(build_report(summary), encoding="utf-8")
    print("stop_path_triggers:", summary["stop_path_triggers"])
    for r in summary["results"]:
        if r.get("status") == "ok":
            print(f"  {r['id']:32s} stop={r['actual_stop']:16s} consistent={r['stop_consistent']}")
        else:
            print(f"  {r['id']:32s} {r['status']}")
    print("written: results/summary.json, results/summary.md, per-task json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
