"""Verify public reference-rank aggregates without private data or a model."""
import json
from collections import Counter
from math import isclose
from pathlib import Path


def main():
    path = Path(__file__).resolve().parent / "reports" / "modern_dev.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    rows = report["rows"]
    dev = {r["diary_id"] for r in rows}
    reserved = set(report["reserved_ids"])
    if len(dev) != len(rows) or len(dev) != report["n_dev"] or dev & reserved:
        raise ValueError("Invalid split")
    print(f"dev={len(dev)}, reserved={len(reserved)}")
    for model in ("B1", "B3"):
        ranks = [r["models"][model]["reference_rank"] for r in rows]
        for k in (1, 5, 20, 50):
            hits = sum(rank <= k for rank in ranks)
            if not isclose(hits/len(rows), report["metrics"][model][f"reference_hit_at_{k}"]):
                raise ValueError(f"Metric mismatch: {model}@{k}")
            print(f"{model}@{k}: {hits}/{len(rows)}")
    paired = Counter(tuple(r["models"][m]["reference_rank"] <= 50 for m in ("B1","B3")) for r in rows)
    print("Both / B1 only / B3 only / neither:", *(paired[k] for k in ((True,True),(True,False),(False,True),(False,False))))


if __name__ == "__main__":
    main()
