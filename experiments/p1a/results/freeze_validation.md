# P1-a 任务 3：充分性判据核查（冻结盲测 + 敏感性 + 分层审计，PR #8 整改修订版）

**冻结协议**：`sufficiency_criteria.py` 全程零修改。**表述口径（整改③）**：新任务部分为**冻结方法的探索性跨任务审计**
（新任务要点虽仅依据任务文件子问题文本起草，但要点与标注同提交，无可核查的事前登记证据，不称严格预登记验证）；
本文档中所有 N/M 一致性数字均为**文档层/标注层一致性**，不是任务停止正确率。

## 0. 新证据溯源审计（整改①）

| 条目 | URL | 查询 | 可核查 | 处置 |
|---|---|---|---|---|
| f01 | https://www.narenvadapalli.com/blog/understanding-kv-cache/… | why does KV cache use so m… | cache_key 可回放 | 计入独立新证据 |
| f02 | https://insiderllm.com/guides/kv-cache-optimization-guide/… | why does KV cache use so m… | cache_key 可回放 | 计入独立新证据 |
| f03 | https://arxiv.org/pdf/2603.20397… | key value cache memory red… | cache_key 可回放 | **排除**：与旧案例同源：e011 (arXiv 2603.20397) |
| f04 | https://www.researchgate.net/publication/389917099_Key_Value… | key value cache memory red… | cache_key 可回放 | 计入独立新证据 |
| f05 | https://ieeexplore.ieee.org/document/10983416… | key value cache memory red… | cache_key 可回放 | **排除**：与新鲜集内条目同源：f04 (IEEE 门户: ieeexplore.ieee.org/document/10983416) |
| f06 | https://openreview.net/pdf?id=ou0AsNbXVG… | key value cache memory red… | cache_key 可回放 | 计入独立新证据 |

专项核查结论：**f03 与旧案例 e011 为同一论文**（arXiv 2603.20397 的 pdf/html 双版本；
e012 的 pdf URL 因先前同源去重已不在案例集，URL 过滤未拦住——本轮修正）；f05 与 f04 为同一论文
ResearchGate/IEEE 双门户。二者均不计为独立新证据，仅留溯源记录。全部条目 URL/查询/缓存键已登记，可经
`artifacts/cache` 回放核查；无不可核实条目。标注口径修订（整改②）：f02→cost、f04→techniques 按
『宣称会解释 vs 实际给出解释』由 sufficient_support 下调为 partial 并附不确定说明（f01→cost 同口径补注）。

## 1. 冻结规则 × 同任务新证据（独立新证据 4 篇 × 3 子问题 = 12 对，标注 CANDIDATE）

- 文档层相关性一致性：8/12
- 文档层充分支持级一致性：11/12

逐条：

- f01/definition：gold=topic_only，冻结判定=partial_points（命中 ['P1-缓存对象', 'P3-场景']），相关层✗，充分层✓——未描述缓存机制本身（宣称 explore the mechanics）
- f01/cost：gold=partial（标注不确定），冻结判定=partial_points（命中 ['P2-量级与占用']），相关层✓，充分层✓——标题宣称 mechanics/calculations，摘要未见增长关系表述
- f01/techniques：gold=topic_only，冻结判定=topic_or_less（命中 []），相关层✓，充分层✓——无
- f02/definition：gold=topic_only，冻结判定=partial_points（命中 ['P1-缓存对象']），相关层✗，充分层✓——无机制描述
- f02/cost：gold=partial（标注不确定），冻结判定=partial_points（命中 ['P2-量级与占用']），相关层✓，充分层✓——标题直接陈述驱动因素（context length 吃掉 VRAM），但摘要未展开机制
- f02/techniques：gold=topic_only，冻结判定=topic_or_less（命中 []），相关层✓，充分层✓——And How to Fix It 仅暗示存在手段，未点名
- f04/definition：gold=topic_only，冻结判定=partial_points（命中 ['P1-缓存对象']），相关层✗，充分层✓——无
- f04/cost：gold=topic_only，冻结判定=topic_or_less（命中 []），相关层✓，充分层✓——无
- f04/techniques：gold=partial（标注不确定），冻结判定=partial_points（命中 ['P1-具体技术（名称或类别）']），相关层✓，充分层✓——宣称系统分析/分类各种压缩策略，但摘要未点名任何具体技术
- f06/definition：gold=topic_only，冻结判定=partial_points（命中 ['P1-缓存对象', 'P3-场景']），相关层✗，充分层✓——无
- f06/cost：gold=partial，冻结判定=partial_points（命中 ['P2-量级与占用']），相关层✓，充分层✓——占用话题（reduction of memory consumption）但无增长机制
- f06/techniques：gold=sufficient_support，冻结判定=partial_points（命中 ['P1-具体技术（名称或类别）']），相关层✓，充分层✗——点名 quantization-based 方法并陈述其实际效果

## 2. 冻结方法 × 新任务：**探索性跨任务审计**（python_web_frameworks，10 篇未用真实结果）

