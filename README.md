# MetaReSeek v0.1

Agent 迭代资源检索的元认知研究原型。核心是单任务内真实外部检索驱动的元认知闭环：

```
Perception（感知检索状态）→ Evaluation（证据充分性评价）
    → Adjustment（调整或停止检索）→ Feedback（决策效果反馈）
                    ↑________________________________________|
```

与普通多轮搜索的区别在于：每一轮先**评价已有证据是否足够**，据此**决定继续、换策略还是停止**，并把**每个决策的理由与实际效果**记录成可审查的轨迹。

## 当前能力（v0.1 P0，已实现并验证）

- 真实外部检索（DuckDuckGo，`ddgs`，无需 API Key），瞬断自动重试、失败降级不中断；
- 单任务多轮搜索，查询永不重复；子问题级覆盖度/来源多样性/边际增益感知；
- 确定性、可解释的充分性**代理**评价（词法口径：0.7×关键词覆盖 + 0.3×来源域多样性），每种判定附带数量化理由；
- 三种显式停止决策：`stop_sufficient`（证据充分）、`stop_diminishing`（边际收益递减，能区分策略收益枯竭与检索通道故障）、`stop_forced`（达最大轮数，如实报告缺口）；
- 每轮决策与效果反馈（helpful / neutral / stalled）全量落盘为 JSON 轨迹，含最终证据清单（URL 可核对）；
- 磁盘缓存支持**离线精确回放**（决策序列 100% 一致、0 次网络调用），保证可复现。

### 指标口径（避免误读）

| 指标 | 含义 |
|---|---|
| `score` | 充分性**代理分数** = 0.7×子问题关键词覆盖度 + 0.3×来源域名多样性；词法、确定性，**不是**语义充分性判断 |
| `new_items` | 本轮新采纳的**唯一文档数**（URL/近似标题去重后，每篇至少对一个子问题相关） |
| `new_relevant_total` | 子问题相关**匹配对增量**：一篇文档可同时支撑多个子问题，故可大于唯一文档数 |
| `new_relevant_for_target` | 目标子问题相关文档数的增量 |
| `provider_retries` | 本轮检索经 N 次重试后**成功**（不算失败，但保留可见性） |
| `provider_error` | 本轮检索**最终失败**（全部重试耗尽）；仅此时反馈标记通道故障 |

## 快速开始

```bash
pip install -r requirements.txt          # ddgs / PyYAML / requests

# 真实检索运行（结果缓存在 artifacts/cache/）
python -m meta_reseek.run examples/tasks/kv_cache_llm.yaml

# 离线回放（严格用缓存复现，0 网络调用；用于复核可复现性）
python -m meta_reseek.run examples/tasks/kv_cache_llm.yaml --cache offline

# 强制重新联网抓取
python -m meta_reseek.run examples/tasks/nobel_physics_2024.yaml --cache refresh
```

运行轨迹写入 `artifacts/runs/<task>.json`。示例任务在 `examples/tasks/`（事实型 / 技术概念型 / 对比型各一）。

## 架构

```
meta_reseek/
├── task.py              任务定义：问题 + 子问题分解 + 停止判据（K 值等）
├── textutil.py          分词/停用词（确定性词法工具）
├── search/              检索层：Provider 抽象 + DuckDuckGo 实现 + 响应缓存
├── evidence.py          证据库：相关性打分（多词加权、共享词降权）、URL/近似标题去重
├── metacog/
│   ├── perception.py    感知：子问题覆盖、来源域、上轮新增
│   ├── evaluation.py    评价：充分性分数 + 判定 + 数量化理由
│   ├── adjustment.py    调整：broaden/specialize/target_weakest/diversify/stop
│   └── controller.py    闭环编排，产出 RoundRecord 轨迹
├── feedback.py          决策日志：逐轮记录、效果度量、JSON 轨迹
└── run.py               CLI 入口
```

评价与调整策略均为**规则基线**（确定性、可解释、可替换），接口留给 P1 的语义/模型化策略。

## 记忆能力（P1-b 第一轮，2026-10-24）

- **WorkingMemory**（`meta_reseek/memory/working.py`）：任务内工作记忆——P0 决策日志的**只读视图**（覆盖状态/最近策略与理由/已试查询/证据缺口/最近反馈与通道状态），不建第二状态源、不参与决策；
- **EpisodicMemory**（`meta_reseek/memory/episodic.py`）：版本化 JSONL 经历库（schema `meta-reseek/episodic` v1），每条完整经历保留「调整前状态 → 调整动作 → 调整理由 → 检索反馈 → 实际结果」，支持按任务/子问题/策略查询与去重加载；
- CLI 可选开启（默认关闭，行为与 P0 完全一致）：`--save-episodes PATH`、`--show-working-memory`；
- **LongTermMemory**（`meta_reseek/memory/longterm.py`，P1-b 第二轮）：跨任务策略统计（schema `meta-reseek/longterm` v1）——按任务×策略聚合尝试/反馈分布/通道错误，每格保存来源 episode ID 可回溯；幂等导入、确定性持久化、`reconcile()` 双向核对；`--save-longterm PATH` 可选开启。**effect=helpful 为 P0 反馈代理，非真实答案质量**；只保存与查询统计，不参与策略选择；
- 边界：不含跨任务策略学习 / 参数自动更新 / 元元认知校准 / RSI。

## 评测集（P1-c，2026-10-24）

`experiments/p1c/`：12 个冻结场景（9 mock 确定性 + 3 真实任务缓存回放），覆盖八类证据条件与三种停止路径；六类指标 + 自动汇总报告（`python experiments/p1c/run_eval.py`，mock 类完全离线可重算）。

## 测试与演示

```bash
python -m pytest tests/ -q        # 43 个离线测试：三种停止路径、重试状态语义（重试后成功≠失败）、
                                  # 通道错误归因、缓存语义、去重等
```

真实运行的演示轨迹见 `artifacts/demo/`（三个任务各含 JSON 轨迹 + `_digest.md` 可读摘要，摘要由 `scripts/make_digest.py` 生成，含指标口径说明）。

## 更多文档

- 协作规范：[AGENTS.md](AGENTS.md)
- 环境与依赖：[docs/ENVIRONMENT.md](docs/ENVIRONMENT.md)
- 进度记录：[docs/PROGRESS.md](docs/PROGRESS.md)
- 验收交付报告：[docs/HANDOFF.md](docs/HANDOFF.md)
- 版本范围与路线：[docs/ROADMAP.md](docs/ROADMAP.md)
