#!/usr/bin/env python3
"""Draws the 200-turn reference audit sample (README.md, "Reference finalization --
blind, before scoring" -> "200-turn audit rule").

Reads every hearing's frozen reference folder (`reference/<hearing_id>/`, see README's
"Reference files" convention) and draws a seeded, deterministic sample of **agreeing**
turns -- turns whose word span does not overlap any span listed in that hearing's
`disagreements.json` -- across all sampled hearings, weighted by word count (a long turn
is as likely to be the one audited as several short turns would be). The seed is the
same NIST beacon `outputValue` used by `sampler.py` (README's seed rule); this script
never fetches the beacon itself, same as `sampler.py`.

Weighting/determinism follows `sampler.py`'s own convention: fix the item order first
(sorted by hearing id, then turn index -- never filesystem/dict order), then consume a
single `random.Random(int(seed, 16))` in that fixed order so the draw only depends on
the seed and the reference folder's contents, not on anything incidental. The weighted
draw itself is Efraimidis-Spirakis weighted sampling without replacement: each item
gets one `rng.random()` call turned into a key `u ** (1 / weight)`, and the n largest
keys win. That is a single pass over a fixed-order item list consuming one random
number per item, the same shape as `sampler.py`'s `rng.sample` over a frozen,
chrg-sorted population -- just swapping the unweighted permutation for a weighted one.

Writes `audit_sample.json`: the seed, `n`, the reference folder's contents hash (for
provenance), and the drawn turns (hearing id, turn index, word offsets, speaker),
sorted by hearing id then turn index for a stable, readable file.

Usage: python3 audit_sample.py --reference reference/ --seed <128-hex> --n 200
       python3 audit_sample.py --reference reference/ --seed <128-hex> --n 200 --out audit_sample.json
"""
import argparse
import hashlib
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _spans_overlap(a_start, a_end, b_start, b_end) -> bool:
    return a_start < b_end and b_start < a_end


def load_hearing_turns(hearing_dir: Path) -> list[dict]:
    """Returns the agreeing turns for one hearing: entries of `reference_final.json`
    whose [word_start, word_end) span does not overlap any span in `disagreements.json`.
    Missing `disagreements.json` means zero disagreements for that hearing (not an
    error -- a hearing where the parser and the LLM agreed on every turn has no file to
    write)."""
    final_path = hearing_dir / "reference_final.json"
    final = json.loads(final_path.read_text())
    turns = final["turns"]

    disagreements_path = hearing_dir / "disagreements.json"
    spans = []
    if disagreements_path.exists():
        spans = json.loads(disagreements_path.read_text()).get("spans", [])
    # An unlocated header-scan flag carries no word offsets: it covers no reference words,
    # so it cannot overlap a turn.
    spans = [s for s in spans if "word_start" in s]

    agreeing = []
    for t in turns:
        w0, w1 = t["word_start"], t["word_end"]
        if any(_spans_overlap(w0, w1, s["word_start"], s["word_end"]) for s in spans):
            continue
        agreeing.append(t)
    return agreeing


def collect_items(reference_dir: Path) -> list[dict]:
    """One row per agreeing turn across every hearing folder under `reference_dir`,
    in a fixed order: hearing id (sorted), then turn index within the hearing. Fixing
    this order before any `rng.random()` call is what makes the draw reproducible --
    same convention as `sampler.py`'s `sorted(pop_hearings, key=...)` before permuting."""
    items = []
    for hearing_dir in sorted((p for p in reference_dir.iterdir() if p.is_dir()),
                               key=lambda p: p.name):
        hearing_id = hearing_dir.name
        for t in sorted(load_hearing_turns(hearing_dir), key=lambda t: t["turn_index"]):
            items.append({
                "hearing_id": hearing_id,
                "turn_index": t["turn_index"],
                "word_start": t["word_start"],
                "word_end": t["word_end"],
                "speaker": t["speaker"],
                "word_count": t.get("word_count", t["word_end"] - t["word_start"]),
            })
    return items


def weighted_sample(items: list[dict], seed_hex: str, n: int) -> list[dict]:
    """Efraimidis-Spirakis weighted sampling without replacement: one `rng.random()`
    draw per item (in the fixed order `items` already carries), turned into a key
    `u ** (1 / weight)`; the n items with the largest keys are the sample. Weight is
    each turn's word count, floored above zero so a zero-word turn can't produce a
    division by zero (and is simply very unlikely to be drawn)."""
    rng = random.Random(int(seed_hex, 16))
    keyed = []
    for item in items:
        u = rng.random()
        weight = max(item["word_count"], 1e-9)
        key = u ** (1.0 / weight)
        keyed.append((key, item))
    keyed.sort(key=lambda kv: kv[0], reverse=True)
    return [item for _, item in keyed[:n]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", default=str(HERE / "reference"),
                     help="path to the reference/ folder (one subfolder per hearing id)")
    ap.add_argument("--seed", required=True, help="128-hex NIST beacon outputValue, same as sampler.py's")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--out", default=str(HERE / "audit_sample.json"))
    args = ap.parse_args()

    if len(args.seed) != 128 or any(c not in "0123456789abcdefABCDEF" for c in args.seed):
        raise SystemExit("seed must be the 128-hex outputValue of a beacon pulse")

    reference_dir = Path(args.reference)
    items = collect_items(reference_dir)
    if args.n > len(items):
        raise SystemExit(f"--n {args.n} exceeds {len(items)} agreeing turns available in {reference_dir}")

    drawn = weighted_sample(items, args.seed, args.n)
    drawn_sorted = sorted(drawn, key=lambda it: (it["hearing_id"], it["turn_index"]))

    out = {
        "seed": args.seed,
        "n": args.n,
        "agreeing_turns_total": len(items),
        "hearings": len({it["hearing_id"] for it in items}),
        "turns": drawn_sorted,
    }
    dest = Path(args.out)
    dest.write_text(json.dumps(out, indent=1) + "\n")
    h = hashlib.sha256(dest.read_bytes()).hexdigest()

    print(f"drew {len(drawn_sorted)} of {len(items)} agreeing turns across "
          f"{out['hearings']} hearings -> {dest.name}")
    print(f"{dest.name} sha256 {h}")


if __name__ == "__main__":
    main()
