# P1-a 最小实验报告：词法评价器失误模式与语义模块检验

- 案例集：12 篇文档 × 3 子问题 = 36 对（gold 人工标注）
- 词法臂（现行生产逻辑）混淆矩阵：{'TP': 4, 'FP': 4, 'FN': 5, 'TN': 23}
- 语义臂：sentence-transformers/all-MiniLM-L6-v2，余弦相似度
- 分离度（min 正对相似度 − max 负对相似度）：-0.3628
  - 正对最小 0.31 / 负对最大 0.6728
- 探索性固定阈值结果：{'0.4': {'TP': 6, 'FP': 9, 'FN': 3, 'TN': 18}, '0.5': {'TP': 4, 'FP': 5, 'FN': 5, 'TN': 22}, '0.6': {'TP': 3, 'FP': 2, 'FN': 6, 'TN': 25}}

## 词法失误明细（gold vs 词法判定）

- [FN] B-fn-definition-paraphrase（fn_paraphrase）→ 子问题 definition：词法分 0.125，语义相似度 0.3909
- [FP] C-fp-cost-topic-overlap（fp_topic_overlap）→ 子问题 cost：词法分 0.231，语义相似度 0.4806
- [FN] E-fn-cost-jargon（fn_jargon）→ 子问题 cost：词法分 0.026，语义相似度 0.3895
- [FP] G-tp-techniques（tp_baseline）→ 子问题 definition：词法分 0.562，语义相似度 0.3352
- [FN] H-fn-techniques-paraphrase（fn_paraphrase）→ 子问题 techniques：词法分 0.021，语义相似度 0.4319
- [FN] I-tp-multi（tp_multi）→ 子问题 cost：词法分 0.179，语义相似度 0.7789
- [FP] J-fp-definition-bait（fp_lexical_bait）→ 子问题 definition：词法分 0.25，语义相似度 0.3663
- [FP] K-tp-techniques-quant（tp_baseline）→ 子问题 definition：词法分 0.312，语义相似度 0.5985
- [FN] K-tp-techniques-quant（tp_baseline）→ 子问题 techniques：词法分 0.149，语义相似度 0.4996

## 语义臂对上述失误的判定（阈值 0.5，探索性）

- B-fn-definition-paraphrase（FN，期望语义判 positive）→ 实际 negative ❌ 未修正
- C-fp-cost-topic-overlap（FP，期望语义判 negative）→ 实际 negative ✅ 修正
- E-fn-cost-jargon（FN，期望语义判 positive）→ 实际 negative ❌ 未修正
- G-tp-techniques（FP，期望语义判 negative）→ 实际 negative ✅ 修正
- H-fn-techniques-paraphrase（FN，期望语义判 positive）→ 实际 negative ❌ 未修正
- I-tp-multi（FN，期望语义判 positive）→ 实际 positive ✅ 修正
- J-fp-definition-bait（FP，期望语义判 negative）→ 实际 negative ✅ 修正
- K-tp-techniques-quant（FP，期望语义判 negative）→ 实际 positive ❌ 未修正
- K-tp-techniques-quant（FN，期望语义判 positive）→ 实际 negative ❌ 未修正

## 口径与限定（按评审意见）

- 嵌入相似度是**相关性**代理，不能直接证明证据充分性；本实验只检验“具体缺口识别”层面的失误修正，不比较 score 数值本身。
- 案例集极小（12 篇），且由构建者标注 gold；结论仅用于定位失误模式与决定 P1-a 方向，不作为性能结论。
- 固定阈值为探索性；分离度是免阈值指标。