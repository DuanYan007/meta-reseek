"""CLI entry: run one task through the metacognitive loop.

Examples:
    python -m meta_reseek.run examples/tasks/nobel_physics_2024.yaml
    python -m meta_reseek.run examples/tasks/kv_cache_llm.yaml --cache offline
    python -m meta_reseek.run examples/tasks/nobel_physics_2024.yaml --cache refresh
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .metacog.controller import MetacognitiveController
from .search.cache import CachedProvider, FileCache
from .search.ddg import DdgProvider
from .task import TaskSpec


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="meta_reseek.run", description=__doc__)
    parser.add_argument("task", help="path to a task YAML under examples/tasks/")
    parser.add_argument("--max-rounds", type=int, default=None)
    parser.add_argument("--max-results", type=int, default=5, help="results per search")
    parser.add_argument(
        "--cache",
        choices=["auto", "refresh", "offline"],
        default="auto",
        help="auto: reuse cached responses, else fetch; refresh: always fetch; "
        "offline: replay strictly from cache (reproducibility check)",
    )
    parser.add_argument("--out", default="artifacts/runs", help="trace output directory")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument(
        "--save-episodes", default=None, metavar="PATH",
        help="P1-b: 把本次运行投影为经历记录并保存为 JSONL（默认关闭，行为与 P0 完全一致）",
    )
    parser.add_argument(
        "--show-working-memory", action="store_true",
        help="P1-b: 运行后打印 WorkingMemory 任务上下文视图（只读，不影响运行）",
    )
    args = parser.parse_args(argv)

    task = TaskSpec.from_yaml(args.task)
    provider = CachedProvider(
        DdgProvider(), FileCache(Path("artifacts/cache")), mode=args.cache
    )
    emit = (lambda _msg: None) if args.quiet else print
    emit(f"=== MetaReSeek v0.1 | 任务: {task.name} ===")
    emit(f"问题: {task.question}")
    for sq in task.sub_questions:
        emit(f"  子问题 [{sq.id}] {sq.text}")

    controller = MetacognitiveController(
        task, provider, max_rounds=args.max_rounds, max_results=args.max_results, emit=emit
    )
    log = controller.run()

    summary = log.summary()
    emit("---")
    emit(
        f"总结: {summary['search_rounds']} 轮检索 / {summary['rounds_total']} 条记录 | "
        f"停止决策: {summary['stop_decision']} | 最终 score {summary['final_score']}"
    )
    emit(f"效果反馈分布: {summary['effect_counts']}")

    if args.show_working_memory:
        from .memory import WorkingMemory

        emit("--- WorkingMemory（只读视图） ---")
        emit(WorkingMemory(task, log).context_summary())

    if args.save_episodes:
        from .memory import EpisodicMemory

        mem = EpisodicMemory()
        n = mem.extend_from_log(log)
        path = mem.save(args.save_episodes)
        emit(f"EpisodicMemory: 已保存 {n} 条经历 -> {path}")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{task.name}.json"
    trace = log.as_dict()
    trace["config"]["cache_mode"] = args.cache
    trace["config"]["cache_network_calls"] = provider.network_calls
    inner_errors = getattr(provider.inner, "errors", [])
    if inner_errors:
        trace["config"]["provider_errors"] = inner_errors
    out_path.write_text(json.dumps(trace, ensure_ascii=False, indent=1), encoding="utf-8")
    emit(f"完整决策轨迹已写入: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
