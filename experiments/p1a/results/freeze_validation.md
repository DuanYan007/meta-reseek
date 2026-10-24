# P1-a 任务 3：充分性判据核查（冻结规则盲测 + 敏感性 + 分层审计）

**冻结协议**：`sufficiency_criteria.py` 全程零修改；新任务要点仅依据其任务文件子问题文本与 keywords 起草并先行登记（`criteria_audit.py`），之后才对新证据做候选标注。

## 1. 冻结规则 × 同任务新证据（2 个新查询、去同源后 5 篇，标注 CANDIDATE）

- 相关性层（partial 及以上算相关）一致性：11/15
- 充分支持层（condition_met）一致性：12/15

逐条：

- f01/definition：gold=topic_only，冻结判定=partial_points（命中 ['P1-缓存对象', 'P3-场景']），相关层✗，充分层✓——未描述缓存机制本身
- f01/cost：gold=partial，冻结判定=partial_points（命中 ['P2-量级与占用']），相关层✓，充分层✓——标题宣称 mechanics/calculations，摘要未见增长关系表述
- f01/techniques：gold=topic_only，冻结判定=topic_or_less（命中 []），相关层✓，充分层✓——无
- f02/definition：gold=topic_only，冻结判定=partial_points（命中 ['P1-缓存对象']），相关层✗，充分层✓——无机制描述
- f02/cost：gold=sufficient_support，冻结判定=partial_points（命中 ['P2-量级与占用']），相关层✓，充分层✗——标题即直接陈述增长关系（Context Length 吃掉 VRAM）
- f02/techniques：gold=topic_only，冻结判定=topic_or_less（命中 []），相关层✓，充分层✓——And How to Fix It 仅暗示存在手段，未点名
- f03/definition：gold=partial，冻结判定=partial_points（命中 ['P1-缓存对象', 'P3-场景']），相关层✓，充分层✓——foundational optimization/eliminating redundant 隐含机制
- f03/cost：gold=topic_only，冻结判定=topic_or_less（命中 []），相关层✓，充分层✓——无占用/增长内容
- f03/techniques：gold=partial，冻结判定=partial_points（命中 ['P2-作用方式（缩减/管理）']），相关层✓，充分层✓——优化策略综述，但摘要未点名具体技术
- f04/definition：gold=topic_only，冻结判定=partial_points（命中 ['P1-缓存对象']），相关层✗，充分层✓——无
- f04/cost：gold=topic_only，冻结判定=topic_or_less（命中 []），相关层✓，充分层✓——无
- f04/techniques：gold=sufficient_support，冻结判定=partial_points（命中 ['P1-具体技术（名称或类别）']），相关层✓，充分层✗——系统化的压缩方法分类研究
- f06/definition：gold=topic_only，冻结判定=partial_points（命中 ['P1-缓存对象', 'P3-场景']），相关层✗，充分层✓——无
- f06/cost：gold=partial，冻结判定=partial_points（命中 ['P2-量级与占用']），相关层✓，充分层✓——占用话题（reduction of memory consumption）但无增长机制
- f06/techniques：gold=sufficient_support，冻结判定=partial_points（命中 ['P1-具体技术（名称或类别）']），相关层✓，充分层✗——讨论 quantization-based 压缩方法

## 2. 冻结方法 × 新任务（python_web_frameworks，10 篇未用真实结果，含跨域陷阱）

- 相关性层一致性：20/30

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

## 7. 结论与退化（如实）

1. 同任务新证据：相关性层基本保持，充分层出现退化——新增长关系动词（eats）、
   名词化表述（reduction 不含子串 reduce）未入冻结模式，f02/f06 判 partial 而候选标注为充分支持；
2. 新任务：框架对比正例可用，但**裸词 ecosystem/community 的跨域碰撞陷阱实测成立**
（生物学页面命中全部要点）——冻结协议从子问题文本起草要点时，主题词即碰撞源；
3. 敏感性：判据与词法的相对优劣在不同合理标注下是否翻转见第 3 节表（如实呈现，不选边）；
4. 机制解释层：名称命中≠机制解释（多数 techniques 文档无机制解释），该区分已可观测（第 4 节）。