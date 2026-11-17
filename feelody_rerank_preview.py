"""One-diary comparison using the existing Feelody Top-3 cache, read only."""
import argparse
from time import perf_counter
import feelody_top3 as f


def show(title, order, groups, positions):
    print("\n" + title)
    for i, (group, song) in enumerate(zip(order[:3], f.display(order, groups)), 1):
        print(f"{i}. {song['title']} — {song['artist']} (검색 {positions[group]}위)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", help="생략하면 일기를 한 줄로 입력합니다.")
    args = parser.parse_args()
    diary = (args.text if args.text is not None else input("일기> ")).strip()
    f.check(0 < len(diary) <= 4000, "일기는 1~4000자로 입력하세요.")
    prior_path = f.OUT / "ablation.json"
    pref, verdict = f.read(prior_path), f.read(f.OUT / "rerank.json")
    f.check(verdict["ablation_sha"] == f.digest(prior_path) and verdict["reranker"] == f.RR,
            "같은 실험의 ablation.json 및 rerank.json이 필요합니다.")
    f.check(pref["selected"] == "raw", "이 비교 도구는 원본 가사를 선택한 실험용입니다.")
    cfg, groups = f.material(None)
    print("저장된 원본 가사 벡터와 검색 모델을 읽습니다.", flush=True)
    enc = f.common(cfg)
    mat = f.matrix(groups, cfg, enc, "raw", pref["context"]["variant_key"])
    before = f.search(diary, enc, mat, groups)
    pos = {g: i for i,g in enumerate(before, 1)}
    show("검색만 적용", before, groups, pos)
    del enc, mat
    print(f"같은 후보 {len(before)}곡을 다시 채점합니다.", flush=True)
    rr = f.Reranker(verdict["revision"])
    t = perf_counter()
    after = rr.rank(diary, before, groups)
    f.check(len(before) == len(after) and set(before) == set(after), "후보 불일치")
    show("재순위화 적용", after, groups, pos)
    print(f"재순위화 계산: {perf_counter()-t:.1f}초 (모델 로딩 제외)")


if __name__ == "__main__":
    main()
