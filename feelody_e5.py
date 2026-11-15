"""Feelody B1: frozen E5 retrieval. Execution and evaluation are left to the user."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from huggingface_hub import HfApi
from transformers import AutoModel, AutoTokenizer

ROOT = Path(__file__).resolve().parent
MODEL_ID = "intfloat/multilingual-e5-small"
EXPERIMENT = "B1_e5_chunk_weighted_mean_v01"
CHUNK_TOKENS = 384
TIE_ATOL = 1e-8  # Raw cosine tolerance; never compare rounded display scores.


def normalize(text):
    return re.sub(r"\s+", " ", text).strip()


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def versions():
    names = ["torch", "transformers", "numpy", "huggingface-hub", "tokenizers", "safetensors"]
    return {name: importlib.metadata.version(name) for name in names}


def read_catalog(path):
    """Keep track identities but encode each whitespace-normalized lyric only once."""
    groups, seen = {}, set()
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"song_id", "title", "artist", "lyrics_text"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"카탈로그 필수 열: {sorted(required)}")
        for line, row in enumerate(reader, 2):
            if any(not (row.get(k) or "").strip() for k in required):
                raise ValueError(f"카탈로그 {line}행: 필수 값이 비어 있습니다.")
            song_id = row["song_id"].strip()
            if song_id in seen:
                raise ValueError(f"중복 song_id: {song_id}; 정제된 카탈로그를 사용하세요.")
            seen.add(song_id)
            text = normalize(row["lyrics_text"])
            if text not in groups:
                groups[text] = {
                    "lyric_group_id": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "lyrics_text": text,
                    "songs": [],
                }
            groups[text]["songs"].append({"song_id": song_id, "title": row["title"], "artist": row["artist"]})
    if not groups:
        raise ValueError("카탈로그가 비어 있습니다.")
    return list(groups.values())


class Encoder:
    def __init__(self, source, revision=None, local=False, device="cpu"):
        options = {"local_files_only": local, "trust_remote_code": False}
        if revision:
            options["revision"] = revision
        self.tokenizer = AutoTokenizer.from_pretrained(source, use_fast=True, **options)
        self.model = AutoModel.from_pretrained(source, use_safetensors=True, **options)
        self.device = torch.device(device)
        self.model.to(self.device).eval()
        self.limit = min(int(self.model.config.max_position_embeddings), 512)

    def encode(self, texts, prefix, batch_size=8, progress=False):
        # Split token IDs directly: no decoding/re-tokenizing, overlap, or silent truncation.
        prefix_ids = self.tokenizer.encode(prefix, add_special_tokens=False)
        if CHUNK_TOKENS + len(prefix_ids) + self.tokenizer.num_special_tokens_to_add(False) > self.limit:
            raise ValueError("조각 크기가 모델 입력 한도를 넘습니다.")
        features, owners, weights, stats = [], [], [], []
        for owner, text in enumerate(texts):
            token_ids = self.tokenizer.encode(normalize(text), add_special_tokens=False,
                                              truncation=False, verbose=False)
            if not token_ids:
                raise ValueError("토큰으로 변환할 내용이 없습니다.")
            count = 0
            for start in range(0, len(token_ids), CHUNK_TOKENS):
                chunk = token_ids[start:start + CHUNK_TOKENS]
                feature = self.tokenizer.prepare_for_model(
                    prefix_ids + chunk, add_special_tokens=True, truncation=False,
                    return_attention_mask=True, return_token_type_ids=False,
                )
                if len(feature["input_ids"]) > self.limit:
                    raise ValueError("입력 한도 초과: 자동 절단하지 않고 중단합니다.")
                features.append(feature)
                owners.append(owner)
                weights.append(len(chunk))
                count += 1
            stats.append({"content_tokens": len(token_ids), "chunks": count})
        totals = np.zeros((len(texts), self.model.config.hidden_size), dtype=np.float64)
        total_weights = np.zeros(len(texts), dtype=np.float64)
        with torch.inference_mode():
            for start in range(0, len(features), batch_size):
                end = min(start + batch_size, len(features))
                batch = self.tokenizer.pad(features[start:end], padding=True, return_tensors="pt")
                batch = {key: value.to(self.device) for key, value in batch.items()}
                hidden = self.model(**batch).last_hidden_state
                mask = batch["attention_mask"].unsqueeze(-1).to(hidden.dtype)
                # Masked mean pooling follows the E5 model card. Padding must not contribute.
                pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1)
                vectors = F.normalize(pooled, p=2, dim=1).cpu().numpy().astype(np.float64)
                for offset, vector in enumerate(vectors):
                    i = start + offset
                    totals[owners[i]] += weights[i] * vector
                    total_weights[owners[i]] += weights[i]
                if progress:
                    print(f"임베딩 조각 {end}/{len(features)}", file=sys.stderr, flush=True)
        totals /= total_weights[:, None]
        norms = np.linalg.norm(totals, axis=1, keepdims=True)
        if not np.isfinite(totals).all() or np.any(norms <= 0):
            raise ValueError("유효하지 않은 임베딩이 생성되었습니다.")
        return totals / norms, stats


def build(args):
    if args.index.exists():
        raise ValueError("인덱스 폴더가 이미 있습니다. --index로 새 폴더를 지정하세요.")
    groups = read_catalog(args.catalog)
    # Resolve the branch once; all downloaded model/tokenizer files use the same commit.
    revision = HfApi().model_info(MODEL_ID, revision=args.revision).sha
    if not revision:
        raise ValueError("모델 커밋을 확인하지 못했습니다.")
    print(f"모델: {MODEL_ID}\n커밋: {revision}", file=sys.stderr)
    encoder = Encoder(MODEL_ID, revision=revision, device=args.device)
    started = time.perf_counter()
    matrix, stats = encoder.encode([g["lyrics_text"] for g in groups], "passage: ",
                                   args.batch_size, progress=True)
    elapsed = time.perf_counter() - started
    for group, stat in zip(groups, stats):
        group["token_stats"] = stat
    # The manifest is written last and marks a completed build.
    args.index.mkdir(parents=True, exist_ok=False)
    encoder.model.save_pretrained(args.index / "model", safe_serialization=True)
    encoder.tokenizer.save_pretrained(args.index / "model")
    np.save(args.index / "embeddings.npy", matrix, allow_pickle=False)
    write_json(args.index / "groups.json", groups)
    environment = sorted(f"{d.metadata['Name']}=={d.version}" for d in importlib.metadata.distributions()
                         if d.metadata.get("Name"))
    (args.index / "environment.txt").write_text("\n".join(environment) + "\n", encoding="utf-8")
    manifest = {
        "experiment": EXPERIMENT, "model_id": MODEL_ID, "revision": revision,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "catalog_sha256": sha256_file(args.catalog), "code_sha256": sha256_file(__file__),
        "files_sha256": {name: sha256_file(args.index / name) for name in ["embeddings.npy", "groups.json"]},
        "python": platform.python_version(), "platform": platform.platform(), "packages": versions(),
        "device": args.device, "batch_size": args.batch_size,
        "chunk_tokens": CHUNK_TOKENS, "overlap_tokens": 0,
        "aggregation": "content_token_weighted_mean_of_unit_chunk_vectors_then_l2",
        "document_prefix": "passage: ", "query_prefix": "query: ", "tie_atol": TIE_ATOL,
        "songs": sum(len(g["songs"]) for g in groups), "lyric_groups": len(groups),
        "multi_chunk_groups": sum(s["chunks"] > 1 for s in stats),
        "chunks_total": sum(s["chunks"] for s in stats), "embedding_dimension": matrix.shape[1],
        "embedding_seconds": elapsed, "fine_tuned": False, "quality_evaluated": False,
        "score_display": "100 * cosine; range -100..100; NOT probability",
    }
    write_json(args.index / "manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


class Recommender:
    def __init__(self, index, device="cpu", batch_size=8):
        self.manifest = read_json(index / "manifest.json")
        if self.manifest["experiment"] != EXPERIMENT or self.manifest["code_sha256"] != sha256_file(__file__):
            raise ValueError("코드/인덱스 버전이 다릅니다. 같은 코드 또는 새 인덱스를 사용하세요.")
        for name, expected in self.manifest["files_sha256"].items():
            if sha256_file(index / name) != expected:
                raise ValueError(f"인덱스 파일이 변경되었습니다: {name}")
        if self.manifest["packages"] != versions():
            print("주의: 인덱스 생성 때와 패키지 버전이 다릅니다. 재현 시 environment.txt를 확인하세요.", file=sys.stderr)
        self.groups = read_json(index / "groups.json")
        self.matrix = np.load(index / "embeddings.npy", allow_pickle=False)
        shape = (len(self.groups), self.manifest["embedding_dimension"])
        if self.matrix.shape != shape or not np.isfinite(self.matrix).all():
            raise ValueError("인덱스 행렬이 유효하지 않습니다.")
        self.encoder = Encoder(str(index / "model"), local=True, device=device)
        self.batch_size = batch_size

    def recommend(self, diary):
        if not normalize(diary):
            raise ValueError("일기가 비어 있습니다.")
        started = time.perf_counter()
        query, stats = self.encoder.encode([diary], "query: ", self.batch_size)
        # Unit vectors: inner product equals cosine. Do not sigmoid or round before selection.
        scores = self.matrix @ query[0]
        if not np.isfinite(scores).all():
            raise ValueError("유효하지 않은 점수입니다.")
        best = float(scores.max())
        winners = np.flatnonzero(np.isclose(scores, best, rtol=0.0, atol=TIE_ATOL))
        songs = []
        for i in winners:
            for song in self.groups[i]["songs"]:
                songs.append({**song, "lyric_group_id": self.groups[i]["lyric_group_id"],
                              "cosine_similarity": float(scores[i]), "similarity_score": float(scores[i] * 100)})
        songs.sort(key=lambda s: (s["title"], s["artist"], s["song_id"]))
        return {"experiment": EXPERIMENT, "max_similarity": best, "tie_count": len(songs),
                "winning_lyric_groups": len(winners), "recommendations": songs,
                "diary_token_stats": stats[0], "query_ms": (time.perf_counter() - started) * 1000,
                "score_note": "코사인 유사도 × 100 (범위 -100~100), 적합 확률 아님"}


def display(result):
    print(f"\n추천 {result['tie_count']}곡 / 고유 가사 {result['winning_lyric_groups']}개")
    for song in result["recommendations"]:
        print(f"- {song['title']} — {song['artist']} [ID {song['song_id']}]")
        print(f"  의미 유사도 점수: {song['similarity_score']:.1f} (원점수 {song['cosine_similarity']:.8f})")
    print(result["score_note"])
    print(f"일기 처리: {result['diary_token_stats']['chunks']}조각 / {result['query_ms']:.1f} ms")


def run_dev(args, recommender):
    if args.output.exists():
        raise ValueError("평가 결과 폴더가 이미 있습니다. 새 --output을 지정하세요.")
    with args.diaries.open(encoding="utf-8-sig", newline="") as f:
        diaries = list(csv.DictReader(f))
    ids = [d.get("diary_id", "") for d in diaries]
    if not diaries or any(not i.strip() for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("일기 ID는 비어 있지 않고 고유해야 합니다.")
    if any(not normalize(d.get("text", "")) for d in diaries):
        raise ValueError("비어 있는 일기가 있습니다.")
    predictions, reviews = [], []
    for i, diary in enumerate(diaries, 1):
        result = recommender.recommend(diary["text"])
        predictions.append({"diary": diary, "result": result})
        for song in result["recommendations"]:
            reviews.append({"diary_id": diary["diary_id"], "diary_text": diary["text"], **song,
                            "emotion_score": "", "context_score": "", "overall_score": "",
                            "error_type": "", "notes": "", "rater_id": ""})
        print(f"개발 일기 {i}/{len(diaries)}", file=sys.stderr)
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output / "predictions.json", predictions)
    with (args.output / "human_review.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(reviews[0]))
        writer.writeheader()
        writer.writerows(reviews)
    write_json(args.output / "manifest.json", {"index_manifest": recommender.manifest,
               "diaries_sha256": sha256_file(args.diaries), "diary_count": len(diaries),
               "inference_packages": versions(), "device": args.device, "batch_size": args.batch_size,
               "quality_evaluated": False, "created_at_utc": datetime.now(timezone.utc).isoformat()})
    print(f"저장: {args.output}\n사람 평가 칸은 비어 있습니다. 자동 품질 점수는 만들지 않았습니다.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["build", "recommend", "dev"]:
        p = sub.add_parser(name)
        p.add_argument("--index", type=Path, default=ROOT / "artifacts" / "b1_e5_v01")
        p.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
        p.add_argument("--batch-size", type=int, default=8)
        if name == "build":
            p.add_argument("--catalog", type=Path, default=ROOT / "data" / "songs_catalog_v01.csv")
            p.add_argument("--revision", default="main", help="재현 시 manifest의 커밋 해시 사용")
        elif name == "recommend":
            group = p.add_mutually_exclusive_group()
            group.add_argument("--text")
            group.add_argument("--file", type=Path)
            p.add_argument("--json", action="store_true")
        else:
            p.add_argument("--diaries", type=Path, default=ROOT / "data" / "dev_diaries_synthetic_v01.csv")
            p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size는 1 이상이어야 합니다.")
    if args.device == "cuda" and not torch.cuda.is_available():
        parser.error("CUDA를 사용할 수 없습니다. 기본 CPU로 실행하세요.")
    torch.manual_seed(0)
    if args.command == "build":
        build(args)
        return
    recommender = Recommender(args.index, args.device, args.batch_size)
    if args.command == "dev":
        run_dev(args, recommender)
        return
    text = args.file.read_text(encoding="utf-8-sig") if args.file else args.text
    if args.json and text is None:
        parser.error("--json에는 --text 또는 --file이 필요합니다.")
    if text is not None:
        result = recommender.recommend(text)
        print(json.dumps(result, ensure_ascii=False, indent=2)) if args.json else display(result)
        return
    print("일기를 한 줄로 입력하세요. 종료: /quit")
    while True:
        diary = input("\n일기> ")
        if diary.strip() == "/quit":
            break
        if not normalize(diary):
            print("내용을 입력하세요.")
            continue
        display(recommender.recommend(diary))


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n종료했습니다.")
    except (ValueError, OSError) as error:
        print(f"오류: {error}", file=sys.stderr)
        sys.exit(1)
