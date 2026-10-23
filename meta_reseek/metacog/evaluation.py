"""Evaluation: judge whether current evidence is sufficient to stop.

Deterministic and explainable by design: every verdict lists the factor
values that produced it, so a reviewer can audit each stop/continue call.
This is the baseline metacognitive evaluator; P1+ may add semantic or
model-based judges behind the same interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..task import TaskSpec
from .perception import Snapshot

# --- thresholds (single source of truth; surfaced in every run trace) ----
W_COVERAGE = 0.7          # weight of sub-question coverage in the score
W_DIVERSITY = 0.3         # weight of source diversity in the score
DIVERSITY_TARGET = 4      # distinct domains counted as "fully diverse"
MIN_ROUNDS_BEFORE_STALL = 3  # diminishing-return stop not allowed earlier
STALL_WINDOW = 2          # consecutive low-gain rounds that count as stalling
STALL_GAIN = 1            # a round adding < this many new relevant items is low-gain


@dataclass
class Assessment:
    score: float
    verdict: str  # "sufficient" | "insufficient" | "diminishing"
    factors: dict[str, float] = field(default_factory=dict)
    weakest: str | None = None
    rationale: str = ""

    def as_dict(self) -> dict:
        return {
            "score": round(self.score, 3),
            "verdict": self.verdict,
            "factors": {k: round(v, 3) for k, v in self.factors.items()},
            "weakest": self.weakest,
            "rationale": self.rationale,
        }


def evaluate(
    snapshot: Snapshot,
    task: TaskSpec,
    recent_gains: list[int],
    error_rounds_in_window: int = 0,
) -> Assessment:
    """recent_gains: new *relevant* items added per past round (index 0 = round 1).

    error_rounds_in_window: how many of the last STALL_WINDOW rounds failed at
    the transport level (no response at all). Zero gain from a broken channel
    must not be attributed to the strategy itself.
    """
    k = task.min_relevant_per_subq
    coverage = snapshot.coverage_score(k)
    diversity_norm = min(snapshot.domain_count / DIVERSITY_TARGET, 1.0)
    score = W_COVERAGE * coverage + W_DIVERSITY * diversity_norm

    counts = {sid: v.relevant_count for sid, v in snapshot.per_subq.items()}
    weakest = snapshot.weakest_subq(k)
    met = [sid for sid, c in counts.items() if c >= k]
    missing = [sid for sid, c in counts.items() if c == 0]

    factors = {
        "coverage": coverage,
        "diversity": diversity_norm,
        "domain_count": float(snapshot.domain_count),
        "total_items": float(snapshot.total_items),
        "recent_gains": float(sum(recent_gains[-STALL_WINDOW:]) if recent_gains else 0.0),
    }

    def _detail() -> str:
        met_txt = "、".join(met) if met else "无"
        short = {sid: f"{c}/{k}" for sid, c in counts.items()}
        return (
            f"各子问题相关证据 {short}（K={k}，已达标: {met_txt}）；"
            f"来源域 {snapshot.domain_count} 个，共 {snapshot.total_items} 条"
        )

    # 1) sufficient: every sub-question covered AND at least two source domains
    if len(met) == len(counts) and snapshot.domain_count >= 2:
        return Assessment(
            score=score,
            verdict="sufficient",
            factors=factors,
            weakest=weakest,
            rationale=f"证据充分：{_detail()}，且来源域≥2，可以停止检索。",
        )

    # 2) diminishing: enough rounds in, and the last STALL_WINDOW rounds added
    #    almost nothing relevant -> extra searching is not paying for itself
    if (
        snapshot.round_idx > MIN_ROUNDS_BEFORE_STALL
        and len(recent_gains) >= STALL_WINDOW
        and sum(recent_gains[-STALL_WINDOW:]) < STALL_GAIN
    ):
        if error_rounds_in_window >= STALL_WINDOW:
            attribution = (
                f"注意：最近 {STALL_WINDOW} 轮全部发生检索通道故障（网络/后端错误），"
                "零增益的原因是基础设施失效而非策略收益递减；停止本轮运行并如实报告，"
                "建议排查网络后重试。"
            )
        else:
            attribution = "继续同样策略收益接近零，建议停止并如实报告未达标部分。"
        return Assessment(
            score=score,
            verdict="diminishing",
            factors=factors,
            weakest=weakest,
            rationale=(
                f"边际收益递减：最近 {STALL_WINDOW} 轮仅新增 "
                f"{sum(recent_gains[-STALL_WINDOW:])} 条相关证据。{_detail()}。{attribution}"
            ),
        )

    # 3) otherwise keep going, pointing at the weakest link
    miss_txt = f"，其中 {('、'.join(missing))} 完全无相关证据" if missing else ""
    return Assessment(
        score=score,
        verdict="insufficient",
        factors=factors,
        weakest=weakest,
        rationale=f"证据不足：{_detail()}{miss_txt}。最薄弱子问题: {weakest}。",
    )
