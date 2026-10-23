# 演示运行记录：kv_cache_llm（真实 DuckDuckGo 检索）

- 运行时间(UTC)：2026-10-23T08:54:02+00:00 | 后端：ddg | 缓存模式：auto（本次运行真实网络调用 3 次）
- 检索轮数：3 / 记录 4 条 | 停止决策：**stop_sufficient**
- 效果反馈分布：{'helpful': 3}

> **指标口径**：score = 0.7×子问题关键词覆盖度 + 0.3×来源域名多样性，是充分性**代理分数**（词法、确定性），不代表语义充分性。“匹配增量”按子问题计，一篇文档支撑多个子问题时计多次，可大于唯一文档数。

## 逐轮元认知记录

### Round 1 — search
- 感知：唯一文档 0 篇，子问题相关文档数 {'definition': 0, 'cost': 0, 'techniques': 0}，来源域 0 个
- 评价：代理 score=0.0，verdict=insufficient
- 决策：initial → `KV cache transformer inference explained`（目标：None）
- 执行：候选 5 → 采纳 5（重复 0，离题 0）
- 反馈：新增唯一文档 5 篇 / 子问题匹配增量 6，效果=helpful
- 理由：证据不足：各子问题相关证据 {'definition': '0/2', 'cost': '0/2', 'techniques': '0/2'}（K=2，已达标: 无）；来源域 0 个，共 0 条，其中 definition、cost、techniques 完全无相关证据。最薄弱子问题: definition。

### Round 2 — search
- 感知：唯一文档 5 篇，子问题相关文档数 {'definition': 5, 'cost': 0, 'techniques': 1}，来源域 5 个
- 评价：代理 score=0.65，verdict=insufficient
- 决策：broaden → `Why does the KV cache consume so much GPU memory`（目标：cost）
- 执行：候选 5 → 采纳 5（重复 0，离题 0）
- 反馈：新增唯一文档 5 篇 / 子问题匹配增量 10，目标子问题 cost 相关文档 +5，效果=helpful
- 理由：证据不足：各子问题相关证据 {'definition': '5/2', 'cost': '0/2', 'techniques': '1/2'}（K=2，已达标: definition）；来源域 5 个，共 5 条，其中 cost 完全无相关证据。最薄弱子问题: cost。

### Round 3 — search
- 感知：唯一文档 10 篇，子问题相关文档数 {'definition': 10, 'cost': 5, 'techniques': 1}，来源域 10 个
- 评价：代理 score=0.883，verdict=insufficient
- 决策：target_weakest → `What techniques reduce KV cache memory usage`（目标：techniques）
- 执行：候选 5 → 采纳 5（重复 0，离题 0）
- 反馈：新增唯一文档 5 篇 / 子问题匹配增量 7，目标子问题 techniques 相关文档 +2，效果=helpful，检索经 1 次重试后成功
- 理由：证据不足：各子问题相关证据 {'definition': '10/2', 'cost': '5/2', 'techniques': '1/2'}（K=2，已达标: definition、cost）；来源域 10 个，共 10 条。最薄弱子问题: techniques。

### Round 4 — stop_sufficient
- 感知：唯一文档 15 篇，子问题相关文档数 {'definition': 14, 'cost': 6, 'techniques': 3}，来源域 14 个
- 评价：代理 score=1.0，verdict=sufficient
- 理由：证据充分：各子问题相关证据 {'definition': '14/2', 'cost': '6/2', 'techniques': '3/2'}（K=2，已达标: definition、cost、techniques）；来源域 14 个，共 15 条，且来源域≥2，可以停止检索。

## 最终证据清单（URL 可点击核对）

- R1 [definition] KV Cache Explained for LLM Inference - krunalkanojiya.com — https://krunalkanojiya.com/blog/kv-cache-explained
- R1 [definition] KV Cache Explained: Why LLMs Remember Keys and Values During Inference — https://learncodecamp.net/kv-cache-explained/
- R1 [techniques] KV Cache in LLMs Explained: How Transformers Make Inference Fast — https://www.tensortonic.com/llm-internals/kv-cache
- R1 [definition] KV Cache Explained with Examples from Real World LLMs — https://inference.net/content/kv-cache-explained/
- R1 [definition] The Complete Guide to Inference Caching in LLMs - Machine Learning Mastery — https://machinelearningmastery.com/the-complete-guide-to-inference-caching-in-llms/
- R2 [definition] KV Cache Explained: LLM Context and GPU Memory | Hivenet — https://www.hivenet.com/post/kv-cache-llm-gpu-memory-context-window
- R2 [cost] The KV Cache Survival Guide: Why Your GPU Runs Out of Memory ... — https://www.sitepoint.com/kv-cache-survival-guide-local-llms/
- R2 [cost] KV Cache Memory Usage in LLMs – Formulas & Examples — https://unanswered.io/guide/kv-cache-memory-usage
- R2 [cost] KV Cache Explained: Why It Eats Your VRAM GIGAGPU — https://gigagpu.com/kv-cache-explained-vram/
- R2 [cost] KV Cache Optimization: Serve 10x More Users per GPU (2026 ... — https://www.spheron.network/blog/kv-cache-optimization-guide/
- R3 [definition] KV Cache Optimization Strategies for Scalable - arXiv.org — https://arxiv.org/html/2603.20397v1
- R3 [definition] KV Cache Optimization Strategies for Scalable and Efficient LLM Inference — https://arxiv.org/pdf/2603.20397
- R3 [definition] The Ultimate Guide to KV Cache Optimization for LLM Inference (2026) — https://www.gpuyard.com/tutorials/howto/optimize-kv-cache/
- R3 [definition] Top 10 KV Cache Compression Techniques for LLM Inference: Reducing ... — https://metaailabs.com/top-10-kv-cache-compression-techniques-for-llm-inference-reducing-memory-overhead-across-eviction-quantization-and-low-rank-methods/
- R3 [techniques] KV-Cache Compression Techniques - emergentmind.com — https://www.emergentmind.com/topics/kv-cache-compression-techniques
