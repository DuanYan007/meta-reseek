# 开发进度与阶段记录

## 2026-10-23 — 节点 A：环境检查与实施方案

**环境**：复用系统 Python 3.11（无 Conda）+ 已有 PyYAML/requests/pytest；新增 `ddgs` 9.16.0（官方 PyPI 源，清华镜像无此包）。torch 2.6.0+cpu 与 transformers 4.57.6 存在但 P0 不用。详见 [ENVIRONMENT.md](ENVIRONMENT.md)。

**技术方案**：
- 检索：DuckDuckGo（`ddgs`，无 Key）+ Provider 抽象（可换后端）+ 磁盘响应缓存（在线运行 / 离线回放 / 强制刷新三模式）；
- 评价：确定性词法充分性评价（子问题覆盖度 0.7 + 来源多样性 0.3，K 条相关证据判据），理由数量化输出；
- 调整：规则策略族 initial / broaden / specialize / target_weakest / diversify，永不重复查询；
- 停止：sufficient / diminishing（区分通道故障归因）/ forced 三种显式决策；
- 反馈：逐轮记录决策理由与实际增益（helpful/neutral/stalled），全量 JSON 轨迹 + 最终证据清单。

**开发顺序**：检索层 → 证据层 → 元认知三件套（感知/评价/调整）→ 控制器与 CLI → 离线测试 → 真实运行与回放验证 → 文档。

**风险**：DDG 后端瞬断（已重试+降级）；pip 镜像缺包（已记录）；无 gh CLI（PR 走网页）。

## 2026-10-23 — 节点 B：P0 元认知闭环端到端跑通

**实现**：全部 P0 功能（见 README"当前能力"）。单元测试 34 个全部通过（`python -m pytest tests/ -q`），覆盖三种停止路径、错误归因、缓存三模式语义、去重与相关性边界。

**真实运行**（DuckDuckGo 真检索，非 mock）：

| 任务 | 检索轮数 | 停止决策 | 最终 score | 反馈分布 |
|---|---|---|---|---|
| nobel_physics_2024 | 1 | stop_sufficient | 0.925 | helpful×1 |
| kv_cache_llm | 3 | stop_sufficient | 1.0 | helpful×3 |
| python_web_frameworks | 3 | stop_sufficient | 1.0 | helpful×3 |

每任务另做离线回放（`--cache offline`）：决策/查询序列 100% 一致，网络调用 0 次。演示轨迹与可读摘要入库 `artifacts/demo/`。

**过程中发现并修复的真实问题**：
1. 词法相关性"串扰"：共享主题词（Nobel/Physics/2024）使 A 子问题的证据误计入 B → 引入共享词 0.25 降权（类 IDF）+ 相对边际 0.6 阈值；
2. `ddgs` 瞬断异常会杀死整个运行 → 重试 2 次 + 降级为空结果（stalled 反馈）+ 错误入轨迹；
3. **通道故障被误归因为"策略收益递减"** → 增加传输层错误标记（随缓存持久化，回放归因一致），连续故障时停止理由如实改写为"基础设施失效而非策略收益递减"。此问题本身是元认知归因研究的真实素材；
4. 缓存空结果语义两难（毒化在线 vs 破坏回放）→ 空结果入缓存但 auto 模式视为未命中、offline 模式如实复现。

**局限**：本轮三次真实运行均走 sufficient 路径提前停止；diminishing 路径有单元测试覆盖 + 此前一次真实触发记录（当时系通道故障，已修正归因），forced 路径仅测试覆盖。评价器为词法规则基线，不含语义理解（P1 范围）。

## 2026-10-23 — 节点 B 验收反馈：有条件通过，四项收尾

GPT 验收结论"有条件通过"，反馈四项：

1. **修复错误状态记录（已完成）**：确认 `DdgProvider` 重试成功路径不清除 `last_error` 的缺陷——此前演示轨迹中存在"成功采纳 5 条但 `provider_error=true`"的轮次，且该错误标志曾随缓存持久化。修复：成功即清除错误状态；新增 `last_retries` 区分"曾重试后成功"（不算失败、保留可见）与"最终失败"（全部重试耗尽）；重试计数随缓存持久化，离线回放还原相同归因。新增 9 个测试（`tests/test_ddg_retry.py`，含脚本化 `_fetch` 的重试状态机与控制器端到端），全套 **43 passed**。重新真实运行（冷缓存，真实网络调用 1/3/3 次）验证：无误标轮次；kv 第 3 轮、frameworks 第 1 轮真实发生"重试 1 次后成功"，轨迹如实记录 `provider_retries=1, provider_error=false`。
2. **澄清指标含义（已完成）**：README 新增"指标口径"表；`evaluation.py` 模块说明与演示摘要明确 `score` 为词法充分性**代理分数**（非语义充分性）；区分 `new_items`（唯一文档数）与 `new_relevant_total`（子问题匹配对增量，可大于文档数）。摘要生成脚本入库 `scripts/make_digest.py`（措辞含口径说明，三个任务摘要可再生成、可审计）。
3. **GitHub 交付流程（已完成）**：修复在 `feature/p0-metacog-loop` 分支完成并推送；通过凭据 API 创建指向 `main` 的 PR，PR 描述列明 P0 功能清单、测试结果、演示轨迹与剩余局限。版本保持 v0.1，未改动 Python/PyTorch/CUDA 环境。
4. **研究边界（遵守）**：未新增算法、语义融合、记忆或元元认知功能；仅修复与文档澄清。

## 2026-10-23 — P0 节点 B 正式验收通过，PR #1 合并 main

- **验收结论**：GPT 确认 P0 节点 B 验收通过，授权合并。
- **合并前复测**：`feature/p0-metacog-loop` @ `b1f946a`，工作区干净，`python -m pytest tests/ -q` → **43 passed**。
- **合并操作**：REST API `PUT /repos/DuanYan007/meta-reseek/pulls/1/merge`，`merge_method=squash`，锁定 `sha=b1f946a`，返回 `merged=true`。
- **合并提交**：`17fca05`（`feat(p0): complete metacognitive retrieval loop [v0.1] (#1)`），merged_at `2026-10-23T09:20:23Z`。
- **合并后验证**：API 确认 `main` HEAD=`17fca05`；树 SHA 等价证明——main 合并提交树 `7e33053` 与被测 feature HEAD 树完全一致，即 main 内容与通过 43 项测试的树逐字节相同。当日 `github.com:443` git 传输间歇阻断（API 正常），本地 `git pull main` 与本地 main 复测在网络恢复后补充执行。
- **节点 B 状态**：**完成**。本批验收记录文档经独立分支 `docs/p0-acceptance-and-p1-brief` + PR 提交（见仓库 PR 列表）。
