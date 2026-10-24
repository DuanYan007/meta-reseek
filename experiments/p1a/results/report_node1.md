# P1-a 第一交付节点：词法基线在固定案例集上的误判记录（四级标注修订版）

- 案例集：19 案例（14 条真实搜索结果标题与摘要 + 5 构造，同源 e012 已并入 e011），来源与候选标注见 cases.json
- 标注状态：CANDIDATE（GLM 起草，待核查）；四级标准，二值切点=partial 及以上
- 文档层混淆矩阵（相关性切点）：{'TP': 17, 'FP': 8, 'FN': 7, 'TN': 25}（共 57 对）
- 词法接受项的真实级别分布：{'sufficient_support': 11, 'partial': 6, 'topic_only': 8}（接受但仅 topic_only 的即伪相关）

## 文档层误判明细（含词法命中/缺失词条，供误因分析）

- [real] e003 → cost：gold=partial pred=False，词法分 0.077；命中词条 ['memory', 'kv', 'cache']；缺失 ['gpu', 'sequence length', 'batch size', 'vram', 'bottleneck', 'consume']
  - 标注依据：含 memory math 要点，提供部分量化信息，未给增长机制
- [real] e008 → definition：gold=topic_only pred=True，词法分 0.188；命中词条 ['kv cache']；缺失 ['key', 'value', 'attention', 'self attention', 'inference', 'transformer']
  - 标注依据：同域主题，摘要只讲用量不讲定义
- [real] e009 → definition：gold=topic_only pred=True，词法分 0.312；命中词条 ['kv cache', 'inference']；缺失 ['key', 'value', 'attention', 'self attention', 'transformer']
  - 标注依据：未解释定义
- [real] e010 → definition：gold=topic_only pred=True，词法分 0.188；命中词条 ['kv cache']；缺失 ['key', 'value', 'attention', 'self attention', 'inference', 'transformer']
  - 标注依据：无定义内容
- [real] e011 → definition：gold=topic_only pred=True，词法分 0.312；命中词条 ['kv cache', 'attention']；缺失 ['key', 'value', 'self attention', 'inference', 'transformer']
  - 标注依据：综述不提供入门定义
- [real] e011 → techniques：gold=sufficient_support pred=False，词法分 0.149；命中词条 ['techniques', 'kv', 'cache', 'memory']；缺失 ['mqa', 'gqa', 'grouped query attention', 'multi query attention', 'pagedattention', 'quantization']
  - 标注依据：系统综述各类 KV cache 管理技术；注：同一论文的 html/pdf 双版本曾被系统同时接受（去重未命中），案例集按单一来源计
- [real] e013 → definition：gold=topic_only pred=True，词法分 0.312；命中词条 ['kv cache', 'inference']；缺失 ['key', 'value', 'attention', 'self attention', 'transformer']
  - 标注依据：无定义解释
- [real] e014 → definition：gold=topic_only pred=True，词法分 0.312；命中词条 ['kv cache', 'inference']；缺失 ['key', 'value', 'attention', 'self attention', 'transformer']
  - 标注依据：无定义内容
- [real] e014 → techniques：gold=sufficient_support pred=False，词法分 0.149；命中词条 ['techniques', 'kv', 'cache', 'memory']；缺失 ['mqa', 'gqa', 'grouped query attention', 'multi query attention', 'pagedattention', 'quantization']
  - 标注依据：Top 10 压缩技术清单
- [fn_paraphrase(同义改写漏检)] B-syn-def → definition：gold=sufficient_support pred=False，词法分 0.125；命中词条 ['attention']；缺失 ['kv cache', 'key', 'value', 'self attention', 'inference', 'transformer']
  - 标注依据：构造：同义改写完整解释缓存机制（memoize past states）
- [fp_topic_overlap(主题词重叠伪相关)] C-topic-cost → cost：gold=topic_only pred=True，词法分 0.231；命中词条 ['memory', 'gpu', 'vram']；缺失 ['sequence length', 'batch size', 'bottleneck', 'kv', 'cache', 'consume']
  - 标注依据：构造：GPU memory 主题词重叠，但对『KV cache 为何耗显存』无任何回答信息
- [fn_jargon(行话表述漏检)] E-jargon-cost → definition：gold=partial pred=False，词法分 0.0；命中词条 []；缺失 ['kv cache', 'key', 'value', 'attention', 'self attention', 'inference']
  - 标注依据：构造：以行话描述逐 token 状态累积现象，隐含机制但未命名 KV cache
- [fn_jargon(行话表述漏检)] E-jargon-cost → cost：gold=sufficient_support pred=False，词法分 0.026；命中词条 ['memory']；缺失 ['gpu', 'sequence length', 'batch size', 'vram', 'bottleneck', 'kv']
  - 标注依据：构造：HBM 耗尽 + 随上下文累积的机制表述，真实相关但词法难命中
- [fn_paraphrase(同义改写漏检)] H-syn-tech → techniques：gold=sufficient_support pred=False，词法分 0.021；命中词条 ['memory']；缺失 ['mqa', 'gqa', 'grouped query attention', 'multi query attention', 'pagedattention', 'quantization']
  - 标注依据：构造：同义表述（sharing heads / compressing cached states）概括两类缩减手段
- [missing_condition(覆盖主题缺关键条件)] CALC-missing-why → definition：gold=topic_only pred=True，词法分 0.188；命中词条 ['kv cache']；缺失 ['key', 'value', 'attention', 'self attention', 'inference', 'transformer']
  - 标注依据：同域主题，无定义

## 标注不确定性记录（3 条，人工核查优先项）

- e003→cost（partial）：不确定：摘要仅列要点名（memory math）而无展开，partial 与 topic_only 边界依赖全文，人工核查优先
- E-jargon-cost→definition（partial）：不确定：『隐含机制』是否构成 definition 的部分回答依赖解读，人工核查优先
- CALC-missing-why→cost（partial）：不确定：决定因子列表是否算『部分回答信息』存在解释空间（也可视作仅主题命中），人工核查优先

## 快照层停止建议 vs 候选充分性标注

| 快照 | 评价器判定 | 停止建议 | 标注应为 | 判定正确 |
|---|---|---|---|---|
| S1-homogeneous-definition | insufficient(0.458) | continue | continue | ✅ |
| S2-pseudo-coverage-wrong-stop | sufficient(1.0) | stop | continue | ❌ |
| S3-real-after-round2 | insufficient(0.883) | continue | continue | ✅ |
| S5-missing-condition | insufficient(0.883) | continue | continue | ✅ |
| S6-real-final-state | sufficient(1.0) | stop | stop | ✅ |

## 子问题层覆盖误判（快照内）

- S2-pseudo-coverage-wrong-stop/cost：评价器认为已覆盖（3 条），标注=不充分——仅 e010/CALC 部分回答 + C 仅主题相关；无任何文档给出增长机制——主题覆盖≠回答条件满足
- S5-missing-condition/cost：评价器认为已覆盖（2 条），标注=不充分——e003/CALC 均为部分回答、C 仅主题相关——无增长机制，回答条件未满足