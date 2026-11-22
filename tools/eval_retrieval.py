"""Compare single-wording and multi-wording search on evals/retrieval.yaml (no model involved).

    python tools/eval_retrieval.py          # recall@6 and MRR@10 for both modes, and the misses
"""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import search  # noqa: E402


def rank_of(hits, expect):
    for i, h in enumerate(hits, 1):
        if h["doc_id"] in expect:
            return i
    return None


def main() -> None:
    items = yaml.safe_load((ROOT / "evals" / "retrieval.yaml").read_text())
    stats = {"single": [], "multi": []}
    for it in items:
        e = set(it["expect_any"])
        r1 = rank_of(search.search(it["query"], 10, None, None, None, False), e)
        r2 = rank_of(search.search(it["query"], 10, None, None, None, False, it.get("also")), e)
        stats["single"].append(r1); stats["multi"].append(r2)
        flag = "" if (r1 and r1 <= 6) == (r2 and r2 <= 6) else "  <- changed"
        print(f"{it['id']:4} single {str(r1):>4}  multi {str(r2):>4}  {it['query'][:62]}{flag}")
    n = len(items)
    for mode, ranks in stats.items():
        rec = sum(1 for r in ranks if r and r <= 6) / n
        mrr = sum(1 / r for r in ranks if r) / n
        print(f"{mode:6} recall@6 {rec:.0%} | MRR@10 {mrr:.3f} | not in top 10: {[items[i]['id'] for i, r in enumerate(ranks) if not r]}")


if __name__ == "__main__":
    main()
