"""Header-scan precheck: before a print is scored, look for lines that read like a turn
header but that neither `gpo_turns.LEADER` nor `gpo_turns_senate.SENATE_LEADER` accepted
as one.

Why this exists: the Tier-A WRONG-TURN audit
(`~/hillgenius-exports/wordgold-tier-a/out/factcheck_1013/WRONG-TURN-AUDIT.md`, built by
`header_scan.py` in that same folder -- a development-only export, not part of this repo)
found that 92% of the words the batch scorers counted "wrong" were not real attribution
mistakes at all: they were the scorer's own gold reference slipping, because the GPO print
contained a turn header the parser didn't recognize (an unrecognized bracket annotation, a
bare "Chair NAME." form, "Mr. Carter of Georgia.", a header with no period, one wrapped
across two physical lines) and the words that should have opened a new turn were folded
into whichever turn was still open instead. PR #402 fixed the specific forms that audit
found; this module is the standing defense against the *next* one -- it runs on every print
this scorer is given and fails loudly if a line looks like a header the parser didn't take,
so a slip is caught before a hearing is scored rather than adjudicated after the fact.

This is deliberately a superset detector, not a parser: it walks the parsers' own per-line
stream (`gpo_turns.house_body_lines()`/`gpo_turns_senate.senate_body_lines()`, the same
generators `gpo_turns()`/`gpo_turns_senate()` consume), so a line this module calls
"accepted" is exactly a line the real parser opened a turn on -- same body bounds, same
front-matter slice, same recurrence counts, same running known-speaker set. (Until
2026-10-26 it re-derived that decision from the `LEADER`/`SENATE_LEADER` regexes and
guards with whole-print inputs and no recurrence counts, and 768 of the 1,703 House lines
it flagged across the 141 population prints were lines the parser already accepted.) It
flags anything else that resembles a header by a looser pattern adapted
from the Tier-A audit's own `LOOSE` regex, widened per the public-test spec to also catch
Senator/Chair forms, a bare capitalized-surname-plus-period form, and bracketed
`[continuing]`/`[presiding]`/`[to ...]` annotations that land on their own line (the real
parsers' turn loop skips any line starting with "[" outright, so an aside placed there is
silently swallowed into whichever turn is still open -- exactly the slip shape the audit
found elsewhere, just at the open-bracket end of a line instead of baked into `LEADER`).
"""
from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup

import gpo_turns as _house
import gpo_turns_senate as _senate

# Adapted from ~/hillgenius-exports/wordgold-tier-a/out/factcheck_1013/header_scan.py's
# `LOOSE`, widened with Senator/Chair/Governor/Mayor/Judge/Professor/Ranking Member (the
# other role words `LEADER`/`SENATE_LEADER` already accept-gate) and a bare
# capitalized-surname-plus-period form (`BARE_SURNAME_HEADER` below, checked separately --
# see its own docstring for why it needs a different guard than the titled forms do).
#
# A "St." surname particle is read as part of the name, not as the header's terminal
# period (2026-10-26): without that, a paragraph-start vocative such as "Judge St. Eve,
# the Judiciary is requesting..." (CHRG-119hhrg60778, 6 lines) matched as a "Judge St."
# header, while a real "Judge St. Eve." header is still caught.
LOOSE_HEADER = re.compile(
    r"^(?:"
    r"(?:Mr|Ms|Mrs|Dr|Miss)\.?\s?(?:St\.\s)?[A-Z][^\s.]+(?:\s(?:of|de|del|Van|van|(?:St\.\s)?[A-Z][^\s.]+)){0,3}"
    r"|(?:The\s)?(?:Chairman|Chairwoman|Chair|Senator|Secretary|Commissioner|Administrator|"
    r"General|Admiral|Ambassador|Representative|Voice|Witness|Governor|Director|Clerk|"
    r"Mayor|Judge|Professor|Ranking Member)(?:\s(?:St\.\s)?[A-Z][^\s.]+){0,3}"
    r")(?<!\bSt)\.\s"
)

# A bare "Surname." header with no title at all. Unlike the titled forms above, this
# shape is indistinguishable by punctuation alone from an ordinary sentence that happens
# to start with a capitalized word (a title abbreviation whose own period is immediately
# followed by a comma-interrupted clause -- "Mr. Hasten, wonderful..." -- backtracks into
# matching bare "Mr." as if "Mr" were a surname; so does any paragraph genuinely starting
# "States.", "Loras.", a quoted name, etc.). The real parsers avoid exactly this ambiguity
# the same way `_accepts_role_candidate`'s `rank_name` case does: by requiring the
# candidate word to be a participant this hearing's own front matter already named. This
# form is checked against that same known-participant set rather than `LOOSE_HEADER`.
BARE_SURNAME_HEADER = re.compile(r"^([A-Z][a-z]+(?:-[A-Z][a-z]+)?)\.\s")

