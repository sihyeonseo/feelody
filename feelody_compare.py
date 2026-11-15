"""Feelody B1/B2 development comparison. Run locally; no verse retrieval yet."""
from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import platform
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from huggingface_hub import HfApi, hf_hub_download

try:
    import feelody_e5 as b1
except ModuleNotFoundError as exc:
    if exc.name != "feelody_e5":
        raise
    raise SystemExit("feelody_compare.py를 기존 feelody_e5.py와 같은 폴더에 넣으세요.") from exc

ROOT = Path(__file__).resolve().parent
B2_MODEL = "upskyy/bge-m3-korean"
B2_EXPERIMENT = "B2_korean_bge_chunk_weighted_mean_v01"
AGGREGATION = "content_token_weighted_mean_of_unit_chunk_vectors_then_l2"


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical_groups(groups):
    # Keep the original order and complete song mapping; token counts are model-specific.
    return [{k: g[k] for k in ("lyric_group_id", "lyrics_text", "songs")} for g in groups]


def catalog_fingerprint(groups):
    payload = json.dumps(canonical_groups(groups), ensure_ascii=False,
                         sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def check_files(index, manifest):
    for name, expected in manifest["files_sha256"].items():
        target = (index / name).resolve()
        if not target.is_relative_to(index.resolve()):
            raise ValueError("인덱스 안의 파일 경로가 잘못되었습니다.")
        if b1.sha256_file(target) != expected:
            raise ValueError(f"인덱스 파일이 변경되었습니다: {name}")


def read_b1(index):
    manifest = b1.read_json(index / "manifest.json")
    if (manifest["experiment"] != b1.EXPERIMENT
            or manifest["code_sha256"] != b1.sha256_file(b1.__file__)):
        raise ValueError("B1 코드/인덱스 버전이 다릅니다. 원본을 확인하고 오류를 공유하세요.")
    required = {"chunk_tokens": 384, "overlap_tokens": 0,
                "aggregation": AGGREGATION, "document_prefix": "passage: ",
                "query_prefix": "query: ", "tie_atol": 1e-8}
    if any(manifest.get(k) != v for k, v in required.items()):
        raise ValueError("합의한 B1 설정과 다른 인덱스입니다.")
    check_files(index, manifest)
    groups = b1.read_json(index / "groups.json")
    ids = [g["lyric_group_id"] for g in groups]
    if not groups or len(set(ids)) != len(ids):
        raise ValueError("B1 가사 그룹이 비었거나 중복되었습니다.")
    return manifest, groups


def model_settings(revision):
    settings = {}
    for name in ("modules.json", "1_Pooling/config.json", "sentence_bert_config.json"):
        path = hf_hub_download(B2_MODEL, name, revision=revision)
        settings[name] = b1.read_json(path)
    modules = settings["modules.json"]
    expected = [("", "sentence_transformers.models.Transformer"),
                ("1_Pooling", "sentence_transformers.models.Pooling")]
    if [(m["path"], m["type"]) for m in modules] != expected:
        raise ValueError("B2 모델 구조가 조사한 설정과 다릅니다. 검토 후 진행하세요.")
    pooling = settings["1_Pooling/config.json"]
    enabled = {k for k, v in pooling.items() if k.startswith("pooling_mode_") and v}
    if enabled != {"pooling_mode_mean_tokens"}:
        raise ValueError("B2가 단일 mean pooling 모델이 아닙니다.")
    if settings["sentence_bert_config.json"].get("do_lower_case", False):
        raise ValueError("B2의 소문자 변환 설정이 예상과 다릅니다.")
    return settings


def build_b2(args):
    if args.b2_index.exists():
        raise ValueError("B2 폴더가 이미 있습니다. 새 --b2-index를 지정하세요.")
    source_manifest, source_groups = read_b1(args.b1_index)
    groups = canonical_groups(source_groups)
    revision = HfApi().model_info(B2_MODEL, revision=args.revision).sha
    if not revision:
        raise ValueError("B2 커밋을 확인하지 못했습니다.")
    settings = model_settings(revision)
    print(f"B2: {B2_MODEL}\n커밋: {revision}\n기존 B1의 {len(groups)}개 가사 그룹 사용",
          flush=True)
    encoder = b1.Encoder(B2_MODEL, revision=revision, device=args.device)
    # The same masked mean implementation also matches this Korean derivative's config.
    # This is NOT the base BAAI/bge-m3 CLS pooling or its ColBERT token-vector head.
    max_seq = int(settings["sentence_bert_config.json"]["max_seq_length"])
    if b1.CHUNK_TOKENS + encoder.tokenizer.num_special_tokens_to_add(False) > max_seq:
        raise ValueError("384토큰 조각이 B2의 설정된 입력 길이를 넘습니다.")
    if encoder.model.config.hidden_size != settings["1_Pooling/config.json"]["word_embedding_dimension"]:
        raise ValueError("B2 모델과 pooling 설정의 차원이 다릅니다.")
    started = time.perf_counter()
    matrices = []
    for start in range(0, len(groups), 32):
        block = groups[start:start + 32]
        matrix, stats = encoder.encode([g["lyrics_text"] for g in block], "", args.b2_batch_size)
        matrices.append(matrix)
        for group, stat in zip(block, stats):
            group["token_stats"] = stat
        print(f"B2 가사 그룹 {min(start + 32, len(groups))}/{len(groups)}", flush=True)
    matrix = np.concatenate(matrices, axis=0)
    elapsed = time.perf_counter() - started
    args.b2_index.mkdir(parents=True, exist_ok=False)
    encoder.model.save_pretrained(args.b2_index / "model", safe_serialization=True)
    encoder.tokenizer.save_pretrained(args.b2_index / "model")
    np.save(args.b2_index / "embeddings.npy", matrix, allow_pickle=False)
    b1.write_json(args.b2_index / "groups.json", groups)
    b1.write_json(args.b2_index / "source_model_settings.json", settings)
    files = [p for p in args.b2_index.rglob("*") if p.is_file()]
    manifest = {
        "experiment": B2_EXPERIMENT, "model_id": B2_MODEL, "revision": revision,
        "created_at_utc": now(), "code_sha256": b1.sha256_file(__file__),
        "b1_code_sha256": b1.sha256_file(b1.__file__),
        "source_b1_manifest": source_manifest,
        "source_b1_manifest_sha256": b1.sha256_file(args.b1_index / "manifest.json"),
        "catalog_fingerprint": catalog_fingerprint(groups),
        "files_sha256": {p.relative_to(args.b2_index).as_posix(): b1.sha256_file(p) for p in files},
        "packages": b1.versions(), "python": platform.python_version(),
        "platform": platform.platform(), "device": args.device,
        "batch_size": args.b2_batch_size, "groups_per_block": 32,
        "chunk_tokens": b1.CHUNK_TOKENS, "overlap_tokens": 0,
        "aggregation": AGGREGATION, "pooling": "attention_masked_mean_including_special_tokens",
        "query_prefix": "", "document_prefix": "", "tie_atol": b1.TIE_ATOL,
        "embedding_dimension": matrix.shape[1], "lyric_groups": len(groups),
        "songs": sum(len(g["songs"]) for g in groups),
        "multi_chunk_groups": sum(g["token_stats"]["chunks"] > 1 for g in groups),
        "chunks_total": sum(g["token_stats"]["chunks"] for g in groups),
        "embedding_seconds": elapsed, "fine_tuned_in_this_experiment": False,
        "quality_evaluated": False,
    }
    b1.write_json(args.b2_index / "manifest.json", manifest)
    print(f"B2 저장 완료: {args.b2_index}")


def read_b2(index, b1_index, source_groups):
    manifest = b1.read_json(index / "manifest.json")
    if (manifest["experiment"] != B2_EXPERIMENT or manifest["model_id"] != B2_MODEL
            or manifest["code_sha256"] != b1.sha256_file(__file__)
            or manifest["b1_code_sha256"] != b1.sha256_file(b1.__file__)):
        raise ValueError("B2 코드/인덱스 버전이 다릅니다. 검사를 제거하지 말고 오류를 공유하세요.")
    if manifest["source_b1_manifest_sha256"] != b1.sha256_file(b1_index / "manifest.json"):
        raise ValueError("B2 생성 당시와 다른 B1 인덱스입니다.")
    check_files(index, manifest)
    groups = b1.read_json(index / "groups.json")
    if not (catalog_fingerprint(groups) == catalog_fingerprint(source_groups)
            == manifest["catalog_fingerprint"]):
        raise ValueError("두 모델의 가사/순서/곡 매핑이 일치하지 않습니다.")
    matrix = np.load(index / "embeddings.npy", allow_pickle=False)
    if matrix.shape != (len(groups), manifest["embedding_dimension"]) or not np.isfinite(matrix).all():
        raise ValueError("B2 임베딩 행렬이 유효하지 않습니다.")
    if not np.allclose(np.linalg.norm(matrix, axis=1), 1.0, rtol=0, atol=1e-6):
        raise ValueError("B2 벡터가 정규화되어 있지 않습니다.")
    if manifest["packages"] != b1.versions():
        print("주의: B2 생성 당시와 패키지 버전이 다릅니다.", file=sys.stderr)
    return manifest, groups, matrix


def score_diaries(encoder, matrix, groups, diaries, prefix, batch_size, experiment):
    scores_all, predictions = [], []
    for diary in diaries:
        started = time.perf_counter()
        query, stats = encoder.encode([diary["text"]], prefix, batch_size)
        scores = matrix @ query[0]
        if not np.isfinite(scores).all():
            raise ValueError("유효하지 않은 추천 점수입니다.")
        best = float(scores.max())
        winners = np.flatnonzero(np.isclose(scores, best, rtol=0, atol=b1.TIE_ATOL))
        songs = []
        for i in winners:
            for song in groups[i]["songs"]:
                songs.append({**song, "lyric_group_id": groups[i]["lyric_group_id"],
                              "cosine_similarity": float(scores[i]),
                              "similarity_score": float(scores[i] * 100)})
        songs.sort(key=lambda s: (s["title"], s["artist"], s["song_id"]))
        predictions.append({"diary": diary, "normalized_text": b1.normalize(diary["text"]),
                            "result": {"experiment": experiment, "max_similarity": best,
                                       "tie_count": len(songs), "winning_lyric_groups": len(winners),
                                       "recommendations": songs, "diary_token_stats": stats[0],
                                       "query_ms": (time.perf_counter() - started) * 1000,
                                       "score_note": "코사인 유사도 × 100; 적합 확률 아님"}})
        scores_all.append(scores)
        print(f"{experiment}: {diary['diary_id']} 처리 완료", flush=True)
    return np.stack(scores_all), predictions


def top_indices(scores, count):
    threshold = np.sort(scores)[-min(count, len(scores))]
    return np.flatnonzero((scores >= threshold) | np.isclose(scores, threshold, rtol=0, atol=b1.TIE_ATOL))


def csv_write(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def compare(args):
    if args.output.exists():
        raise ValueError("결과 폴더가 이미 있습니다. 새 --output을 지정하세요.")
    diary_input = b1.read_json(args.diaries)
    diaries = diary_input["diaries"]
    ids = [d["diary_id"] for d in diaries]
    if not diaries or any(not i.strip() for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("일기 ID가 비었거나 중복되었습니다.")
    if any(not b1.normalize(d["text"]) for d in diaries):
        raise ValueError("일기 본문이 비었습니다.")
    m1, source_groups = read_b1(args.b1_index)
    m2, groups2, matrix2 = read_b2(args.b2_index, args.b1_index, source_groups)
    # Load the two neural models sequentially to avoid holding both in memory.
    recommender = b1.Recommender(args.b1_index, args.device, args.b1_batch_size)
    s1, p1 = score_diaries(recommender.encoder, recommender.matrix, recommender.groups,
                          diaries, "query: ", args.b1_batch_size, b1.EXPERIMENT)
    del recommender
    gc.collect()
    if args.device == "cuda":
        torch.cuda.empty_cache()
    encoder2 = b1.Encoder(str(args.b2_index / "model"), local=True, device=args.device)
    s2, p2 = score_diaries(encoder2, matrix2, groups2, diaries, "", args.b2_batch_size, B2_EXPERIMENT)
    del encoder2
    gc.collect()
    rng = random.Random(args.seed)
    reviews, key, top1_rows, reproduction = [], [], [], []
    for d, diary in enumerate(diaries):
        pools = {"B1": set(top_indices(s1[d], args.top_k).tolist()),
                 "B2": set(top_indices(s2[d], args.top_k).tolist())}
        pool = sorted(pools["B1"] | pools["B2"])
        rng.shuffle(pool)
        for n, i in enumerate(pool, 1):
            group = source_groups[i]
            review_id = f"{diary['diary_id']}_R{n:03d}"
            reviews.append({"review_id": review_id, "diary_id": diary["diary_id"],
                            "diary_text": diary["text"],
                            "songs_json": json.dumps(group["songs"], ensure_ascii=False),
                            "lyrics_text": group["lyrics_text"],
                            "emotion_score": "", "context_score": "", "overall_score": "",
                            "uncertain": "", "notes": "", "rater_id": ""})
            for label, scores, group_list in (("B1", s1[d], source_groups), ("B2", s2[d], groups2)):
                row = {"review_id": review_id, "diary_id": diary["diary_id"], "model": label,
                       "lyric_group_id": group["lyric_group_id"],
                       "songs_json": json.dumps(group["songs"], ensure_ascii=False),
                       "cosine": float(scores[i]), "raw_rank": int(np.sum(scores > scores[i])) + 1,
                       "gap_to_best": float(scores.max() - scores[i]),
                       "is_top1": bool(np.isclose(scores[i], scores.max(), rtol=0, atol=b1.TIE_ATOL)),
                       "in_model_top_k_pool": i in pools[label],
                       "lyric_tokens": group_list[i]["token_stats"]["content_tokens"],
                       "lyric_chunks": group_list[i]["token_stats"]["chunks"]}
                key.append(row)
                if row["is_top1"]:
                    top1_rows.append(row)
        previous = diary.get("previous_b1_observation")
        if previous:
            result = p1[d]["result"]
            observed_ids = sorted(str(s["song_id"]) for s in result["recommendations"])
            expected_ids = sorted(str(i) for i in previous["song_ids"])
            reproduction.append({"diary_id": diary["diary_id"], "previous_song_ids": expected_ids,
                                 "current_song_ids": observed_ids, "same_top1_song_set": observed_ids == expected_ids,
                                 "previous_reported_cosine": previous["cosine"],
                                 "current_max_cosine": result["max_similarity"],
                                 "delta_from_reported": result["max_similarity"] - previous["cosine"],
                                 "note": "사용자 보고값과 비교; 품질 정답/비트 단위 재현 검사가 아님"})
    args.output.mkdir(parents=True, exist_ok=False)
    private = args.output / "private"
    private.mkdir()
    csv_write(args.output / "review_blind.csv", reviews)
    csv_write(private / "candidate_comparison.csv", key)
    csv_write(private / "top1_comparison.csv", top1_rows)
    b1.write_json(private / "predictions.json", {"B1": p1, "B2": p2})
    b1.write_json(private / "b1_reproduction.json", reproduction)
    np.savez_compressed(private / "all_scores.npz", B1=s1, B2=s2)
    b1.write_json(private / "score_axes.json", {"rows_diary_ids": ids,
                  "columns_lyric_group_ids": [g["lyric_group_id"] for g in source_groups]})
    (args.output / "START_HERE.txt").write_text(
        "먼저 review_blind.csv에서 일기와 가사 전체를 읽고 0~3점으로 평가하세요.\n"
        "모델명/점수/순위를 숨겼지만, 과거 추천을 본 경우 완전한 눈가림은 아닙니다.\n"
        "private 폴더는 평가 후 열어 보세요. 추천 결과와 모델별 후보 정보가 있습니다.\n"
        "점수: 0=불일치, 1=약한 연결, 2=대체로 적합, 3=명확히 적합.\n"
        "emotion/context/overall을 각각 평가하고, 불확실하면 점수를 비워 uncertain=1과 이유를 적으세요.\n"
        "가사 의미를 평가하며 음원/장르/제목만으로 곡의 정서를 단정하지 마세요.\n"
        "전체 추천 적합성은 감정/맥락 점수의 자동 평균이 아닙니다.\n"
        "최고점과 공동 최고점 전체가 최종 추천입니다. 상위 후보는 비교 평가용입니다.\n"
        "이 6건은 이미 살펴본 개발 사례이므로 최종 성능을 일반화할 수 없습니다.\n",
        encoding="utf-8")
    b1.write_json(args.output / "manifest.json", {
        "created_at_utc": now(), "B1_index_manifest": m1, "B2_index_manifest": m2,
        "code_sha256": b1.sha256_file(__file__), "b1_code_sha256": b1.sha256_file(b1.__file__),
        "diaries_sha256": b1.sha256_file(args.diaries), "diary_input": diary_input,
        "catalog_fingerprint": catalog_fingerprint(source_groups), "packages": b1.versions(),
        "python": platform.python_version(), "platform": platform.platform(), "device": args.device,
        "b1_batch_size": args.b1_batch_size, "b2_batch_size": args.b2_batch_size,
        "top_k_groups_per_model": args.top_k, "include_cutoff_ties": True,
        "tie_atol": b1.TIE_ATOL, "shuffle_seed": args.seed, "review_rows": len(reviews),
        "quality_evaluated": False,
        "limitations": ["development_only", "model_tokenizer_and_input_format_change_together",
                        "cross_model_cosine_not_comparable_as_quality", "prior_exposure_limits_blinding",
                        "timings_include_warmup_not_benchmarks"]})
    if any(not row["same_top1_song_set"] for row in reproduction):
        print("주의: 이전 B1 보고와 다른 1위가 있습니다. private/b1_reproduction.json을 확인하세요.")
    print(f"저장 완료: {args.output}\n먼저 review_blind.csv를 평가하세요. 모델 결과는 private 폴더에 있습니다.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("build-b2", "compare"):
        p = sub.add_parser(command)
        p.add_argument("--b1-index", type=Path, default=ROOT / "artifacts" / "b1_e5_v01")
        p.add_argument("--b2-index", type=Path, default=ROOT / "artifacts" / "b2_korean_bge_v01")
        p.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
        p.add_argument("--b2-batch-size", type=int, default=2)
        if command == "build-b2":
            p.add_argument("--revision", default="main", help="재현 시 저장된 B2 커밋 지정")
        else:
            p.add_argument("--b1-batch-size", type=int, default=8)
            p.add_argument("--diaries", type=Path, default=ROOT / "comparison_diaries.json")
            p.add_argument("--output", type=Path, default=ROOT / "results" / "b1_b2_compare_001")
            p.add_argument("--top-k", type=int, default=10)
            p.add_argument("--seed", type=int, default=20261024)
    args = parser.parse_args()
    if args.b2_batch_size < 1 or getattr(args, "b1_batch_size", 1) < 1 or getattr(args, "top_k", 1) < 1:
        parser.error("배치 크기와 top-k는 1 이상이어야 합니다.")
    if args.device == "cuda" and not torch.cuda.is_available():
        parser.error("CUDA를 사용할 수 없습니다. CPU로 실행하세요.")
    torch.manual_seed(0)
    if args.command == "build-b2":
        build_b2(args)
    else:
        compare(args)


if __name__ == "__main__":
    main()
