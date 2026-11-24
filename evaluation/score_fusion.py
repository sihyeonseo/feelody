"""Report partial-identification bounds until the new top three are fully rated."""
import csv
import json
from pathlib import Path
from statistics import mean

from openpyxl import load_workbook


def score(runs, known, workbook):
    with Path(known).open(encoding="utf-8-sig") as f:
        labels = {(r["diary_id"],r["lyric_group_id"]):int(r["grade"]) for r in csv.DictReader(f)}
    wb = load_workbook(workbook, read_only=True)
    for sheet in ("045 먼저","나머지"):
        for did, gid, _, _, grade in list(wb[sheet].values)[1:]:
            if grade is None:
                continue
            if type(grade) is not int or grade not in range(4):
                raise ValueError(f"Invalid grade for {did} {gid}")
            if labels.setdefault((did,gid),grade) != grade:
                raise ValueError(f"Conflicting grade for {did} {gid}")
    rows = json.loads(Path(runs).read_text())["rows"]
    if len(rows)!=10 or len({r["diary"] for r in rows})!=10:
        raise ValueError("Expected the ten frozen diaries")
    for name in rows[0]["orders"]:
        hits, unknown, hits_per_diary = 0, 0, []
        for r in rows:
            gs = [labels.get((r["diary"],g)) for g in r["orders"][name][:3]]
            hit = any(g is not None and g>=2 for g in gs)
            hits_per_diary.append((int(hit),int(hit or None in gs)))
            hits += sum(g is not None and g>=2 for g in gs)
            unknown += gs.count(None)
        n = 3*len(rows)
        print(f"{name:20} Precision@3 [{hits/n:.3f}, {(hits+unknown)/n:.3f}]  "
              f"Hit@3 [{mean(r[0] for r in hits_per_diary):.2f}, {mean(r[1] for r in hits_per_diary):.2f}]  미채점 {unknown}/{n}")
    if all("matches_archived_kure" in r for r in rows):
        print("KURE 기준 순서 재현",sum(r["matches_archived_kure"] for r in rows),"/",len(rows))
    grades = [grade for (did,_),grade in labels.items() if did=="AIREF_045"]
    print("045 후보 채점",len(grades),"/ 30")
    if any(g>=2 for g in grades):
        print("045: 기존 KURE 최종 3곡 밖에 적합곡이 확인됨")
    elif len(grades)==30:
        print("045: 기존 후보 30개 안에 적합곡 없음")
    else:
        print("045: 원인 미확정")
