"""P1-a minimal experiment: where does the lexical evaluator misjudge, and can
an off-the-shelf semantic module fix those specific misses?

Design (per 2026-10-24 review):
- hand-verified case set (cases.json): each document labeled with the
  sub-question(s) it genuinely answers (gold);
- arm 1 (production lexical): relevance() + EvidenceStore accept rule
  (absolute threshold + relative margin) -> per-(doc, subq) verdicts vs gold;
- arm 2 (semantic baseline): all-MiniLM-L6-v2 cosine similarity between the
  sub-question text and the document; reported as per-pair similarities and a
  threshold-free separation score (min positive vs max negative), plus
  exploratory fixed thresholds.

Caveat kept explicit: embedding similarity is a *relevance* proxy. It does
not by itself prove evidence sufficiency (see docs/P1_BRIEF.md).

Usage:
    python experiments/p1a/run_experiment.py            # writes results.json + report.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from meta_reseek.evidence import EvidenceStore, relevance  # noqa: E402
from meta_reseek.task import TaskSpec  # noqa: E402

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
HERE = Path(__file__).parent
EXPLORATORY_THRESHOLDS = [0.40, 0.50, 0.60]


# --------------------------------------------------------------------------
def lexical_verdicts(task: TaskSpec, cases: list[dict]) -> dict[str, dict[str, dict]]:
    """Production accept rule per (case, subq): {subq: {score, accepted}}."""
    out = {}
    for case in cases:
        text = f"{case['title']}\n{case['snippet']}"
        scores = {
            sq.id: relevance(text, sq.terms, task.common_terms)
            for sq in task.sub_questions
        }
        best = max(scores.values(), default=0.0)
        out[case["id"]] = {
            sid: {
                "score": round(s, 3),
                "accepted": s >= EvidenceStore.MIN_RELEVANCE
                and s >= EvidenceStore.RELATIVE_MARGIN * best,
            }
            for sid, s in scores.items()
        }
    return out


def semantic_scores(task: TaskSpec, cases: list[dict]) -> tuple[dict[str, dict[str, float]], str]:
    """Cosine similarity (sub-question text vs document). Returns matrix + model id."""
    import os

    os.environ.setdefault("HF_ENDPOINT", "https://huggingface.co")
    import torch
    from transformers import AutoModel, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModel.from_pretrained(MODEL_ID)
    model.eval()

    texts = [sq.text for sq in task.sub_questions] + [
        f"{c['title']}. {c['snippet']}" for c in cases
    ]
    enc = tok(texts, padding=True, truncation=True, max_length=256, return_tensors="pt")
    with torch.no_grad():
        hidden = model(**enc).last_hidden_state
    mask = enc["attention_mask"].unsqueeze(-1).to(hidden.dtype)
    emb = (hidden * mask).sum(1) / mask.sum(1)
    emb = torch.nn.functional.normalize(emb, dim=1)
    n_subq = len(task.sub_questions)
    subq_emb, doc_emb = emb[:n_subq], emb[n_subq:]
    sims = (doc_emb @ subq_emb.T).tolist()

    matrix = {
        case["id"]: {
            sq.id: round(float(sims[i][j]), 4)
            for j, sq in enumerate(task.sub_questions)
        }
        for i, case in enumerate(cases)
    }
    return matrix, MODEL_ID


# --------------------------------------------------------------------------
def evaluate(cases, task, lex, sem):
    subq_ids = [sq.id for sq in task.sub_questions]
    pairs = []  # one row per (case, subq)
    confusion = {"TP": 0, "FP": 0, "FN": 0, "TN": 0}
    lex_errors = []
    for case in cases:
        cid = case["id"]
        for sid in subq_ids:
            gold_pos = sid in case["gold"]
            accepted = lex[cid][sid]["accepted"]
            outcome = ("TP" if gold_pos else "FP") if accepted else ("FN" if gold_pos else "TN")
            confusion[outcome] += 1
            if outcome in {"FP", "FN"}:
                lex_errors.append(
                    {
                        "case": cid,
                        "intent": case["intent"],
                        "subq": sid,
                        "error": outcome,
                        "lexical_score": lex[cid][sid]["score"],
                        "semantic_sim": sem[cid][sid],
                        "title": case["title"],
                    }
                )
            pairs.append(
                {
                    "case": cid,
                    "intent": case["intent"],
                    "subq": sid,
                    "gold": gold_pos,
                    "lexical_score": lex[cid][sid]["score"],
                    "lexical_accepted": accepted,
                    "semantic_sim": sem[cid][sid],
                }
            )

    positives = [p["semantic_sim"] for p in pairs if p["gold"]]
    negatives = [p["semantic_sim"] for p in pairs if not p["gold"]]
    separation = round(min(positives) - max(negatives), 4) if positives and negatives else None
    thresholds = {
        str(t): {
            "TP": sum(p["gold"] and p["semantic_sim"] >= t for p in pairs),
            "FP": sum((not p["gold"]) and p["semantic_sim"] >= t for p in pairs),
            "FN": sum(p["gold"] and p["semantic_sim"] < t for p in pairs),
            "TN": sum((not p["gold"]) and p["semantic_sim"] < t for p in pairs),
        }
        for t in EXPLORATORY_THRESHOLDS
    }
    # does the semantic arm specifically rescue the lexical errors?
    rescue = [
        {**e, "semantic_verdict_at_0.5": "positive" if e["semantic_sim"] >= 0.5 else "negative"}
        for e in lex_errors
    ]
    return pairs, confusion, separation, thresholds, lex_errors, rescue


def main() -> int:
    spec = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    task = TaskSpec.from_yaml(REPO / spec["task"])
    cases = spec["cases"]

    lex = lexical_verdicts(task, cases)
    sem, model_id = semantic_scores(task, cases)
    pairs, confusion, separation, thresholds, lex_errors, rescue = evaluate(
        cases, task, lex, sem
    )

    results = {
        "experiment": "p1a-lexical-failure-modes",
        "date": "2026-10-24",
        "task": spec["task"],
        "n_cases": len(cases),
        "n_pairs": len(pairs),
        "lexical_confusion": confusion,
        "lexical_errors": lex_errors,
        "semantic_model": model_id,
        "semantic_separation": separation,
        "semantic_separation_detail": {
            "min_positive_sim": min(p["semantic_sim"] for p in pairs if p["gold"]),
            "max_negative_sim": max(p["semantic_sim"] for p in pairs if not p["gold"]),
        },
        "semantic_exploratory_thresholds": thresholds,
        "semantic_rescue_of_lexical_errors": rescue,
        "pairs": pairs,
    }
    (HERE / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    lines = [
        "# P1-a 最小实验报告：词法评价器失误模式与语义模块检验",
        "",
        f"- 案例集：{len(cases)} 篇文档 × {len(task.sub_questions)} 子问题 = {len(pairs)} 对（gold 人工标注）",
        f"- 词法臂（现行生产逻辑）混淆矩阵：{confusion}",
        f"- 语义臂：{model_id}，余弦相似度",
        f"- 分离度（min 正对相似度 − max 负对相似度）：{separation}",
        "  - 正对最小 {min_positive_sim} / 负对最大 {max_negative_sim}".format(**results["semantic_separation_detail"]),
        f"- 探索性固定阈值结果：{thresholds}",
        "",
        "## 词法失误明细（gold vs 词法判定）",
        "",
    ]
    for e in lex_errors:
        lines.append(
            f"- [{e['error']}] {e['case']}（{e['intent']}）→ 子问题 {e['subq']}："
            f"词法分 {e['lexical_score']}，语义相似度 {e['semantic_sim']}"
        )
    lines += [
        "",
        "## 语义臂对上述失误的判定（阈值 0.5，探索性）",
        "",
    ]
    for r in rescue:
        want = "positive" if r["error"] == "FN" else "negative"
        got = r["semantic_verdict_at_0.5"]
        lines.append(
            f"- {r['case']}（{r['error']}，期望语义判 {want}）→ 实际 {got} "
            f"{'✅ 修正' if got == want else '❌ 未修正'}"
        )
    lines += [
        "",
        "## 口径与限定（按评审意见）",
        "",
        "- 嵌入相似度是**相关性**代理，不能直接证明证据充分性；本实验只检验“具体缺口识别”层面的失误修正，不比较 score 数值本身。",
        "- 案例集极小（12 篇），且由构建者标注 gold；结论仅用于定位失误模式与决定 P1-a 方向，不作为性能结论。",
        "- 固定阈值为探索性；分离度是免阈值指标。",
    ]
    (HERE / "report.md").write_text("\n".join(lines), encoding="utf-8")

    print("confusion:", confusion, "| separation:", separation)
    print("lexical errors:", len(lex_errors))
    for e in lex_errors:
        print(f"  [{e['error']}] {e['case']} -> {e['subq']} lex={e['lexical_score']} sem={e['semantic_sim']}")
    print("written:", HERE / "results.json", "and", HERE / "report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
