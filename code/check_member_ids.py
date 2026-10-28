#!/usr/bin/env python3
"""check_member_ids.py: compare every scored voice's member id with the member ids in the
reference the score used. Written after scoring, in answer to a review: score.py matches a
member by Bioguide id only when it can resolve the print's speaker on the roster, and by surname
otherwise, so a surname match could credit a different member who shares the name. This check
does not rescore anything; it reports, voice by voice, whether our id agrees with the reference.

Runs on the published folder alone:

    python code/check_member_ids.py <published folder>

The reference for a hearing is references_corrected/<hearing_id>/ where it exists, otherwise
references/<hearing_id>/. Writes results/member_id_check.jsonl (one row per scored voice) and
prints a summary as JSON.

id_check values:
  agrees           our id is the reference's id for that speaker
  conflicts        the reference has an id for that speaker and ours is a different one
  no_id_ours       the reference has an id; our label names the speaker but carries no id
  no_id_reference  the reference has no member id for that speaker (witnesses, staff, and
                   members the reference left unresolved); same_surname_in_chamber lists the
                   other members of the chamber with our member's surname, if any
"""
import collections
import json
import sys
from pathlib import Path

B = Path(sys.argv[1])
rows = [json.loads(l) for l in (B / "results/per_cluster.jsonl").read_text().splitlines() if l.strip()]


def reference(h):
    p = B / "references_corrected" / h / "reference_final.json"
    if not p.exists():
        p = B / "references" / h / "reference_final.json"
    return json.loads(p.read_text())


refs, rosters, out = {}, {}, []
count = collections.Counter()
for r in rows:
    if r["outcome"] not in ("correct", "wrong"):
        continue
    h = r["hearing_id"]
    if h not in refs:
        refs[h] = reference(h)
        rosters[h] = json.loads((B / "roster_cache" / f"{h}.json").read_text())
    words = collections.Counter()
    for t in refs[h]["turns"]:
        if t["speaker"] == r["gold_surname"] and t.get("bioguide_id"):
            words[t["bioguide_id"]] += t["word_end"] - t["word_start"]
    ours = r["shipped_bioguide_id"]
    same = []
    if not words:
        check = "no_id_reference"
        if ours:
            sur = (r["shipped_surname"] or "").lower()
            same = sorted({c["bioguide_id"] for c in rosters[h].get("chamber_candidates") or []
                           if (c.get("cl_last") or "").lower() == sur and c["bioguide_id"] != ours})
    elif ours in words:
        check = "agrees"
    elif ours:
        check = "conflicts"
    else:
        check = "no_id_ours"
    count[(r["outcome"], check)] += 1
    if same:
        count[(r["outcome"], "no_id_reference_same_surname")] += 1
    out.append({"chrg": r["chrg"], "hearing_id": h, "cluster_id": r["cluster_id"], "outcome": r["outcome"],
                "gold_surname": r["gold_surname"], "shipped_name": r["shipped_name"],
                "shipped_bioguide_id": ours, "reference_bioguide_ids": dict(words), "id_check": check,
                "same_surname_in_chamber": same})

(B / "results/member_id_check.jsonl").write_text("".join(json.dumps(o, ensure_ascii=False) + "\n" for o in out))
summary = {outcome: {check: n for (o, check), n in sorted(count.items()) if o == outcome}
           for outcome in ("correct", "wrong")}
summary["correct_same_surname_voices"] = [
    {k: o[k] for k in ("chrg", "cluster_id", "gold_surname", "shipped_name", "shipped_bioguide_id",
                       "same_surname_in_chamber")}
    for o in out if o["outcome"] == "correct" and o["same_surname_in_chamber"]]
print(json.dumps(summary, indent=1, ensure_ascii=False))
