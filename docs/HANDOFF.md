# MetaReSeek v0.1 — 交付文档（单页完整版）

更新：2026-10-24（含 PR #2 评审意见修订）。本文档自包含全部交接信息，传递本文档即可，无需查阅其他文件。

## 1. 状态总览

- **P0（元认知检索闭环）**：已实现 → 节点 B 验收**通过** → PR #1 已合并 `main`（`17fca05`）
- **PR #2**（验收记录 + GitHub 操作规范 + P1 简报）：GPT 评审**小幅修改后通过**（2026-10-24），已按四条意见修订，授权 squash 合并 → https://github.com/DuanYan007/meta-reseek/pull/2
- 版本：v0.1（未升级）；下一轮仅启动 P1-a 最小实验，不同时启动全部 P1

## 2. PR #1 合并记录（事实）

- 合并前复测：`feature/p0-metacog-loop` @ `b1f946a`，工作区干净，`pytest` **43 passed**，PR head SHA 与本地一致且 mergeable
- 合并操作：REST API squash 合并，锁定 `sha=b1f946a`，返回 `merged=true`（2026-10-23T09:20:23Z）；无强制推送，未绕过测试
- 合并提交：`17fca05905b804a63daadfa7ec1e453f83f42728`（现为 `main` HEAD）
- 合并后验证：main 合并树 `7e33053` 与被测 feature HEAD 树**逐字节一致**（树 SHA 等价证明）

## 3. P0 已实现功能（全部已在 `main`）

1. 真实外部检索：DuckDuckGo（`ddgs`，无 API Key），Provider 可插拔，瞬断重试 + 失败降级
2. 单任务多轮搜索：查询永不重复；initial / broaden / specialize / target_weakest / diversify 策略
3. 检索状态感知：子问题覆盖度、来源域名数、上轮新增
4. 充分性评价：确定性词法**代理** score = 0.7×关键词覆盖 + 0.3×来源域多样性，判定附数量化理由
5. 三种显式停止：`stop_sufficient` / `stop_diminishing`（区分策略收益递减与检索通道故障）/ `stop_forced`（如实报告缺口）
6. 决策理由与效果反馈全量 JSON 轨迹，含最终证据清单（URL 可核对）
7. 可复现：磁盘缓存 + `--cache offline` 离线精确回放

## 4. 测试

`python -m pytest tests/ -q` → **43 passed**（离线、确定性、无网络依赖）。覆盖：三种停止路径、重试状态语义（重试后成功≠最终失败）、通道故障归因、缓存三模式、URL/近似标题去重、查询不重复、轨迹结构完整性。PR #2 修订未改任何 P0 代码。

## 5. 真实运行演示（2026-10-23，冷缓存真实网络）

| 任务 | 检索轮 | 网络调用 | 停止决策 | 代理 score |
|---|---|---|---|---|
| nobel_physics_2024 | 1 | 1 | stop_sufficient | 0.925 |
| kv_cache_llm | 3 | 3 | stop_sufficient | 1.0 |
| python_web_frameworks | 3 | 3 | stop_sufficient | 1.0 |

三任务离线回放决策序列 100% 一致（0 网络调用）。轨迹与可读摘要在 `main` 的 `artifacts/demo/`。

## 6. 指标口径

- `score`：词法充分性**代理分数**，非语义充分性判断
- `new_items`：本轮新采纳的唯一文档数；`new_relevant_total`：子问题匹配对增量（一篇文档支撑多个子问题时计多次，可大于文档数）
- `provider_retries`：检索经 N 次重试后**成功**（不算失败）；`provider_error`：检索**最终失败**（重试全部耗尽）

## 7. 剩余局限与未解决事项（如实）