# A bracketed annotation at the START of a line -- "[continuing]", "[Presiding.]",
# "[To Mr. Smith.]" -- that the real parsers' turn loop skips outright (any line starting
# with "[" is `continue`d past without ever being tested against LEADER/SENATE_LEADER), so
# it is silently folded into whichever turn is still open.
LEADING_BRACKET_ASIDE = re.compile(
    r"^\[\s*(continuing|presiding|to\s+(?:Mr|Ms|Mrs|Dr|Senator|Sen|Chairman|Chairwoman)\b)",
    re.I,
)


def _scan_lines(body_lines, known_surnames: set[str]) -> list[dict]:
    """Walk the `(raw_line, line, header)` stream from `gpo_turns.house_body_lines()`/
    `gpo_turns_senate.senate_body_lines()` -- the parser's own per-line decision, so a
    line counts as accepted exactly when the real parser opened a turn on it -- and return
    the lines that did not open a turn but still look like a header, per `LOOSE_HEADER`,
    or carry a leading bracket aside."""
    unparsed = []
    for raw_line, line, header in body_lines:
        if not line:
            continue
        if line.startswith("["):
            if LEADING_BRACKET_ASIDE.match(line):
                unparsed.append({"line": line, "indent": len(raw_line) - len(raw_line.lstrip(" ")),
                                  "reason": "leading_bracket_aside"})
            continue
        if header is None or header:
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        # GPO's print layout only gives a true new paragraph (a real turn's first line)
        # >=4 leading spaces; a line wrapped by the print's fixed width to start with a
        # capitalized word -- "States. The book thus outlined..." mid-sentence, or a
        # quoted/mentioned name like "Mr. Trump was one of the first..." -- carries the
        # raw print's own continuation indent instead, confirmed 0 in the cases PR #402's
        # own false-positive guard (`_accepts_role_candidate`) was written against. Without
        # this same gate, `LOOSE_HEADER` (necessarily loose, since it has to catch headers
        # the real parser's own, narrower patterns miss) flags most of a hearing's body
        # text, not just its headers.
        if indent >= 4:
            if LOOSE_HEADER.match(line):
                unparsed.append({"line": line, "indent": indent, "reason": "header_like_not_accepted"})
                continue
            bm = BARE_SURNAME_HEADER.match(line)
            if bm and bm.group(1).lower() in known_surnames:
                unparsed.append({"line": line, "indent": indent, "reason": "bare_surname_not_accepted"})
    return unparsed


def _surname_set(*names_groups) -> set[str]:
    out = set()
    for names in names_groups:
        for n in names or ():
            out.add(str(n).strip().lower())
            out.add(str(n).strip().split()[-1].lower()) if str(n).strip() else None
    return {s for s in out if s}


# The known-participant names for `BARE_SURNAME_HEADER` come from the front matter
# (`raw[:start]`) only, the same slice the parsers read. Reading the whole print let a
# body line such as "Dr. Smith. No, ..." add "No" as a known name, which then flagged
# every paragraph opening "No."/"Yes."/"Okay." (2026-10-26 population scan).
def scan_house(raw: str) -> list[dict]:
    start, end = _house._find_bounds(raw)
    front = raw[:start]
    chair_surname = _house._house_chair_surname(front)
    known_names = (_house._house_front_matter_known_names(front)
                   | _house._house_witness_intro_names(front))
    roster_members = _house._house_roster_members(front)
    known_surnames = _surname_set(known_names, roster_members, [chair_surname] if chair_surname else [])
    return _scan_lines(_house.house_body_lines(raw, start, end), known_surnames)


def scan_senate(raw: str) -> list[dict]:
    start, end = _senate._find_bounds_senate(raw)
    front = raw[:start]
    known_names = _senate._front_matter_known_names(front)
    roster_chair = _senate._roster_chair_surname(front)
    known_surnames = _surname_set(known_names, [roster_chair] if roster_chair else [])
    return _scan_lines(_senate.senate_body_lines(raw, start, end), known_surnames)


def scan_print(path: Path, chrg_id: str, chamber: str | None = None) -> list[dict]:
    """Returns a list of `{"line", "indent", "reason"}` dicts for every header-like line
    the matching chamber's parser did not accept as a turn. An empty list means the
    print's header set is fully covered by the vendored parser -- the condition this
    scorer requires before it will score a hearing."""
    soup = BeautifulSoup(path.read_text(), "html.parser")
    raw = soup.get_text("\n")
    ch = chamber or _senate.chamber_of(chrg_id)
    if ch == "senate":
        return scan_senate(raw)
    if ch == "house":
        return scan_house(raw)
    raise ValueError(f"unknown chamber: {ch!r}")


def main():
    import argparse
    import json
    import sys

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--print", dest="print_path", required=True, type=Path)
    ap.add_argument("--chrg", required=True)
    ap.add_argument("--chamber", choices=["house", "senate"], default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    unparsed = scan_print(args.print_path, args.chrg, args.chamber)
    if args.out:
        args.out.write_text(json.dumps(unparsed, indent=1))
    print(f"{len(unparsed)} unparsed header-like line(s)", file=sys.stderr)
    for u in unparsed[:20]:
        print(f"  [{u['reason']}] {u['line'][:100]!r}", file=sys.stderr)
    if unparsed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
