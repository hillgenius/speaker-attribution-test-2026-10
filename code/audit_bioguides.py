#!/usr/bin/env python3
# Published copy: home-directory paths replaced with relative ones.
"""audit_bioguides.py: every (hearing, speaker, bioguide) the 100 frozen references resolved, checked
against the print's own member lists. A resolved member passes when some column of a print line
names their surname next to their state (GPO rosters: "Mark E. Green, MD, Tennessee, Chairman",
"Sheri Biggs, South Carolina          Sylvester Turner, Texas"). Prints the rest for review, with
the print's roster columns that carry the same surname."""
import json, re, unicodedata
from collections import Counter
from pathlib import Path
from bs4 import BeautifulSoup

K = Path(__file__).resolve().parent  # the test kit
M = json.loads((K / "work/drawn_prints/manifest.json").read_text())
ids = json.loads((K / "hearing_ids.json").read_text())
drawn = [r["chrg"] for r in json.loads((K / "sample.json").read_text())["sample"]]
ST = {"AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
      "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
      "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
      "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
      "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
      "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
      "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
      "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
      "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
      "WI": "Wisconsin", "WY": "Wyoming", "PR": "Puerto Rico", "GU": "Guam", "VI": "Virgin Islands",
      "AS": "American Samoa", "MP": "Northern Mariana Islands", "DC": "District of Columbia"}


def fold(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


bad, ok, nores = [], 0, Counter()
for c in drawn:
    h = ids[c]
    fin = json.loads((K / "reference" / h / "reference_final.json").read_text())["turns"]
    roster = json.loads((K / "roster_cache" / f"{h}.json").read_text())
    entries = {}
    def walk(o):
        if isinstance(o, dict):
            if "bioguide_id" in o and "name" in o:
                entries[o["bioguide_id"]] = o
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(roster)
    p = Path(M[c]["path"])
    raw = p.read_text() if p.suffix == ".txt" else BeautifulSoup(p.read_text(), "html.parser").get_text("\n")
    cols = [fold(x) for l in raw.split("\n") for x in re.split(r"\s{3,}", l.strip()) if x]
    words = Counter()
    for t in fin:
        if t.get("bioguide_id"):
            words[(t["speaker"], t["bioguide_id"])] += t["word_end"] - t["word_start"]
    for (sp, bg), n in words.items():
        e = entries.get(bg)
        if not e:
            nores[c] += 1
            bad.append((c, sp, bg, n, "bioguide not in roster_cache", []))
            continue
        last = fold(e.get("cl_last") or e["name"].split()[-1])
        state = fold(ST.get(e.get("state", ""), e.get("state", "")))
        if any(last in col and state in col for col in cols if "," in col):
            ok += 1
        else:
            same = sorted({col[:80] for col in cols if last in col and "," in col and len(col) < 90})[:4]
            bad.append((c, sp, bg, n, f"{e['name']} ({e.get('state')})", same))
print(f"resolved (speaker, bioguide) pairs passing the print-roster check: {ok}; to review: {len(bad)}")
for b in bad:
    print(*b[:5], "| print:", b[5])
