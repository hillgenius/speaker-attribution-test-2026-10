#!/usr/bin/env python3
"""Step 2 of the public speaker-attribution test: the sampler, published before the seed exists.

Draws a full permutation of population.json (every hearing, no replacement), in the
population's frozen sort order (by chrg) as the starting sequence, using Python's
`random.Random(seed)`. The seed is the integer value of a 128-hex NIST Randomness Beacon v2
pulse `outputValue`, for a pulse timestamp announced at least 24 hours in advance (README.md
has the rule). This script never fetches the beacon; it only takes the hex string on the
command line, so the draw is reproducible offline by anyone holding population.json and the
pulse value.

The first `n` positions of the permutation are the sample that gets processed. Positions
n+1..N are the pre-registered, ordered **replacement list**: if a sampled hearing turns out to
be unprocessable for a reason outside the pipeline's control (no public video, the print turns
out to be a different event than the audio, video shorter than 10 minutes), it is replaced by
the next unused position in this list, in order — never a hand-picked substitute. A hearing
that fails inside the pipeline itself is not replaced; it is reported as a failure.

Writes sample.json: the population hash it was drawn from, the seed, `n`, the `sample` (the
first n positions), and the `replacements` (the ordered remainder, positions n+1..N). Prints
the sha256 of sample.json.

Usage: python3 sampler.py --seed <128-hex outputValue> --n 100
       python3 sampler.py --dry-run [--n 100]   # seed 00*128, for testing the mechanics only
"""
import argparse
import hashlib
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent


def permute(pop_hearings, seed_hex):
    rng = random.Random(int(seed_hex, 16))
    # frozen order: population.json's own sort (by chrg); the permutation must start from that
    # fixed sequence, not from whatever order json.load happens to preserve, so re-sort defensively.
    frozen = sorted(pop_hearings, key=lambda x: x["chrg"])
    order = rng.sample(frozen, len(frozen))  # a full permutation, no replacement
    return [{"position": i + 1, **h} for i, h in enumerate(order)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", help="128-hex outputValue of a NIST Randomness Beacon v2 pulse")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--dry-run", action="store_true", help="use a stand-in seed (00*128); never a real draw")
    ap.add_argument("--population", default=str(HERE / "population.json"))
    args = ap.parse_args()

    if args.dry_run:
        seed = "0" * 128
    elif args.seed:
        seed = args.seed
    else:
        raise SystemExit("--seed <128-hex NIST beacon outputValue> is required (or --dry-run)")

    if len(seed) != 128 or any(c not in "0123456789abcdefABCDEF" for c in seed):
        raise SystemExit("seed must be the 128-hex outputValue of a beacon pulse")

    pop_path = Path(args.population)
    pop = json.loads(pop_path.read_text())
    hearings = pop["hearings"]
    if args.n > len(hearings):
        raise SystemExit(f"--n {args.n} exceeds population size {len(hearings)}")

    permutation = permute(hearings, seed)
    sample = permutation[:args.n]
    replacements = permutation[args.n:]

    out = {
        "population_sha256": hashlib.sha256(pop_path.read_bytes()).hexdigest(),
        "population_size": len(hearings),
        "seed": seed,
        "n": args.n,
        "dry_run": args.dry_run,
        "sample": sample,
        "replacements": replacements,
    }
    dest = HERE / ("sample_dry_run.json" if args.dry_run else "sample.json")
    dest.write_text(json.dumps(out, indent=1) + "\n")
    h = hashlib.sha256(dest.read_bytes()).hexdigest()

    print(f"drew {len(sample)} of {len(hearings)} hearings as the sample, "
          f"{len(replacements)} held as the ordered replacement list, "
          f"from population sha256 {out['population_sha256'][:16]}... -> {dest.name}")
    print(f"{dest.name} sha256 {h}")
    for s in sample[:10]:
        print(f"  {s['position']:3d}  {s['chrg']:<22} {s['chamber']:<7} {s['date']}  {s['title'][:60]}")
    if replacements:
        r0 = replacements[0]
        print(f"  first replacement (position {r0['position']}): {r0['chrg']} {r0['chamber']} "
              f"{r0['date']}  {r0['title'][:60]}")


if __name__ == "__main__":
    main()
