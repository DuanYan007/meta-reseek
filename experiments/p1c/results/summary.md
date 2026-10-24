# P1-c 评测汇总（冻结任务集，预期 CANDIDATE）

**口径**：下述全部『一致性』指**模拟场景/冻结预期与控制器规则行为的一致**，**不等于真实回答充分性**；mock 类关键条件分析借用 KV 领域冻结模式，属跨领域候选诊断。

- 场景 12 个（mock 9 + cache-replay 3）
- 实际停止路径触发记录：{'stop_diminishing': 2, 'stop_forced': 1, 'stop_sufficient': 9}
- 回放缺缓存跳过：无

## 分类别结果（mock 与 cache-replay 分列，不混算）

### mock（9 个）

| 场景 | 停止(预期/实际) | 轮数 | 查询去重 | 证据/重复/离题 | 通道错误轮/重试 | 归因提通道 | 关键缺口 | 记忆溯源 |
|---|---|---|---|---|---|---|---|---|
| M1-sufficient-easy | stop_sufficient/stop_sufficient | 1 | ✓ | 4/0/0 | 0/0 | 否 | — | ✓ |
| M2-adjust-broaden | stop_sufficient/stop_sufficient | 2 | ✓ | 4/0/0 | 0/0 | 否 | — | ✓ |
| M3-diminishing | stop_diminishing/stop_diminishing | 3 | ✓ | 2/4/0 | 0/0 | 否 | — | ✓ |
| M4-forced | stop_forced/stop_forced | 3 | ✓ | 0/0/3 | 0/0 | 否 | — | ✓ |
| M5-provider-final-failure | stop_diminishing/stop_diminishing | 3 | ✓ | 2/0/0 | 2/0 | 是 | — | ✓ |
| M6-retry-recovered | stop_sufficient/stop_sufficient | 1 | ✓ | 4/0/0 | 0/1 | 否 | — | ✓ |
| M7-pseudo-high-coverage | stop_sufficient/stop_sufficient | 1 | ✓ | 4/0/0 | 0/0 | 否 | — | ✓ |
| M8-duplicates-same-source | stop_sufficient/stop_sufficient | 2 | ✓ | 5/1/0 | 0/0 | 否 | — | ✓ |
| M9-cross-domain-collision | stop_sufficient/stop_sufficient | 1 | ✓ | 3/0/0 | 0/0 | 否 | — | ✓ |

- 停止一致性：9/9；轮数一致：9/9；查询全唯一：9/9；记忆溯源：9/9；去重下限达成：0/1（M8 未达成即去重阈值局限，保留为发现）
- 通道错误轮一致：9/9；重试一致：9/9；归因一致：2/2

### cache-replay（3 个）

| 场景 | 停止(预期/实际) | 轮数 | 查询去重 | 证据/重复/离题 | 通道错误轮/重试 | 归因提通道 | 关键缺口 | 记忆溯源 |
|---|---|---|---|---|---|---|---|---|
| R1-kv-cache-replay | stop_sufficient/stop_sufficient | 3 | ✓ | 15/0/0 | 0/1 | 否 | — | ✓ |
| R2-frameworks-replay | stop_sufficient/stop_sufficient | 3 | ✓ | 11/0/4 | 0/1 | 否 | — | ✓ |
| R3-nobel-replay | stop_sufficient/stop_sufficient | 1 | ✓ | 5/0/0 | 0/0 | 否 | — | ✓ |

- 停止一致性：3/3；轮数一致：3/3；查询全唯一：3/3；记忆溯源：3/3；去重下限达成：0/0（M8 未达成即去重阈值局限，保留为发现）
- 通道错误轮一致：0/0；重试一致：0/0；归因一致：0/0

## 不一致项记录（冻结预期 vs 实际，如实呈现）

- M8-duplicates-same-source.duplicates_consistent = False（实际去重 1 条，低于冻结下限——近似标题附加词较多时 jaccard<0.8 未被判重复，去重阈值局限的实证）
## 口径与限定

- 全部一致性对照的是**冻结的候选预期**与控制器规则行为，不是真实答案质量；
- 词法 score / helpful 代理 / 候选标签一致率均不解释为答案质量；
- mock 类可精确离线重算；cache-replay 类依赖本机缓存，缺失即跳过并如实标注；
- M7/M9 为诊断场景：按现行规则 stop_sufficient 属预期一致，其已知局限（伪覆盖/跨域碰撞）由关键条件缺口指标与用途字段记录。