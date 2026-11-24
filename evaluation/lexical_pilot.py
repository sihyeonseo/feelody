"""Does a lexical baseline retain emotionally suitable songs in the same E5 pool?"""
import argparse
import json
from collections import Counter
from math import log1p
from pathlib import Path
from zipfile import ZipFile

from pilot_audit import recover
from reference_benchmark import tokens


def benchmark(directory):
    with ZipFile(directory/"feelody_live_model_kit.zip") as z:
        catalog = json.loads(z.read("feelody-live/artifacts/b1_e5_v01/groups.json"))
    counts = {g["lyric_group_id"]:Counter(tokens(g["lyrics_text"])) for g in catalog}
    df = Counter()
    for freq in counts.values():
        df.update(freq.keys())
    n = len(counts)
    avg_len = sum(c.total() for c in counts.values())/n
    rows = []
    for row, labels, orders, _, _ in recover(directory):
        pool = row["pool"]
        words = set(tokens(row["diary"]))
        def bm25(g):
            c = counts[g]
            norm = 1.2*(0.25+0.75*c.total()/avg_len)
            return sum(log1p((n-df[t]+0.5)/(df[t]+0.5))*2.2*c[t]/(norm+c[t])
                       for t in sorted(words.intersection(c)))
        top = sorted(pool,key=lambda g:(-bm25(g),g))[:3]
        rows.append(dict(diary=row["id"],top=top,grades=[labels.get(g) for g in top]))
    return rows


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("directory",type=Path)
    p.add_argument("output",type=Path)
    a=p.parse_args()
    rows=benchmark(a.directory)
    a.output.write_text(json.dumps(rows,indent=2),encoding="utf-8")
    grades=[g for r in rows for g in r["grades"]]
    print("Judged positive / unjudged / total:",sum(g is not None and g>=2 for g in grades),grades.count(None),len(grades))
