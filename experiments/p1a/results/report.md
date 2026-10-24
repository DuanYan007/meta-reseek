# P1-a 最小实验报告（固定案例集：词法基线 vs 语义模块）

- 案例集：19 案例（14 条真实搜索结果标题与摘要 + 5 构造）× 3 子问题；快照 5 个；标注状态：CANDIDATE（GLM 起草，未经核查，非金标准）
- 词法臂（现行生产逻辑，阈值 0.15/边际 0.6）：{'TP': 17, 'FP': 8, 'FN': 7, 'TN': 25}（接受 25 对，成色 {'sufficient_support': 11, 'partial': 6, 'topic_only': 8}）
- 语义臂（sentence-transformers/all-MiniLM-L6-v2，主阈值 0.5，同一接受规则形状）：{'TP': 18, 'FP': 20, 'FN': 6, 'TN': 13}（接受 38 对，成色 {'sufficient_support': 13, 'topic_only': 20, 'partial': 5}）
- 免阈值分离度：min 正对 0.3219 − max 负对 0.6995 = -0.3776
- 探索性阈值对照：@0.4 接受 46（{'sufficient_support': 14, 'topic_only': 25, 'partial': 7}，错 28）；@0.5 接受 38（{'sufficient_support': 13, 'topic_only': 20, 'partial': 5}，错 26）；@0.6 接受 22（{'sufficient_support': 12, 'partial': 4, 'topic_only': 6}，错 14）

## 一、词法基线的具体误判（第一交付节点，数据驱动重述）

词法臂共 15 处误判（FN 7 / FP 8），逐条明细见 `report_node1.md`（由 run_baseline.py 同口径生成）。

标注不确定性记录（3 条，人工核查优先项）：
- e003→cost（partial）：不确定：摘要仅列要点名（memory math）而无展开，partial 与 topic_only 边界依赖全文，人工核查优先
- E-jargon-cost→definition（partial）：不确定：『隐含机制』是否构成 definition 的部分回答依赖解读，人工核查优先
- CALC-missing-why→cost（partial）：不确定：决定因子列表是否算『部分回答信息』存在解释空间（也可视作仅主题命中），人工核查优先

## 二、语义模块修正了哪些误判（第二交付节点）

- ✅ C-topic-cost/cost
- ✅ e010/definition
- ✅ e011/techniques
- ✅ e014/techniques

## 三、语义模块引入的新错误

- ❌ CALC-missing-why/techniques（词法判对，语义判错；相似度 0.6995）
- ❌ e001/techniques（词法判对，语义判错；相似度 0.5691）
- ❌ e002/cost（词法判对，语义判错；相似度 0.5306）
- ❌ e002/techniques（词法判对，语义判错；相似度 0.5569）
- ❌ e004/techniques（词法判对，语义判错；相似度 0.5327）
- ❌ e006/definition（词法判对，语义判错；相似度 0.4999）
- ❌ e006/techniques（词法判对，语义判错；相似度 0.5636）
- ❌ e007/techniques（词法判对，语义判错；相似度 0.611）
- ❌ e008/techniques（词法判对，语义判错；相似度 0.6719）
- ❌ e009/techniques（词法判对，语义判错；相似度 0.6237）
- ❌ e010/techniques（词法判对，语义判错；相似度 0.5726）
- ❌ e011/cost（词法判对，语义判错；相似度 0.5928）
- ❌ e013/cost（词法判对，语义判错；相似度 0.5294）
- ❌ e015/cost（词法判对，语义判错；相似度 0.5102）
- ❌ e015/definition（词法判对，语义判错；相似度 0.5178）

## 四、对搜索决策（继续/调整/停止）的影响

| 快照 | 词法 | 语义@0.4 | 语义@0.5 | 语义@0.6 | 标注应为 |
|---|---|---|---|---|---|
| S1-homogeneous-definition | continue(✓) stop(✗) | continue(✓) | continue(✓) | continue |
| S2-pseudo-coverage-wrong-stop | stop(✗) stop(✗) | stop(✗) | stop(✗) | continue |
| S3-real-after-round2 | continue(✓) stop(✗) | stop(✗) | stop(✗) | continue |
| S5-missing-condition | continue(✓) stop(✗) | stop(✗) | continue(✓) | continue |
| S6-real-final-state | stop(✓) stop(✓) | stop(✓) | stop(✓) | stop |

停止建议正确率：词法 4/5；语义@0.4 1/5、语义@0.5 2/5、语义@0.6 3/5。

## 五、仅靠语义相关性仍无法解决的充分性问题

1. **冗余≠覆盖**：同质文档相似度同样高，成对相似度表达不了集合的边际信息量；
2. **主题相似≠回答条件满足**：主题高度相似的文档可能不含子问题的关键回答要点；
3. **相似度不构成充分性证明**：充分性仍需结构性证据（覆盖、多样性、关键条件）。

## 口径与限定

- 全部比较基于固定证据快照（静态，证据=标题与摘要），未做动态检索实验；
- 案例集由 GLM 设计与候选标注（未经核查），结论用于定位问题而非性能宣称；
- 语义阈值为探索性；模型为通用小型嵌入模型，未微调。