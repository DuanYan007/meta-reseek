# 演示运行记录：python_web_frameworks（真实 DuckDuckGo 检索）

- 运行时间(UTC)：2026-10-23T08:54:27+00:00 | 后端：ddg | 缓存模式：auto（本次运行真实网络调用 3 次）
- 检索轮数：3 / 记录 4 条 | 停止决策：**stop_sufficient**
- 效果反馈分布：{'helpful': 3}

> **指标口径**：score = 0.7×子问题关键词覆盖度 + 0.3×来源域名多样性，是充分性**代理分数**（词法、确定性），不代表语义充分性。“匹配增量”按子问题计，一篇文档支撑多个子问题时计多次，可大于唯一文档数。

## 逐轮元认知记录

### Round 1 — search
- 感知：唯一文档 0 篇，子问题相关文档数 {'performance': 0, 'use_cases': 0, 'ecosystem': 0}，来源域 0 个
- 评价：代理 score=0.0，verdict=insufficient
- 决策：initial → `Flask FastAPI Django comparison REST API`（目标：None）
- 执行：候选 5 → 采纳 5（重复 0，离题 0）
- 反馈：新增唯一文档 5 篇 / 子问题匹配增量 7，效果=helpful，检索经 1 次重试后成功
- 理由：证据不足：各子问题相关证据 {'performance': '0/2', 'use_cases': '0/2', 'ecosystem': '0/2'}（K=2，已达标: 无）；来源域 0 个，共 0 条，其中 performance、use_cases、ecosystem 完全无相关证据。最薄弱子问题: performance。

### Round 2 — search
- 感知：唯一文档 5 篇，子问题相关文档数 {'performance': 5, 'use_cases': 1, 'ecosystem': 1}，来源域 5 个
- 评价：代理 score=0.767，verdict=insufficient
- 决策：target_weakest → `Which framework fits which use case microservices vs full website`（目标：use_cases）
- 执行：候选 5 → 采纳 5（重复 0，离题 0）
- 反馈：新增唯一文档 5 篇 / 子问题匹配增量 5，目标子问题 use_cases 相关文档 +5，效果=helpful
- 理由：证据不足：各子问题相关证据 {'performance': '5/2', 'use_cases': '1/2', 'ecosystem': '1/2'}（K=2，已达标: performance）；来源域 5 个，共 5 条。最薄弱子问题: use_cases。

### Round 3 — search
- 感知：唯一文档 10 篇，子问题相关文档数 {'performance': 5, 'use_cases': 6, 'ecosystem': 1}，来源域 10 个
- 评价：代理 score=0.883，verdict=insufficient
- 决策：target_weakest → `How do their ecosystems and extensions compare`（目标：ecosystem）
- 执行：候选 5 → 采纳 1（重复 0，离题 4）
- 反馈：新增唯一文档 1 篇 / 子问题匹配增量 1，目标子问题 ecosystem 相关文档 +1，效果=helpful
- 理由：证据不足：各子问题相关证据 {'performance': '5/2', 'use_cases': '6/2', 'ecosystem': '1/2'}（K=2，已达标: performance、use_cases）；来源域 10 个，共 10 条。最薄弱子问题: ecosystem。

### Round 4 — stop_sufficient
- 感知：唯一文档 11 篇，子问题相关文档数 {'performance': 5, 'use_cases': 6, 'ecosystem': 2}，来源域 11 个
- 评价：代理 score=1.0，verdict=sufficient
- 理由：证据充分：各子问题相关证据 {'performance': '5/2', 'use_cases': '6/2', 'ecosystem': '2/2'}（K=2，已达标: performance、use_cases、ecosystem）；来源域 11 个，共 11 条，且来源域≥2，可以停止检索。

## 最终证据清单（URL 可点击核对）

- R1 [performance] Comparison of FastAPI with Django and Flask - GeeksforGeeks — https://www.geeksforgeeks.org/python/comparison-of-fastapi-with-django-and-flask/
- R1 [performance] FastAPI vs Django vs Flask: A Comprehensive Framework Comparison — https://betterstack.com/community/guides/scaling-nodejs/fastapi-vs-django-vs-flask/
- R1 [performance] Django vs Flask vs FastAPI: 106K vs 13K req/s [2026] — https://tech-insider.org/django-vs-flask-vs-fastapi-2026/
- R1 [performance] Which Is the Best Python Web Framework: Django, Flask, or ... — https://blog.jetbrains.com/pycharm/2025/02/django-flask-fastapi/
- R1 [performance] Comparing Python Web Frameworks: Django, Flask, and FastAPIFastAPI vs Django REST vs Flask: Who Wins in 2025?Django vs FastAPI vs Flask: Choosing the Right Python ... — https://www.capitalnumbers.com/blog/django-vs-flask-vs-fastapi
- R2 [use_cases] Monolith vs Microservices Decision Framework 2026 ... — https://www.agilesoftlabs.com/blog/2026/02/monolith-vs-microservices-decision
- R2 [use_cases] Microservices vs. Monolith in 2026: A Practical Decision ... — https://outplane.com/blog/microservices-vs-monolith
- R2 [use_cases] Microservices vs Monolith: Choosing the Right Fit (2026) — https://nordiso.com/blog/microservices-vs-monolith-architecture-choosing-the-right-fit
- R2 [use_cases] Monolith vs Microservices vs Micro-Frontend Guide — https://betatestsolutions.com/blog/micro-frontend-vs-monolith-the-ui-scaling-secret/
- R2 [use_cases] Microservices vs Monolith: A Decision Framework | 2026 — https://www.developers.dev/tech-talk/microservices-vs-monolith-a-pragmatic-decision-framework-for-engineering-leaders.html
- R3 [ecosystem] Ecosystems · Ecosystems Extension · UHELP — https://www.ecosystemsandlandcare.org/ecosystems