- 文档层相关性一致性：20/30（**非任务停止正确率**）

**跨域主题碰撞陷阱实测**：生物学 ecosystem 页面对 ecosystem 子问题——

- n14：命中要点 ['P1-扩展与包生态', 'P2-具体组件或社区']，全部要点命中=True
- n15：命中要点 ['P1-扩展与包生态']，全部要点命中=False
- n17：命中要点 ['P1-扩展与包生态']，全部要点命中=False

## 3. 敏感性分析（任务 3.1：S1/S3/S5 的 techniques 标注争议）

S1/S3/S5 的 techniques 候选标注（不充分）与判据（充分，由 e001 完整摘要证据驱动）冲突，
两种合理标注下各臂停止正确率（/5）：

| 变体 | 词法 | 语义@0.5 | 判据 |
|---|---|---|---|
| A-原标注 | 4/5 | 2/5 | 4/5 |
| B-替代标注(e001 佐证下 techniques 充分) | 3/5 | 3/5 | 5/5 |

## 4. 名称命中 vs 作用机制解释（任务 3.2，techniques 文档层）

| 文档 | 判据分类 | 机制解释（audit 层） | 候选标注 |
|---|---|---|---|
| e001 | condition_met | ✗ | topic_only |
| e003 | partial_points | ✗ | sufficient_support |
| e004 | partial_points | ✗ | topic_only |
| e008 | partial_points | ✗ | topic_only |
| e009 | partial_points | ✗ | topic_only |
| e010 | partial_points | ✗ | topic_only |
| e011 | condition_met | ✗ | sufficient_support |
| e013 | condition_met | ✗ | sufficient_support |
| e014 | condition_met | ✓ | sufficient_support |
| e015 | condition_met | ✗ | sufficient_support |
| H-syn-tech | condition_met | ✓ | sufficient_support |

## 5. 来源域多样性 vs 独立佐证（任务 3.3，快照结构分类）

结构分类：single_source（全部要点同一域）/ complementary（不同域覆盖不同要点）/ corroborative（多域重复覆盖同要点组合）。
域名计数是独立性的弱代理——同域多文档只计一次，但不同域也可能内容抄袭（本轮无法检测）。

| 快照/子问题 | 结构 | 域 | 判定 |
|---|---|---|---|
| S1-homogeneous-definition/definition | complementary | 3 | 充分 |
| S1-homogeneous-definition/techniques | complementary | 2 | 充分 |
| S2-pseudo-coverage-wrong-stop/definition | complementary | 6 | 充分 |
| S2-pseudo-coverage-wrong-stop/cost | corroborative | 4 | 不充分 |
| S2-pseudo-coverage-wrong-stop/techniques | complementary | 4 | 充分 |
| S3-real-after-round2/definition | complementary | 10 | 充分 |
| S3-real-after-round2/cost | complementary | 5 | 充分 |
| S3-real-after-round2/techniques | complementary | 6 | 充分 |
| S5-missing-condition/definition | complementary | 5 | 充分 |
| S5-missing-condition/cost | single_source | 1 | 不充分 |
| S5-missing-condition/techniques | complementary | 2 | 充分 |
| S6-real-final-state/definition | complementary | 14 | 充分 |
| S6-real-final-state/cost | complementary | 8 | 充分 |
| S6-real-final-state/techniques | complementary | 10 | 充分 |

## 6. 三层评价分离（任务 3.4）

- 文档层（要点命中）：`results/sufficiency_comparison.json` doc_level——逐文档逐子问题的要点命中与证据；
- 子问题层（充分性）：snapshots[].per_subq——要点覆盖、缺口、独立域、理由；
- 任务层（停止决策）：snapshots[].criteria_stop_suggestion——三臂对比见 `sufficiency_report.md`。
三层错误可分别发生：文档层误命中（如裸词 vram）不必然传导为子问题层误判（机制要点把关），
子问题层误判（如跨域碰撞）在任务层可能被其他子问题的缺口掩盖——分层报告使各层错误可归因。

## 7. 结论与退化（整改后如实修订）

1. 同任务新证据（独立 4 篇）：文档层相关性/充分级一致性见第 1 节（数字已随标注口径修订重算）；
   实测退化点 a：名词化表述（reduction 不含子串 reduce）致 f06/techniques 充分级降判 partial；
   实测退化 b：剩余 4 处相关性不一致全部为 definition 断言级页面（裸词 P1 命中判 partial，候选标注 topic_only）；
   f02 的动词缺口（eats）在标注下调后不再计为不一致，但其标题断言是否构成充分支持属标注不确定项；
2. 新任务（探索性跨任务审计）：框架对比正例可用，**裸词 ecosystem/community 的跨域碰撞陷阱实测成立**
（生物学页面命中全部要点）——从子问题文本起草要点时，主题词即碰撞源；
3. 敏感性：判据与词法的相对优劣在不同合理标注下是否翻转见第 3 节表（如实呈现，不选边）；
4. 机制解释层：名称命中≠机制解释（多数 techniques 文档无机制解释），该区分已可观测（第 4 节）。