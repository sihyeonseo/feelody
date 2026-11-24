"""Reconcile archived blind ratings and compare systems on identical diaries."""
import argparse
import csv
import json
import math
import random
from collections import Counter
from pathlib import Path
from statistics import mean, median
from zipfile import ZipFile


def load(directory, name):
    return json.loads((directory / name).read_text(encoding="utf-8-sig"))


def metrics(top, labels, pool):
    grades = [labels[g] for g in top]
    if len(top) != 3 or len(set(top)) != 3 or not set(top) <= set(pool):
        raise ValueError("Expected three distinct groups from the frozen pool")
    hits = [i for i, grade in enumerate(grades, 1) if grade >= 2]
    def dcg(values):
        return sum((2**v - 1) / math.log2(i + 2) for i, v in enumerate(values))
    ideal = sorted((labels[g] for g in pool if g in labels), reverse=True)[:3]
    return dict(precision=len(hits)/3, hit=int(bool(hits)), mrr=1/hits[0] if hits else 0,
                pooled_ndcg=dcg(grades)/dcg(ideal) if dcg(ideal) else None)


def recover(directory):
    with ZipFile(directory / "feelody_paired10_gpu.zip") as archive:
        frozen = json.loads(archive.read("pools.json"))
    host = load(directory, "feelody_cpu30_host_results.json")
    original = load(directory, "feelody_10diaries_ratings.json")
    bge = load(directory, "feelody_bge10_results.json")
    more = load(directory, "feelody_bge10_ratings.json")
    diagnostic = load(directory, "feelody_paired10_scored.json")["diagnostic"]
    extra = load(directory, "feelody_039_ratings.json")
    if (host["metadata"]["rating_tag"], bge["rating_tag"], diagnostic["tag"]) != (
            original["tag"], more["tag"], extra["tag"]):
        raise ValueError("Blind review file mismatch")
    hosts = {r["diary_id"]: r for r in host["rows"]}
    for row in frozen["rows"]:
        did = row["id"]
        h = hosts[did]
        pool = row["pool"]
        if pool != h["top30"] or len(set(pool)) != 30:
            raise ValueError("Frozen pool changed")
        labels = {}
        def add(g, grade):
            if type(grade) is not int or grade not in range(4) or labels.setdefault(g, grade) != grade:
                raise ValueError("Invalid or conflicting label")
        for system, group_ids in h["orders"].items():
            for gid, token in zip(group_ids, host["blind_assignments"][did][system], strict=True):
                add(gid, original["scores"][token])
        for token, (diary, gid) in bge["new_review_key"].items():
            if diary == did:
                add(gid, more["ratings"][token])
        if did == diagnostic["id"]:
            for token, gid in diagnostic["unjudged_key"].items():
                add(gid, extra["ratings"][token])
        orders = dict(E5=h["orders"]["retrieval"], KURE=h["orders"]["nano30"], BGE=bge["rows"][did]["bge"])
        yield row, labels, orders, h["timing"], frozen["lyrics"]


def audit(directory, output):
    output.mkdir(parents=True, exist_ok=True)
    per_diary, timings, pending, qrels = [], [], [], []
    for row, labels, orders, timing, lyrics in recover(directory):
        pool = row["pool"]
        did = row["id"]
        known = [labels[g] for g in pool if g in labels]
        scores = {name: metrics(order, labels, pool) for name, order in orders.items()}
        if scores["KURE"]["hit"]:
            status = "top3_hit"
        elif any(x >= 2 for x in known):
            status = "rerank_miss"
        elif len(known) == len(pool):
            status = "empty_candidate_pool"
        else:
            status = "unresolved"
        per_diary.append(dict(diary=did, judged=len(known), positives=sum(x >= 2 for x in known),
                              status=status, scores=scores))
        timings.append(timing)
        for gid in pool:
            if gid in labels:
                qrels.append((did, gid, labels[gid]))
            else:
                pending.append((did, gid, row["diary"], lyrics[gid]["text"]))
    # Random order within each diary; the ambiguous failure is the first review block.
    random.Random(73).shuffle(pending)
    pending.sort(key=lambda r: (r[0] != "AIREF_045", r[0]))
    for name, header, rows in [
        ("qrels.csv", ["diary_id","lyric_group_id","grade"], qrels),
        ("blind.csv", ["diary_id","lyric_group_id","diary","lyrics","grade"], [(*r,"") for r in pending])]:
        with (output/name).open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)
    summary = dict(per_diary=per_diary, failure_counts=Counter(r["status"] for r in per_diary),
                   macro={}, timing_median_s={k:median(t[k] for t in timings) for k in timings[0]},
                   rerank_share=sum(t["rerank_s"] for t in timings)/sum(t["total_s"] for t in timings))
    for system in per_diary[0]["scores"]:
        summary["macro"][system] = {}
        for key in per_diary[0]["scores"][system]:
            values = [r["scores"][system][key] for r in per_diary]
            defined = [v for v in values if v is not None]
            summary["macro"][system][key] = mean(defined) if defined else None
            summary["macro"][system][key+"_n"] = len(defined)
    (output/"pilot_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(summary["failure_counts"], summary["macro"], summary["rerank_share"], len(pending))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("archives", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    audit(args.archives, args.output)
