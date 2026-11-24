"""Reference song retrieval on the existing 114 development diaries only."""
import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from zipfile import ZipFile

import numpy as np


def tokens(text):
    # Within-word bigrams reduce sensitivity to Korean particles and inflections.
    for word in re.findall(r"[가-힣a-z0-9]+", text.lower()):
        if len(word) == 1:
            yield word
        else:
            yield from (word[i:i+2] for i in range(len(word)-1))


def compare(archive, diaries):
    report = json.loads((Path(__file__).resolve().parents[1]/"reports/modern_dev.json").read_text())
    if hashlib.sha256(diaries.read_bytes()).hexdigest() != report["source_sha256"]:
        raise ValueError("Use the original 142-row diary CSV")
    with ZipFile(archive) as z:
        raw = z.read("feelody-live/artifacts/b1_e5_v01/groups.json")
    if hashlib.sha256(raw).hexdigest() != report["index_manifest"]["files_sha256"]["groups.json"]:
        raise ValueError("Unexpected catalogue version")
    groups = json.loads(raw)
    index = defaultdict(list)
    lengths = []
    song_rows = {}
    for i,g in enumerate(groups):
        counts = Counter(tokens(g["lyrics_text"]))
        lengths.append(sum(counts.values()))
        for term, count in counts.items():
            index[term].append((i,count))
        song_rows.update({str(s["song_id"]):i for s in g["songs"]})
    n = len(groups)
    norm = 1.2 * (0.25 + 0.75 * np.array(lengths)/np.mean(lengths))
    with diaries.open(encoding="utf-8-sig") as f:
        texts = {r["diary_id"]:r for r in csv.DictReader(f)}
    rows = []
    for row in report["rows"]:
        did = row["diary_id"]
        assert did not in report["reserved_ids"] and texts[did]["target_song_id"] == row["reference_id"]
        scores = np.zeros(n)
        for term in sorted(set(tokens(texts[did]["text"]))):
            postings = index.get(term, [])
            idf = math.log1p((n-len(postings)+0.5)/(len(postings)+0.5))
            for i,tf in postings:
                scores[i] += idf*tf*2.2/(tf+norm[i])
        target = song_rows[row["reference_id"]]
        # Match the published optimistic tie convention. Report tie counts separately.
        rank = 1 + int(np.count_nonzero(scores > scores[target]+1e-8))
        rows.append(dict(diary_id=did, BM25=rank, ties=int(sum(abs(scores-scores[target])<=1e-8)),
                         **{m:v["reference_rank"] for m,v in row["models"].items()}))
    cuts = (3,10,30,50,100)
    return dict(n_dev=len(rows), catalog=n, reference_hits={
        m:{k:sum(row[m]<=k for row in rows) for k in cuts} for m in ("BM25","B1","B3")},
        random_expected_rate={k:k/n for k in cuts}, rows=rows)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for arg in ("archive","diaries","output"):
        p.add_argument(arg, type=Path)
    a = p.parse_args()
    report = compare(a.archive, a.diaries)
    a.output.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(report["reference_hits"])
