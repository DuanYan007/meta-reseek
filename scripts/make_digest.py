"""Render a human-readable digest from a run trace JSON.

Usage:
    python scripts/make_digest.py artifacts/demo/kv_cache_llm.json [more.json ...]

Wording is deliberately precise about what the metrics mean:

- ``score``       是充分性**代理分数**：0.7×子问题关键词覆盖度 + 0.3×来源域名
                  多样性，不代表语义层面的充分性判断。
- ``new_items``   本轮新采纳的唯一文档数（去重后，每篇至少对一个子问题相关）。
- ``new_relevant_total``
                  子问题相关匹配对增量：一篇文档可同时支撑多个子问题，因此
                  该值可大于唯一文档数。
- ``provider_retries / provider_error``
                  重试后成功不算失败（retries 记录恢复次数）；error 仅在
                  全部重试耗尽时为真。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def render(trace: dict) -> str:
    t = trace
    cfg = t["config"]
    s = t["summary"]
    lines = [
        f"# 演示运行记录：{t['task']}（真实 DuckDuckGo 检索）",
        "",
        f"- 运行时间(UTC)：{t['started_at']} | 后端：{cfg['provider']} | 缓存模式：{cfg.get('cache_mode')}"
        f"（本次运行真实网络调用 {cfg.get('cache_network_calls')} 次）",
        f"- 检索轮数：{s['search_rounds']} / 记录 {s['rounds_total']} 条 | 停止决策：**{s['stop_decision']}**",
        f"- 效果反馈分布：{s['effect_counts']}",
        "",
        "> **指标口径**：score = 0.7×子问题关键词覆盖度 + 0.3×来源域名多样性，"
        "是充分性**代理分数**（词法、确定性），不代表语义充分性。"
        "“匹配增量”按子问题计，一篇文档支撑多个子问题时计多次，可大于唯一文档数。",
        "",
        "## 逐轮元认知记录",
        "",
    ]
    for r in t["rounds"]:
        counts = {k: v["relevant_count"] for k, v in r["perception"]["per_subq"].items()}
        lines.append(f"### Round {r['round_idx']} — {r['decision']}")
        lines.append(
            f"- 感知：唯一文档 {r['perception']['total_items']} 篇，"
            f"子问题相关文档数 {counts}，来源域 {r['perception']['domain_count']} 个"
        )
        lines.append(
            f"- 评价：代理 score={r['evaluation']['score']}，verdict={r['evaluation']['verdict']}"
        )
        if r["action"]:
            lines.append(
                f"- 决策：{r['action']['strategy']} → `{r['action']['query']}`"
                f"（目标：{r['action']['target_subq']}）"
            )
        if r["ingest"]:
            lines.append(
                f"- 执行：候选 {r['ingest']['candidates']} → 采纳 {r['ingest']['added']}"
                f"（重复 {r['ingest']['duplicates']}，离题 {r['ingest']['irrelevant']}）"
            )
        if r["feedback"]:
            fb = r["feedback"]
            note = ""
            if fb.get("provider_retries"):
                note += f"，检索经 {fb['provider_retries']} 次重试后成功"
            if fb.get("provider_error"):
                note += "，检索通道故障"
            target = (
                f"，目标子问题 {fb['target_subq']} 相关文档 +{fb['new_relevant_for_target']}"
                if fb.get("target_subq")
                else ""
            )
            lines.append(
                f"- 反馈：新增唯一文档 {fb['new_items']} 篇 / 子问题匹配增量 "
                f"{fb['new_relevant_total']}{target}，效果={fb['effect']}{note}"
            )
        lines.append(f"- 理由：{r['decision_reason']}")
        lines.append("")
    lines += ["## 最终证据清单（URL 可点击核对）", ""]
    for ev in t["evidence"]:
        best = max(ev["relevance"], key=ev["relevance"].get)
        lines.append(f"- R{ev['round_added']} [{best}] {ev['title']} — {ev['url']}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    for arg in argv[1:]:
        trace = json.loads(Path(arg).read_text(encoding="utf-8"))
        out = Path(arg).with_suffix("").as_posix() + "_digest.md"
        Path(out).write_text(render(trace), encoding="utf-8")
        print("digest written:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
