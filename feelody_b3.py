"""Feelody B3 v0.1: fixed emotion prototypes, full-catalogue comparison with B1."""
import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import feelody_e5 as b1

ROOT = Path(__file__).resolve().parent
# Exploratory, hand-written axes. They are neither learned classes nor probabilities.
ANCHORS = {
    "평온·만족": "마음이 편안하고 지금 가진 것으로 충분하여 만족스럽다.",
    "감사·온기": "받은 마음이 고맙고 소중하게 느껴져 가슴이 따뜻하다.",
    "기쁨·감격": "한껏 기쁘고 감격스러워 가슴이 벅차오른다.",
    "설렘·기대": "앞으로의 일이 기대되어 마음이 설레고 들뜬다.",
    "자부심": "해낸 일이 자랑스럽고 스스로가 대견하다.",
    "애틋함·그리움": "곁에 없는 존재가 보고 싶고 그리워 마음이 애틋하다.",
    "슬픔·상실": "소중한 것을 잃어 마음이 무너지고 깊은 슬픔에 잠긴다.",
    "외로움·공허": "혼자 남은 것처럼 쓸쓸하고 마음이 텅 빈 듯하다.",
    "후회·자책": "지나간 선택을 후회하고 스스로를 탓한다.",
    "분노": "잘못된 일을 받아들일 수 없어 화가 나고 분하다.",
    "결의": "어려움에도 흔들리지 않고 끝까지 해내겠다는 마음이 단단하다.",
    "불안·두려움": "무슨 일이 생길지 몰라 불안하고 겁이 난다.",
    "안도": "줄곧 걱정하던 일이 풀려 긴장이 가시고 마음이 놓인다.",
    "무력감·체념": "애써도 달라질 것이 없다고 느껴 기운이 빠지고 체념하게 된다.",
}
# For reporting only; these IDs and ratings are never passed to either scoring method.
DEV_LABELS = {
    "MA_007": {"30566061": 1, "1500206": 1, "3800393": 0, "502946": 0, "46163": 3},
    "NJ_002": {"1533404": 2, "516204": 0},
    "NJ_005": {"32361098": 2, "2951700": 0},
}


def profiles(vectors, anchors):
    similarities = vectors @ anchors.T
    centered = similarities - similarities.mean(axis=1, keepdims=True)
    norms = np.linalg.norm(centered, axis=1, keepdims=True)
    if not np.isfinite(norms).all() or np.any(norms < 1e-12):
        raise ValueError("감정 축 사이에 유효한 차이가 없어 순위를 계산할 수 없습니다.")
    return centered / norms


def winners(rec, scores):
    best = scores.max()
    indices = np.flatnonzero(best - scores <= b1.TIE_ATOL)
    return [{**song, "group": rec.groups[i]["lyric_group_id"], "cosine": float(scores[i])}
            for i in indices for song in rec.groups[i]["songs"]]


def run(args):
    rec = b1.Recommender(args.index, device=args.device)
    encode = lambda texts, prefix: rec.encoder.encode(texts, prefix, rec.batch_size)[0]
    # Same input role for diary and lyrics in B3: each is a passage scored by fixed queries.
    anchors = encode(list(ANCHORS.values()), "query: ")
    song_profiles = profiles(rec.matrix, anchors)
    id_to_row = {str(song["song_id"]): i for i, group in enumerate(rec.groups) for song in group["songs"]}
    results = []
    for did, diary in {"custom": args.diary}.items():
        if not diary.strip():
            raise ValueError("일기 본문이 비어 있습니다.")
        b1_scores = rec.matrix @ encode([diary], "query: ")[0]
        diary_profile = profiles(encode([diary], "passage: "), anchors)[0]
        b3_scores = song_profiles @ diary_profile
        outputs = {key: winners(rec, s) for key, s in (("B1", b1_scores), ("B3", b3_scores))}
        print("\n" + did)
        for key, songs in outputs.items():
            print(key + ": " + " / ".join(f"{s['title']} — {s['artist']} [{s['song_id']}]" for s in songs))
        rated = []
        for sid, rating in DEV_LABELS.get(did, {}).items():
            i = id_to_row[sid]
            ranks = [int(np.count_nonzero(s > s[i] + b1.TIE_ATOL)) + 1 for s in (b1_scores, b3_scores)]
            rated.append(dict(song_id=sid, emotion_score=rating, B1_group_rank=ranks[0], B3_group_rank=ranks[1]))
        results.append(dict(diary_id=did, diary=diary, winners=outputs, known_cases=rated,
                            diary_relative_profile=dict(zip(ANCHORS, diary_profile.tolist()))))
    report = dict(method="B3_v0.1_centered_emotion_profile_cosine", anchors=ANCHORS, device=args.device,
                  tie_atol=b1.TIE_ATOL, source_sha256=b1.sha256_file(__file__), packages=b1.versions(),
                  index_manifest=rec.manifest, results=results)
    out = ROOT / ("b3_results_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".json")
    with out.open("x", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, allow_nan=False)
    print("\n결과 파일:", out)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--index", type=Path, default=ROOT / "artifacts" / "b1_e5_v01")
    p.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    p.add_argument("--diary", required=True, help="비교할 일기 한 편")
    run(p.parse_args())