1. 评价器为词法规则基线（代理分数），无语义理解
2. 真实运行均走 sufficient 路径；diminishing / forced 停止由单元测试覆盖
3. DDG 后端偶发限流/tls 故障：已重试 + 降级 + 归因，连续故障时诚实提前终止
4. 本机 `github.com:443` git 传输间歇阻断（API 正常）：PR #2 分支经 Git Data API 服务端创建与更新（树 SHA 与本地构建一致已验证，快进更新无强推）；本地 `main` 例行 `git pull` 同步待网络恢复后补做，不影响仓库状态
5. 原型边界：元认知资源检索控制器，非完整长程任务 Agent；无语义融合 / 记忆体系 / 元元认知

## 8. PR #2 修订内容（仅文档，无代码变更；变更统计以 PR 页面为准）

| 文件 | 内容 |
|---|---|
| `AGENTS.md` | 永久加入 GitHub 命令行操作规范 6 条 |
| `docs/PROGRESS.md` | P0 正式验收与 PR #1 合并记录 |
| `docs/HANDOFF.md` | 本文档（单页完整版，已按评审意见修正过时统计与状态描述） |
| `docs/ROADMAP.md` | P0 完成（合并 `17fca05`）；测试数修正为 43；P1 仍属 v0.1 |
| `docs/P1_BRIEF.md` | P1 实施简报，已按评审意见修订（见第 9 节） |

评审意见落实：① ROADMAP 测试数 34→43；② HANDOFF 过时统计与评审状态修正；③ P1_BRIEF 明确嵌入相似度≠证据充分性、P1-a 以人工核对案例评估缺口识别为先；④ Episodic Memory 保存完整「调整前状态→调整动作→反馈结果」经历，长期记忆作为元元认知的工作材料。

## 9. P1 实施简报（已按 2026-10-24 评审意见修订）

**P1-a 语义证据整理、融合与充分性评价（最小实验先行）**：
- 复用已装 transformers 4.57.6 + CPU torch；候选本地嵌入模型 all-MiniLM-L6-v2（~90MB，镜像/预置缓存下载，权重不入库）
- **关键限定**：嵌入相似度只是相关性的代理，**不能直接证明证据充分性**；充分性判断仍需覆盖度/多样性等结构性证据支撑
- 实验顺序（按评审要求）：**先构建少量人工核对案例**，验证现有词法评价器在哪些情况下判断失误（同义改写漏检、主题词重叠伪相关等），再检验语义模块能否改善这些**具体的证据缺口识别**问题——而非只比较 score 数值
- 之后：`RelevanceScorer` 接口化词法/语义双轨；语义相关性用于子问题打分、语义去重、证据分组；融合边界=排序+去冗余+分组，不做生成式摘要；嵌入结果缓存保证离线回放

**P1-b 三层 Memory 渐进实现**：
- WorkingMemory：任务内证据滑动窗口 + 决策上下文（进程内对象，接口固定）
- EpisodicMemory：JSONL 轨迹库，保存**完整经历**——「调整前状态（感知/评价）→ 调整动作（策略/查询/理由）→ 反馈结果（增益/效果/通道状态）」，与现有 RoundRecord 字段直接对应；按任务/子问题检索的最小接口
- LongTermMemory：JSON KV 存策略参数与跨任务统计，仅存取不做学习算法；其中**评价器判断与实际结果的对账记录构成元元认知的后续工作材料**（本版本只保存，不做校准）
- 预留元元认知接口：Evaluator 可插拔注册 + trace 记录评价器自报置信度字段

**P1-c 评测集扩展**：10+ 任务含故意不可满足任务（真实触发 diminishing/forced），自动评分脚本（停止正确率/轮数/证据命中）

**环境与风险**：不动 Python/torch/CUDA；CPU 嵌入吞吐可满足演示规模；HF 下载经镜像，失败提交阻塞报告。**版本保持 v0.1；不同时启动全部 P1 功能。**

---

*复现命令：`pip install -r requirements.txt`（ddgs 需 `-i https://pypi.org/simple`）→ `python -m pytest tests/ -q` → `python -m meta_reseek.run examples/tasks/kv_cache_llm.yaml`（真实检索）/ 同命令加 `--cache offline`（离线回放）。*
