#!/usr/bin/env python3
"""Pool many hearings' `score.py` per-cluster jsonl output into the public test's two
headline numbers (strict and adjudicated), each reported two ways (by cluster, by word).

Strict: every per-cluster row as `score.py` wrote it, exactly as printed -- no hand
exclusions. This intentionally does NOT replicate the development harness's
GOLD_WRONG_CLUSTERS dicts (clusters a developer decided the GPO-alignment gold label
itself was wrong for and dropped before scoring): the public test scores the print as-is,
and any genuine print-vs-reality disagreement is handled by the separate, published
adjudication pass below -- see the kit README's "Adjudication rule" section.

Adjudicated: strict, plus the pre-registered adjudication rule applied. An adjudications
file is a JSON list of:

    {"hearing_id": "...", "cluster_id": "...", "verdict": "overturned", "evidence": "..."}

Only `"overturned"` entries change a number (a `"wrong"` row for that (hearing_id,
cluster_id) is recounted as `"correct"`, because the hearing's own video or a speaker's own
spoken self-identification showed the print was wrong for that turn). Any other verdict
(e.g. `"upheld"`, recording that a disagreement was reviewed and the print stands) changes
nothing numerically -- it exists so every reviewed disagreement is in the file, not just the
overturned ones, per the reporting rule ("a disagreement that stands against HillGenius is
listed exactly like one that was overridden"). An adjudication naming a (hearing_id,
cluster_id) this pool doesn't have a "wrong" row for is reported as unmatched rather than
silently ignored, since that usually means a hearing_id/cluster_id typo.

Usage:
  pool.py cluster1.jsonl cluster2.jsonl ...
  pool.py "out/*/*-per-cluster.jsonl" --adjudications adjudications.json
"""
from __future__ import annotations

import argparse
import glob
import json
from collections import Counter
from pathlib import Path


def load_rows(patterns: list[str]) -> list[dict]:
    paths = []
    for pat in patterns:
        matched = sorted(glob.glob(pat))
        paths.extend(matched if matched else [pat])
    rows = []
    seen_paths = set()
    for p in paths:
        p = str(Path(p))
        if p in seen_paths:
            continue
        seen_paths.add(p)
        for line in Path(p).read_text().splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _stats(correct: int, wrong: int, blank: int) -> dict:
    n_scored = correct + wrong
    precision = correct / n_scored if n_scored else None
    recall_denom = n_scored + blank
    recall = correct / recall_denom if recall_denom else None
    return {"n_correct": correct, "n_wrong": wrong, "n_blank": blank,
            "n_answered": n_scored, "precision": precision, "recall": recall}


def pool_rows(rows: list[dict]) -> dict:
    scorable = [r for r in rows if r["outcome"] in ("correct", "wrong", "blank")]
    by_cluster = Counter(r["outcome"] for r in scorable)
    by_word = Counter()
    for r in scorable:
        by_word[r["outcome"]] += r.get("gold_cluster_support", 0)
    n_hearings = len({r["hearing_id"] for r in rows})
    n_ambiguous = sum(1 for r in rows if r["outcome"] == "ambiguous")
    return {
        "n_hearings": n_hearings,
        "n_clusters_scored": len(scorable),
        "n_ambiguous_discarded": n_ambiguous,
        "by_cluster": _stats(by_cluster["correct"], by_cluster["wrong"], by_cluster["blank"]),
        "by_word": _stats(by_word["correct"], by_word["wrong"], by_word["blank"]),
    }


def apply_adjudications(rows: list[dict], adjudications: list[dict]) -> tuple[list[dict], list[dict]]:
    """Returns (adjudicated_rows, unmatched). Only mutates a copy; `rows` is untouched so
    the caller can still report strict numbers from the original list."""
    by_key = {}
    for i, r in enumerate(rows):
        by_key.setdefault((r.get("hearing_id"), r.get("cluster_id")), []).append(i)

    out = [dict(r) for r in rows]
    unmatched = []
    for adj in adjudications:
        key = (adj.get("hearing_id"), adj.get("cluster_id"))
        idxs = by_key.get(key)
        if not idxs:
            unmatched.append(adj)
            continue
        if adj.get("verdict") != "overturned":
            continue
        for i in idxs:
            if out[i]["outcome"] == "wrong":
                out[i]["outcome"] = "correct"
                out[i]["adjudicated"] = True
                out[i]["adjudication_evidence"] = adj.get("evidence")
            else:
                unmatched.append({**adj, "note": f"row outcome was {out[i]['outcome']!r}, not 'wrong'"})
    return out, unmatched


def _fmt(stats: dict, label: str) -> str:
    p = f"{stats['precision']:.1%}" if stats["precision"] is not None else "n/a"
    r = f"{stats['recall']:.1%}" if stats["recall"] is not None else "n/a"
    return (f"  {label:9s} correct={stats['n_correct']:4d} wrong={stats['n_wrong']:4d} "
            f"blank={stats['n_blank']:4d}  precision={p:>6s}  recall={r:>6s}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", help="per-cluster jsonl files or glob patterns")
    ap.add_argument("--adjudications", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None, help="write the pooled JSON here too")
    args = ap.parse_args()

    rows = load_rows(args.inputs)
    if not rows:
        raise SystemExit("no per-cluster rows found in the given inputs")

    strict = pool_rows(rows)
    result = {"strict": strict}

    print(f"{strict['n_hearings']} hearings, {strict['n_clusters_scored']} scored clusters "
          f"({strict['n_ambiguous_discarded']} ambiguous discarded)")
    print("STRICT:")
    print(_fmt(strict["by_cluster"], "by-cluster"))
    print(_fmt(strict["by_word"], "by-word"))

    if args.adjudications:
        adjudications = json.loads(args.adjudications.read_text())
        adj_rows, unmatched = apply_adjudications(rows, adjudications)
        adjudicated = pool_rows(adj_rows)
        result["adjudicated"] = adjudicated
        result["n_adjudications_applied"] = sum(1 for r in adj_rows if r.get("adjudicated"))
        result["unmatched_adjudications"] = unmatched

        print(f"\nADJUDICATED ({result['n_adjudications_applied']} overturned applied, "
              f"{len(unmatched)} unmatched/no-op):")
        print(_fmt(adjudicated["by_cluster"], "by-cluster"))
        print(_fmt(adjudicated["by_word"], "by-word"))
        if unmatched:
            print("  unmatched adjudications (no matching 'wrong' row -- check for a typo):")
            for u in unmatched:
                print(f"    {u}")

    if args.out:
        args.out.write_text(json.dumps(result, indent=1))
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
