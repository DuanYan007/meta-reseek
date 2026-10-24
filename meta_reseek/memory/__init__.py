"""P1-b memory foundation.

WorkingMemory  — 任务内工作记忆：P0 DecisionLog/EvidenceStore 的只读视图，
                 不建立第二状态源，不参与任何决策。
EpisodicMemory — 任务经历库：把 RoundRecord 投影为完整经历
                 （调整前状态 → 调整动作 → 调整理由 → 检索反馈 → 实际结果）
                 并以版本化 JSONL 持久化，提供最小查询接口。

边界（任务书第七节）：不做跨任务策略学习 / 参数自动更新 / 元元认知校准 / RSI。
"""

from .episodic import EpisodicMemory, SCHEMA_VERSION, episodes_from_log
from .working import WorkingMemory

__all__ = ["WorkingMemory", "EpisodicMemory", "episodes_from_log", "SCHEMA_VERSION"]
