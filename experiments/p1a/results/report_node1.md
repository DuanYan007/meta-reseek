# P1-a 第一交付节点：词法基线在固定案例集上的误判记录

- 案例集：20 案例（15 真实检索结果 + 5 构造），来源与候选标注见 cases.json
- 标注状态：CANDIDATE（GLM 起草，待核查）
- 文档层混淆矩阵：{'TP': 15, 'FP': 11, 'FN': 7, 'TN': 27}（共 60 对）

## 文档层误判明细（含词法命中/缺失词条，供误因分析）

- [real] e003 → cost：gold=True pred=False，词法分 0.077；命中词条 ['memory', 'kv', 'cache']；缺失 ['gpu', 'sequence length', 'batch size', 'vram', 'bottleneck', 'consume']
  - 标注依据：含 memory math（显存计算）
- [real] e008 → definition：gold=False pred=True，词法分 0.188；命中词条 ['kv cache']；缺失 ['key', 'value', 'attention', 'self attention', 'inference', 'transformer']
  - 标注依据：只讲用量，不讲定义
- [real] e009 → definition：gold=False pred=True，词法分 0.312；命中词条 ['kv cache', 'inference']；缺失 ['key', 'value', 'attention', 'self attention', 'transformer']
  - 标注依据：未解释定义
- [real] e010 → definition：gold=False pred=True，词法分 0.188；命中词条 ['kv cache']；缺失 ['key', 'value', 'attention', 'self attention', 'inference', 'transformer']
  - 标注依据：无
- [real] e011 → definition：gold=False pred=True，词法分 0.312；命中词条 ['kv cache', 'attention']；缺失 ['key', 'value', 'self attention', 'inference', 'transformer']
  - 标注依据：综述不提供入门定义
- [real] e011 → techniques：gold=True pred=False，词法分 0.149；命中词条 ['techniques', 'kv', 'cache', 'memory']；缺失 ['mqa', 'gqa', 'grouped query attention', 'multi query attention', 'pagedattention', 'quantization']
  - 标注依据：系统综述各类 KV cache 管理技术
- [real] e012 → definition：gold=False pred=True，词法分 0.438；命中词条 ['kv cache', 'attention', 'inference']；缺失 ['key', 'value', 'self attention', 'transformer']
  - 标注依据：同 e011
- [real] e012 → techniques：gold=True pred=False，词法分 0.149；命中词条 ['techniques', 'kv', 'cache', 'memory']；缺失 ['mqa', 'gqa', 'grouped query attention', 'multi query attention', 'pagedattention', 'quantization']
  - 标注依据：同 e011（与 e011 为同一论文 html/pdf 双版本——同质重复）
- [real] e013 → definition：gold=False pred=True，词法分 0.312；命中词条 ['kv cache', 'inference']；缺失 ['key', 'value', 'attention', 'self attention', 'transformer']
  - 标注依据：无定义解释
- [real] e014 → definition：gold=False pred=True，词法分 0.312；命中词条 ['kv cache', 'inference']；缺失 ['key', 'value', 'attention', 'self attention', 'transformer']
  - 标注依据：无
- [real] e014 → cost：gold=False pred=True，词法分 0.282；命中词条 ['memory', 'gpu', 'kv', 'cache', 'consume']；缺失 ['sequence length', 'batch size', 'vram', 'bottleneck', 'so', 'much']
  - 标注依据：只给参数/缓存用量对比数字
- [real] e014 → techniques：gold=True pred=False，词法分 0.149；命中词条 ['techniques', 'kv', 'cache', 'memory']；缺失 ['mqa', 'gqa', 'grouped query attention', 'multi query attention', 'pagedattention', 'quantization']
  - 标注依据：Top 10 压缩技术清单
- [fn_paraphrase(同义改写漏检)] B-syn-def → definition：gold=True pred=False，词法分 0.125；命中词条 ['attention']；缺失 ['kv cache', 'key', 'value', 'self attention', 'inference', 'transformer']
  - 标注依据：构造：同义改写解释缓存机制（memoize past states），无词面重叠
- [fp_topic_overlap(主题词重叠伪相关)] C-topic-cost → cost：gold=False pred=True，词法分 0.231；命中词条 ['memory', 'gpu', 'vram']；缺失 ['sequence length', 'batch size', 'bottleneck', 'kv', 'cache', 'consume']
  - 标注依据：构造：游戏显卡 VRAM 选购，主题词重叠（GPU memory）但与 KV cache 增长原因无关
- [fn_jargon(行话表述漏检)] E-jargon-cost → cost：gold=True pred=False，词法分 0.026；命中词条 ['memory']；缺失 ['gpu', 'sequence length', 'batch size', 'vram', 'bottleneck', 'kv']
  - 标注依据：构造：以行话（HBM/中间态累积/上下文长度）表述显存耗尽原因——真实相关但词法难命中
- [fn_paraphrase(同义改写漏检)] H-syn-tech → techniques：gold=True pred=False，词法分 0.021；命中词条 ['memory']；缺失 ['mqa', 'gqa', 'grouped query attention', 'multi query attention', 'pagedattention', 'quantization']
  - 标注依据：构造：同义表述（sharing heads / compressing cached states）概括两类缩减手段，无 MQA/GQA 等术语
- [missing_condition(覆盖主题缺关键条件)] CALC-missing-why → definition：gold=False pred=True，词法分 0.188；命中词条 ['kv cache']；缺失 ['key', 'value', 'attention', 'self attention', 'inference', 'transformer']
  - 标注依据：无
- [missing_condition(覆盖主题缺关键条件)] CALC-missing-why → cost：gold=False pred=True，词法分 0.179；命中词条 ['memory', 'gpu', 'kv', 'cache']；缺失 ['sequence length', 'batch size', 'vram', 'bottleneck', 'consume', 'so']
  - 标注依据：构造：用量计算器（数字/公式模板），主题高度相关但完全不含『为何增长』的机制信息——缺关键回答条件

## 快照层停止建议 vs 候选充分性标注

| 快照 | 评价器判定 | 停止建议 | 标注应为 | 判定正确 |
|---|---|---|---|---|
| S1-homogeneous-definition | insufficient(0.458) | continue | continue | ✅ |
| S2-pseudo-coverage-wrong-stop | sufficient(1.0) | stop | continue | ❌ |
| S3-real-after-round2 | insufficient(0.883) | continue | continue | ✅ |
| S5-missing-condition | insufficient(0.883) | continue | continue | ✅ |
| S6-real-final-state | sufficient(1.0) | stop | stop | ✅ |

## 子问题层覆盖误判（快照内）

- S2-pseudo-coverage-wrong-stop/cost：评价器认为已覆盖（3 条），标注=不充分——仅 e009 真正解释原因；C（游戏选购）与 CALC（只有数字无机制）为伪相关，关键信息不足
- S5-missing-condition/cost：评价器认为已覆盖（2 条），标注=不充分——CALC 只有数字、C 是游戏页——无任何『为何增长』信息，主题覆盖≠回答条件满足