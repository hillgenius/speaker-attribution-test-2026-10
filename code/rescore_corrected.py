#!/usr/bin/env python3
# Published copy: home-directory paths replaced with relative ones.
"""rescore_corrected.py: rescore all 100 hearings with every reference error found after the
locked scoring run corrected, applied the same way to every hearing so a correction that cuts
against HillGenius shows up too. Locked kit files and committed references are not touched:
corrected copies go to work/corrected/, scores to
work/scoring_corrected/.

Corrections:
  1. The member database's surname-matching field is null for Mark E. Green (G000590), Sylvester Turner (T000489) and
     Marjorie Taylor Greene (G000596). Filled ("Green", "Turner", "Greene") in every hearing's
     roster cache, so a "Green"/"Turner" gold label can no longer resolve only to Al Green or
     Michael Turner. The two references that froze those wrong ids get corrected copies:
     60649 Green G000553 -> G000590 and Turner T000463 -> T000489; 60692 Turner T000463 ->
     T000489. Each print's committee roster lists Mark E. Green (Chairman) and Sylvester Turner.
  2. Reference labels that name one speaker two ways, so the cluster vote splits:
     61366 RUBIO -> Rubio, MAST -> Mast; 61418 "Kim of California" -> Kim; 64242 VAN DUYNE ->
     Van Duyne.
  3. Print error: 59601 prints "Mr. Murray." for the witness Nicholas McMurray; those turns
     -> McMurray (no member id).
"""
import json
import shutil
import subprocess
from pathlib import Path

K = Path(__file__).resolve().parent  # the test kit
E = K / "work"  # scoring inputs and outputs
ORIG = E / "scoring"
C = E / "corrected"
OUT = E / "scoring_corrected"
PY = "python3"
CL_LAST = {"G000590": "Green", "T000489": "Turner", "G000596": "Greene"}
RELABEL = {
    "CHRG-119hhrg60649": {("Green", "G000553"): ("Green", "G000590"), ("Turner", "T000463"): ("Turner", "T000489")},
    "CHRG-119hhrg60692": {("Turner", "T000463"): ("Turner", "T000489")},
    "CHRG-119hhrg61366": {("RUBIO", None): ("Rubio", None), ("MAST", "M001199"): ("Mast", "M001199")},
    "CHRG-119hhrg61418": {("Kim of California", "K000397"): ("Kim", "K000397")},
    "CHRG-119hhrg64242": {("VAN DUYNE", None): ("Van Duyne", None)},
    "CHRG-119hhrg59601": {("Murray", "M001111"): ("McMurray", None)},
}

ids = json.loads((K / "hearing_ids.json").read_text())
drawn = [r["chrg"] for r in json.loads((K / "sample.json").read_text())["sample"]]
manifest = json.loads((E / "drawn_prints/manifest.json").read_text())

rc = C / "roster_cache"
rc.mkdir(parents=True, exist_ok=True)
filled = 0
for f in (K / "roster_cache").glob("*.json"):
    r = json.loads(f.read_text())
    for key in ("committee_candidates", "chamber_candidates", "other_chamber_candidates"):
        for cand in r.get(key) or []:
            if cand.get("bioguide_id") in CL_LAST and not cand.get("cl_last"):
                cand["cl_last"] = CL_LAST[cand["bioguide_id"]]
                filled += 1
    (rc / f.name).write_text(json.dumps(r))
print(f"roster cache: filled {filled} null cl_last entries")

log = []
for c in drawn:
    h = ids[c]
    ref_path = K / "reference" / h / "reference_final.json"
    if c in RELABEL:
        ref = json.loads(ref_path.read_text())
        n = 0
        for t in ref["turns"]:
            new = RELABEL[c].get((t["speaker"], t.get("bioguide_id")))
            if new:
                t["speaker"], t["bioguide_id"] = new
                n += t["word_end"] - t["word_start"]
        d = C / "reference" / h
        d.mkdir(parents=True, exist_ok=True)
        ref_path = d / "reference_final.json"
        ref_path.write_text(json.dumps(ref, indent=1))
        log.append(f"{c}: relabeled {n} reference words")
    d = OUT / h
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "score.log", "w") as lf:
        rcode = subprocess.run([PY, "score.py", "--hearing-id", h, "--chrg", c, "--print", manifest[c]["path"],
                                "--segments", str(ORIG / h / f"{h}-segments.jsonl"), "--out", str(d),
                                "--roster-cache", str(rc), "--reference", str(ref_path)],
                               cwd=K / "scorer", stdout=lf, stderr=subprocess.STDOUT).returncode
    if rcode:
        log.append(f"{c}: score.py exit {rcode}")
print("\n".join(log))
subprocess.run([PY, "pool.py", str(OUT / "*/*-per-cluster.jsonl"), "--out", str(OUT / "pooled.json")],
               cwd=K / "scorer", check=True)
