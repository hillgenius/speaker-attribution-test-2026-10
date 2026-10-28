#!/usr/bin/env python3
"""Score one hearing's HillGenius transcript against its GPO print, strictly (no hand
exclusions -- see README.md "GOLD_WRONG_CLUSTERS" note).

Pipeline (mirrors `build_gold_batch10.py` + `score_methods_batch10_shipped.py` in the
development harness, ~/hillgenius-exports/wordgold-tier-a/, adapted to read a self-contained
segments-jsonl input instead of cached prelabel.json/diarization.parquet/speaker_mapping.json
pipeline artifacts -- see PROVENANCE.md):

  1. Parse the GPO print into an ordered list of turns (gpo_turns.py / gpo_turns_senate.py,
     dispatched by chamber) and a parallel per-reference-word turn-id array.
  2. Read the segments jsonl (one row per diarized turn: a cluster id, the final name/
     bioguide HillGenius shipped for that cluster, start/end time, and the turn's text).
     Tokenize every segment's text the same way the GPO print's turns are tokenized
     (score_one.normalize), in chronological order, to build one hypothesis word stream for
     the whole hearing.
  3. Word-align the reference stream against the hypothesis stream with jiwer's
     process_words (the same WER-style alignment build_gold_batch10.py uses). A hypothesis
     word gets a gold speaker label only from an "equal" alignment run of at least
     `MIN_RUN` words that isn't within `MARGIN` reference words of a GPO speaker change --
     this is what keeps a gold label from leaking across a turn boundary into the wrong
     speaker.
  4. Each diarized cluster's gold speaker is the plurality vote among its own words' gold
     labels. A cluster with fewer than MIN_CLUSTER_SUPPORT votes, or with two-or-more gold
     speakers each holding a significant share of the vote (SIGNIFICANT_MIN_VOTES,
     UNRELIABLE_TOP_SHARE_2WAY), is "ambiguous" and discarded -- not scored either way.
  5. The cluster's shipped name is compared against its gold speaker. When the gold
     speaker is a member of the hearing's own committee (roster.py: the print's
     "Members present" sentence when it has one, else the hearing's Supabase committee
     membership) and the shipped segment carries a bioguide id, the comparison is by
     bioguide id -- `match_rule: "bioguide"` in the per-cluster row. Otherwise (a
     witness, an unresolved roster lookup, or either side missing an id) it falls back
     to the normalized-surname match (surname_match.py) -- `match_rule: "surname"`.
     correct / wrong / blank (no shipped name at all for that cluster).

`--reference <reference_final.json>` (written by finalize_reference.py) scores against the
hearing's frozen, reviewed reference instead of the parser's own turns: the reference words are
still the parser's (their sha256 must match the one the reference recorded, or scoring refuses),
but each word's speaker comes from the reference's turns. A header-scan line the reference lists
as reviewed (`header_scan_reviewed`) no longer blocks scoring; any other flagged line still does.

Writes `<out>/<hearing-id>-per-cluster.jsonl` (one row per scored or ambiguous cluster) and
`<out>/<hearing-id>-summary.json` (counts, precision/recall by cluster and by word, and the
alignment diagnostics build_gold_batch10.py also recorded -- WER, ref/hyp word counts, flags).
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from jiwer import process_words

from gpo_turns_senate import build_ref_turn_index_auto, chamber_of
from header_scan import scan_print
from roster import Roster, build_roster
from score_one import normalize
from surname_match import (US_STATE_ABBR, gold_surname_match, norm_surname, shipped_variants,
                            split_state_qualifier)

MIN_RUN = 3
MARGIN = 1
MIN_CLUSTER_SUPPORT = 3
SIGNIFICANT_MIN_VOTES = 20
UNRELIABLE_TOP_SHARE_2WAY = 0.90
ELIGIBILITY_MARGIN = 1.5


def load_segments(path: Path) -> list[dict]:
    segs = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        segs.append(row)
    segs.sort(key=lambda r: (r.get("sequence_number") is None,
                              r.get("sequence_number", 0),
                              r.get("start_time", 0.0)))
    return segs


def build_hyp_tokens(segments: list[dict]) -> tuple[list[str], list[int]]:
    """Returns (tokens, owner) where owner[i] is the index into `segments` that produced
    tokens[i]. Segments contribute tokens whether or not they carry a cluster id, so the
    jiwer alignment sees the hearing's full word stream; only clustered segments feed the
    per-cluster vote in `cluster_gold_map`."""
    tokens, owner = [], []
    for si, seg in enumerate(segments):
        for tok in normalize(seg.get("text") or "").split():
            tokens.append(tok)
            owner.append(si)
    return tokens, owner


def align_gold(ref_words: list[str], turn_id: list[int], turns: list[dict],
               hyp_tokens: list[str]) -> list[str | None]:
    """Returns one gold-speaker-or-None per hyp token, via jiwer word alignment plus the
    min-run / speaker-change-margin safety rules build_gold_batch10.py uses."""
    res = process_words(" ".join(ref_words), " ".join(hyp_tokens))
    ops = [{"type": o.type, "rs": o.ref_start_idx, "re": o.ref_end_idx,
            "hs": o.hyp_start_idx, "he": o.hyp_end_idx} for o in res.alignments[0]]
    op_hs = [o["hs"] for o in ops]

    spk_of_ref = [turns[t]["speaker"] for t in turn_id]
    unsafe = [False] * len(ref_words)
    for i in range(1, len(ref_words)):
        if spk_of_ref[i] != spk_of_ref[i - 1]:
            for j in range(max(0, i - MARGIN), min(len(ref_words), i + MARGIN)):
                unsafe[j] = True

    def op_at(h):
        i = bisect.bisect_right(op_hs, h) - 1
        i = max(0, min(i, len(ops) - 1))
        while i < len(ops) and ops[i]["he"] <= h:
            i += 1
        if i >= len(ops):
            return None
        o = ops[i]
        return o if o["hs"] <= h < o["he"] else None

    gold = []
    for h in range(len(hyp_tokens)):
        o = op_at(h)
        if o is None or o["type"] != "equal" or (o["he"] - o["hs"]) < MIN_RUN:
            gold.append(None)
            continue
        r = o["rs"] + (h - o["hs"])
        if unsafe[r]:
            gold.append(None)
            continue
        gold.append(spk_of_ref[r])
    return gold, res.wer


def cluster_gold_map(segments: list[dict], owner: list[int], gold: list[str | None]) -> dict:
    """cluster_id -> {gold_surname, support, total_votes, vote_breakdown, unreliable,
    unreliable_reason}, voting every gold-labeled hyp token into the diarized cluster that
    owns it (segments with no cluster_id contribute no votes anywhere -- same as a
    SPEAKER_UNKNOWN/CROSSTALK word being dropped in the development harness)."""
    votes = defaultdict(Counter)
    for h, spk in enumerate(gold):
        if spk is None:
            continue
        seg = segments[owner[h]]
        cid = seg.get("cluster_id")
        if not cid:
            continue
        votes[cid][spk] += 1

    out = {}
    for cid, counter in votes.items():
        top, n = counter.most_common(1)[0]
        total = sum(counter.values())
        significant = sorted(((s, c) for s, c in counter.items() if c >= SIGNIFICANT_MIN_VOTES),
                              key=lambda sc: -sc[1])
        unreliable, reason = False, None
        if len(significant) >= 3:
            unreliable = True
            reason = f"{len(significant)} distinct gold speakers each with >={SIGNIFICANT_MIN_VOTES} aligned words"
        elif len(significant) == 2:
            top_share = significant[0][1] / total
            if top_share < UNRELIABLE_TOP_SHARE_2WAY:
                unreliable = True
                reason = (f"2 distinct gold speakers with >={SIGNIFICANT_MIN_VOTES} words each, "
                          f"top share {top_share:.1%} < {UNRELIABLE_TOP_SHARE_2WAY:.0%}")
        out[cid] = {"gold_surname": top, "support": n, "total_votes": total,
                     "vote_breakdown": dict(counter.most_common()),
                     "unreliable": unreliable, "unreliable_reason": reason}
    return out


def cluster_shipped_label(segments: list[dict], cid: str) -> tuple[str | None, str | None, bool]:
    """(speaker_label, bioguide_id, consistent) for every segment sharing this cluster_id.
    `consistent` is False if the segments disagree on the label (should not happen in
    production -- a cluster's final name is decided once -- but is recorded rather than
    silently picking one if it ever does)."""
    labels = [(s.get("speaker_label") or None, s.get("bioguide_id") or None)
              for s in segments if s.get("cluster_id") == cid]
    if not labels:
        return None, None, True
    counts = Counter(labels)
    (label, bioguide), _ = counts.most_common(1)[0]
    return label, bioguide, len(counts) == 1


def unreviewed_headers(unparsed: list[dict], reviewed: list[str]) -> list[dict]:
    """The header-scan flags not covered by the reference's reviewed lines (matched by line
    text, one review per flagged occurrence)."""
    left = Counter(reviewed)
    out = []
    for u in unparsed:
        if left[u["line"]] > 0:
            left[u["line"]] -= 1
        else:
            out.append(u)
    return out


def reference_turn_index(reference: dict, ref_words: list[str], hearing_id: str,
                         chrg: str) -> tuple[list[int], list[dict]]:
    """(turn_id, turns) from a frozen reference_final.json, after checking it belongs to this
    hearing and print and that its turns tile `ref_words` exactly. Raises ValueError otherwise."""
    if reference.get("hearing_id") != hearing_id or reference.get("chrg") != chrg:
        raise ValueError(f"reference is for {reference.get('chrg')} {reference.get('hearing_id')}")
    digest = hashlib.sha256(" ".join(ref_words).encode()).hexdigest()
    if digest != reference.get("ref_words_sha256"):
        raise ValueError("the print's reference words differ from the ones the reference was built on")
    turns, turn_id = [], []
    for t in reference["turns"]:
        if t["word_start"] != len(turn_id) or t["word_end"] <= t["word_start"]:
            raise ValueError(f"reference turn {t.get('turn_index')} does not start where the previous one ends")
        turn_id.extend([len(turns)] * (t["word_end"] - t["word_start"]))
        turns.append({"speaker": t["speaker"], "bioguide_id": t.get("bioguide_id")})
    if len(turn_id) != len(ref_words):
        raise ValueError(f"reference covers {len(turn_id)} words, the print has {len(ref_words)}")
    return turn_id, turns


def _stats(correct: int, wrong: int, blank: int) -> tuple[int, float | None, float | None]:
    n_scored = correct + wrong
    precision = correct / n_scored if n_scored else None
    recall_denom = n_scored + blank
    recall = correct / recall_denom if recall_denom else None
    return n_scored, precision, recall


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hearing-id", required=True)
    ap.add_argument("--chrg", required=True, help="GovInfo package id, e.g. CHRG-119hhrg61939")
    ap.add_argument("--print", dest="print_path", required=True, type=Path,
                     help="Path to the GPO print (.htm or .txt)")
    ap.add_argument("--segments", required=True, type=Path,
                     help="Path to the segments jsonl (see fetch_inputs.py / README.md)")
    ap.add_argument("--out", required=True, type=Path, help="Output directory")
    ap.add_argument("--roster-cache", type=Path, default=None,
                     help="Directory of committed <hearing_id>.json roster caches "
                          "(roster.py): read/written there instead of always calling "
                          "hg-sql, so a public run with committed caches works offline.")
    ap.add_argument("--reference", type=Path, default=None,
                     help="Frozen reference_final.json (finalize_reference.py) to score against "
                          "instead of the parser's own turns.")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    chamber = chamber_of(args.chrg)
    reference = json.loads(args.reference.read_text()) if args.reference else None

    unparsed_headers = scan_print(args.print_path, args.chrg, chamber)
    (args.out / f"{args.hearing_id}_unparsed_headers.json").write_text(json.dumps(unparsed_headers, indent=1))
    n_headers_reviewed = 0
    if reference is not None:
        blocking = unreviewed_headers(unparsed_headers, reference.get("header_scan_reviewed", []))
        n_headers_reviewed = len(unparsed_headers) - len(blocking)
        unparsed_headers = blocking
    if unparsed_headers:
        print(f"{len(unparsed_headers)} unparsed header-like line(s) in {args.print_path} -- "
              f"see {args.out}/{args.hearing_id}_unparsed_headers.json. Refusing to score until "
              f"the print's header set is fully covered by gpo_turns.py/gpo_turns_senate.py "
              f"(see PROVENANCE.md, header_scan.py).", file=sys.stderr)
        for u in unparsed_headers[:10]:
            print(f"  [{u['reason']}] {u['line'][:100]!r}", file=sys.stderr)
        summary = {"hearing_id": args.hearing_id, "chrg": args.chrg, "chamber": chamber,
                   "unparsed_headers": len(unparsed_headers), "scored": False}
        (args.out / f"{args.hearing_id}-summary.json").write_text(json.dumps(summary, indent=1))
        sys.exit(1)

    ref_words, turn_id, turns = build_ref_turn_index_auto(args.print_path, args.chrg)
    reference_sha256 = None
    if reference is not None:
        try:
            turn_id, turns = reference_turn_index(reference, ref_words, args.hearing_id, args.chrg)
        except ValueError as exc:
            print(f"refusing to score: {exc} ({args.reference})", file=sys.stderr)
            sys.exit(1)
        reference_sha256 = hashlib.sha256(args.reference.read_bytes()).hexdigest()
    spk_of_ref = [turns[t]["speaker"] for t in turn_id]
    by_speaker = Counter(spk_of_ref)

    segments = load_segments(args.segments)
    hyp_tokens, owner = build_hyp_tokens(segments)

    flags = []
    ratio = len(ref_words) / max(1, len(hyp_tokens))
    if ratio > ELIGIBILITY_MARGIN:
        flags.append(f"ELIGIBILITY GUARD TRIPPED: ref_words {len(ref_words)} vs hyp_words "
                      f"{len(hyp_tokens)} (ratio {ratio:.2f}x > {ELIGIBILITY_MARGIN}x)")
    top, topn = (by_speaker.most_common(1) or [(None, 0)])[0]
    top_share = topn / max(1, len(ref_words))
    if len(by_speaker) <= 2:
        flags.append(f"only {len(by_speaker)} speaker(s) parsed from GPO print")
    if top_share > 0.60:
        flags.append(f"top speaker '{top}' holds {top_share:.0%} of GPO reference words")

    gold, wer = align_gold(ref_words, turn_id, turns, hyp_tokens)
    cmap = cluster_gold_map(segments, owner, gold)

    # Member scoring: the hearing's committee roster (roster.py), used below to compare a
    # member cluster's shipped bioguide id against the gold speaker's bioguide id directly,
    # when both are known -- a stricter signal than the surname match (two same-surname
    # members are never conflated even without a state-qualified gold label). A roster
    # lookup failure (hg-sql down, no network) is not fatal: every cluster just falls back
    # to the surname-only match, same as a witness or an unresolved roster name already does.
    try:
        roster = build_roster(args.print_path, args.hearing_id, roster_cache_dir=args.roster_cache)
    except Exception as exc:
        print(f"roster lookup failed ({exc}) -- scoring every cluster by surname only",
              file=sys.stderr)
        roster = Roster([], [], [], None, "none", [], None)
    print(f"  roster: source={roster.source} candidates={len(roster.candidates)}"
          f" (committee={len(roster.committee_candidates)} chamber={len(roster.chamber_candidates)}"
          f" other_chamber={len(roster.other_chamber_candidates)})"
          + (f" present={len(roster.present_bioguides)}" if roster.present_bioguides is not None else "")
          + (f" sentence_unresolved={roster.unresolved_sentence_tokens}" if roster.unresolved_sentence_tokens else ""),
          file=sys.stderr)

    # A gold label can carry a state-disambiguation suffix ("Carter of Georgia") when the
    # fixed parser needed one to tell apart two same-surname members/senators in this same
    # hearing (see surname_match.gold_surname_match). The state half of that suffix only
    # needs to be checked when it's actually doing disambiguating work here -- i.e. when
    # another scored cluster in this hearing has a *different* gold label sharing the same
    # base surname. Scanning the eligible clusters' gold labels up front avoids requiring a
    # state match for a hearing that happens to have only one same-surname member at all.
    base_to_golds = defaultdict(set)
    for entry in cmap.values():
        if entry["support"] < MIN_CLUSTER_SUPPORT or entry["unreliable"]:
            continue
        base, _state = split_state_qualifier(entry["gold_surname"])
        base_to_golds[norm_surname(base)].add(entry["gold_surname"])
    ambiguous_bases = {b for b, golds in base_to_golds.items() if len(golds) > 1}

    per_cluster_rows = []
    pooled = Counter()
    n_no_gold = n_unreliable = 0

    for cid, entry in sorted(cmap.items()):
        if entry["support"] < MIN_CLUSTER_SUPPORT:
            n_no_gold += 1
            continue
        if entry["unreliable"]:
            n_unreliable += 1
            per_cluster_rows.append({
                "hearing_id": args.hearing_id, "chrg": args.chrg, "cluster_id": cid,
                "gold_surname": entry["gold_surname"], "gold_cluster_support": entry["support"],
                "gold_cluster_total_votes": entry["total_votes"],
                "gold_vote_breakdown": entry["vote_breakdown"],
                "outcome": "ambiguous", "ambiguous_reason": entry["unreliable_reason"],
                "shipped_name": None, "shipped_bioguide_id": None,
            })
            continue

        label, bioguide, consistent = cluster_shipped_label(segments, cid)
        if not label:
            outcome = "blank"
            shipped_surname = None
            match_rule = None
            gold_bioguide = None
        else:
            surname, variants = shipped_variants(label)
            base, _state = split_state_qualifier(entry["gold_surname"])
            gold_state_abbr = US_STATE_ABBR.get(_state.lower()) if _state else None
            gold_bioguide = roster.resolve(base, gold_state_abbr)
            if gold_bioguide and bioguide:
                # Both sides have an id: the gold speaker is a resolved committee member
                # and the shipped segment carries HillGenius's own bioguide match. Compare
                # ids directly -- this is the task's "count correct iff the shipped
                # bioguide equals the reference id" rule, and is strictly more precise
                # than a surname match (a wrong same-surname member is never credited).
                outcome = "correct" if gold_bioguide == bioguide else "wrong"
                match_rule = "bioguide"
            else:
                # Either side has no id (a witness/staffer, an unresolved roster lookup,
                # or a shipped segment with no bioguide match) -- fall back to the
                # existing normalized-surname match.
                state_required = norm_surname(base) in ambiguous_bases
                outcome = ("correct" if gold_surname_match(label, variants, entry["gold_surname"],
                                                             state_required=state_required)
                           else "wrong")
                match_rule = "surname"
            shipped_surname = surname
        pooled[outcome] += 1
        per_cluster_rows.append({
            "hearing_id": args.hearing_id, "chrg": args.chrg, "cluster_id": cid,
            "gold_surname": entry["gold_surname"], "gold_cluster_support": entry["support"],
            "gold_cluster_total_votes": entry["total_votes"],
            "gold_vote_breakdown": entry["vote_breakdown"],
            "outcome": outcome, "shipped_name": label, "shipped_bioguide_id": bioguide,
            "shipped_surname": shipped_surname,
            "label_consistent_across_segments": consistent,
            "gold_bioguide_id": gold_bioguide, "match_rule": match_rule,
        })

    n_scored, precision, recall = _stats(pooled["correct"], pooled["wrong"], pooled["blank"])
    n_bioguide_decided = sum(1 for r in per_cluster_rows if r.get("match_rule") == "bioguide")
    n_surname_decided = sum(1 for r in per_cluster_rows if r.get("match_rule") == "surname")
    word_correct = sum(r["gold_cluster_support"] for r in per_cluster_rows if r["outcome"] == "correct")
    word_wrong = sum(r["gold_cluster_support"] for r in per_cluster_rows if r["outcome"] == "wrong")
    word_blank = sum(r["gold_cluster_support"] for r in per_cluster_rows if r["outcome"] == "blank")
    _, word_precision, word_recall = _stats(word_correct, word_wrong, word_blank)

    with (args.out / f"{args.hearing_id}-per-cluster.jsonl").open("w") as fh:
        for row in per_cluster_rows:
            fh.write(json.dumps(row) + "\n")

    summary = {
        "hearing_id": args.hearing_id, "chrg": args.chrg, "chamber": chamber,
        "wer": round(wer, 4), "ref_words": len(ref_words), "hyp_words": len(hyp_tokens),
        "gpo_turns": len(turns), "gpo_speakers": len(by_speaker),
        "ref_to_hyp_ratio": round(ratio, 4), "flags": flags,
        "unparsed_headers": len(unparsed_headers),
        "reference": "final" if reference is not None else "parser",
        "reference_sha256": reference_sha256, "unparsed_headers_reviewed": n_headers_reviewed,
        "n_clusters_scored": len(per_cluster_rows) - n_unreliable,
        "n_no_gold_cluster": n_no_gold, "n_ambiguous": n_unreliable,
        "roster_source": roster.source, "roster_candidates": len(roster.candidates),
        "roster_sentence_unresolved": roster.unresolved_sentence_tokens,
        "roster_unresolved": roster.roster_unresolved,
        "n_bioguide_decided": n_bioguide_decided, "n_surname_decided": n_surname_decided,
        "by_cluster": {"n_answered": n_scored, "n_blank": pooled["blank"],
                        "n_correct": pooled["correct"], "n_wrong": pooled["wrong"],
                        "precision": precision, "recall": recall},
        "by_word": {"n_answered": word_correct + word_wrong, "n_blank": word_blank,
                     "n_correct": word_correct, "n_wrong": word_wrong,
                     "precision": word_precision, "recall": word_recall},
    }
    (args.out / f"{args.hearing_id}-summary.json").write_text(json.dumps(summary, indent=1))

    print(f"{args.hearing_id} [{args.chrg}, {chamber}]  WER={wer:.4f}  "
          f"clusters scored={summary['n_clusters_scored']} ambiguous={n_unreliable} no_gold={n_no_gold}")
    p = f"{precision:.1%}" if precision is not None else "n/a"
    r = f"{recall:.1%}" if recall is not None else "n/a"
    print(f"  by-cluster  correct={pooled['correct']} wrong={pooled['wrong']} blank={pooled['blank']}  "
          f"precision={p} recall={r}")
    wp = f"{word_precision:.1%}" if word_precision is not None else "n/a"
    wr = f"{word_recall:.1%}" if word_recall is not None else "n/a"
    print(f"  by-word     correct={word_correct} wrong={word_wrong} blank={word_blank}  "
          f"precision={wp} recall={wr}")
    print(f"  match_rule  bioguide={n_bioguide_decided} surname={n_surname_decided}")
    if roster.roster_unresolved:
        print(f"  roster_unresolved (surname collisions, no id decided): {len(roster.roster_unresolved)}",
              file=sys.stderr)
    if flags:
        print(f"  flags: {'; '.join(flags)}")
    print(f"wrote {args.out}/{args.hearing_id}-per-cluster.jsonl, {args.out}/{args.hearing_id}-summary.json")


if __name__ == "__main__":
    main()
