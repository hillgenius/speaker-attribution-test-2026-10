# Published copy: database queries and internal names cut, each marked [redacted: ...]; the
# original's SHA-256 (5984775ae099476a3695e7ccd280107e58493160a0142782219524f3428c16cf) is the one in SHA256SUMS.
"""Resolve a GPO print's member-speaker surnames to bioguide ids, for `score.py`'s
bioguide-based cluster scoring (see README.md "Member scoring"/REGRESSION.md section 4).

New code, not a vendor copy (see PROVENANCE.md).

Four roster sources, tried **in this order** -- a waived-on member (sitting on a
different committee, or a different chamber entirely) should still resolve to a
bioguide id instead of falling back to surname matching, so the search keeps widening
until something matches rather than stopping at the hearing's own committee:

1. **The print's own "Members present:"/"Also present:" roster sentence**, when the
   print has one (every validated Senate print; the rare House print too, though PR #403
   found most House Appropriations prints lack it entirely). House prints spell this
   "Members present: Representatives NAME1, NAME2 of STATE, ...." with full given+surname
   names, optionally state-qualified; Senate prints spell it "Members present: Senators
   NAME1, NAME2, ... and NAMEn." with bare surnames only. Either way this is GPO's own
   enumeration of who was actually in the room for this hearing -- the most precise
   "present" signal available. Each token is resolved against the *union* of sources
   2-4 below (see `_resolve_token`), not just the committee roster, because a waived-on
   member or a visiting senator named in this sentence is never on the hearing's own
   committee roster either.
2. **The hearing's own committee *and* subcommittee membership**, combined into one
   pool (not subcommittee-preferred-over-committee as an earlier cut of this module
   did -- a full-committee member who waives on to one of its subcommittee's hearings,
   e.g. Rep. Jim Costa sitting in on a House Appropriations subcommittee hearing he
   isn't a member of, was previously decided by surname only; now the full committee's
   roster is in the same pool as the subcommittee's, so membership in *either* resolves
   the id -- see REGRESSION.md section 5 limitation 2, now fixed when the member is on
   the full committee).
3. **The full chamber's membership for that Congress** ([redacted: table name]), when the
   speaker isn't on the hearing's committee/subcommittee at all -- e.g. Rep. Jim Costa in
   `hhrg61939` (HSAP10, House Appropriations' Military Construction/VA subcommittee) sits
   on Agriculture and Foreign Affairs, not Appropriations in any form, but is still a
   119th-Congress House member and so resolves here.
4. **The other chamber's membership for that Congress** -- a `Senator NAME.` header
   appearing inside a House print (a senator testifying or waiving on) has no match in
   sources 2-3 (all House), but resolves against the Senate's own [redacted: table name] rows for
   the same Congress.

Sources 2-4 come from the HillGenius member database [redacted: query details]; `--roster-cache <dir>` caches the fetched rows for each
hearing to `<dir>/<hearing_id>.json` so a later run reads them back with no database calls
at all (the public kit's regression/demo runs are meant to work with no DB access, once
a roster has been fetched once and the cache file committed).

**Resolving one printed header (or roster-sentence token) to a bioguide id:** match its
surname (using the state qualifier when the print carries one, same as before) against
whichever source-pool is being tried. A state qualifier, when present, disambiguates
same-surname candidates outright. Without one, and when more than one candidate in that
pool shares the surname, the tie-break is: (a) prefer the candidate who is also a member
of the hearing's own committee/subcommittee (source 2), then (b) prefer the one whose
surname was itself named in the "Members present" sentence (source 1) -- in either order
these amount to "the person most clearly tied to this specific hearing wins." If neither
narrows it to exactly one candidate, the id is left unresolved (score.py falls back to
its existing surname-only match) and the collision is recorded in `Roster.roster_unresolved`
with the candidates that tied, for later inspection -- never guessed.

`score.py` only calls `Roster.resolve()` for a gold turn's surname, which falls back to
the existing surname-only match automatically whenever this module can't produce a
unique bioguide id (no candidate at all in any source, or an unresolved collision) -- see
score.py's cluster loop.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from bs4 import BeautifulSoup

from surname_match import US_STATE_ABBR, split_state_qualifier, surname_match, surname_variants

# Matches both chambers' "Members present:"/"Also present:" sentence: House prints name
# "Representatives", Senate prints name "Senators" (both optional -- a print that drops
# the role noun entirely still matches). Same split-on-comma, strip-leading-"and" shape as
# gpo_turns.py's own (House-only) `_house_roster_members`, generalized to both chambers'
# observed wording (gpo_turns.py's version is House-specific and not reused here).
_ROSTER_LINE = re.compile(
    r"(?:Members present|Also present):\s*(?:Senators?|Representatives?)?\s*(.*?)\.\s",
    re.DOTALL,
)


def run_query(query: str) -> list[dict]:
    # [redacted: database query] The scorer reads every roster from roster_cache/, so this never runs.
    raise RuntimeError("database lookup redacted in the published copy; pass --roster-cache")


def _congress_for_date(date_str: str) -> int:
    """119th Congress = 2025-2026; a new Congress every odd year. Same formula as
    [redacted: internal file]'s `congress_for_date` (not imported from
    there -- this kit is self-contained, see PROVENANCE.md -- but deliberately kept
    identical: `(year - 1789) // 2 + 1`)."""
    year = int(str(date_str)[:4])
    return (year - 1789) // 2 + 1


def _parse_roster_sentence(raw: str) -> list[str] | None:
    """Every name/surname token in the print's "Members present:"/"Also present:"
    sentence(s), or None if the print has no such sentence at all (see module
    docstring) -- `None` vs `[]` matters the same way it does in gpo_turns.py's own
    `_house_roster_members`: "no sentence found" must fall back to the committee roster
    as-is, not be treated as "a sentence was found naming zero members."""
    found = False
    names: list[str] = []
    for m in _ROSTER_LINE.finditer(raw):
        found = True
        body = re.sub(r"\s+", " ", m.group(1)).strip()
        for part in body.split(","):
            part = re.sub(r"^\s*and\s+", "", part.strip()).strip()
            if part:
                names.append(part)
    return names if found else None


def _hearing_context(hearing_id: str) -> dict:
    # [redacted: database query] The scorer reads every roster from roster_cache/, so this never runs.
    raise RuntimeError("database lookup redacted in the published copy; pass --roster-cache")


def _members_for_committee(thomas_id: str, date_only: str) -> tuple[list[dict], str]:
    # [redacted: database query] The scorer reads every roster from roster_cache/, so this never runs.
    raise RuntimeError("database lookup redacted in the published copy; pass --roster-cache")


def _committee_candidates(ctx: dict) -> tuple[list[dict], str | None]:
    """The hearing's own committee *and* subcommittee rosters, combined into one
    deduped pool (source 2 -- see module docstring; each committee's own
    spans-then-current-membership fallback is resolved independently via
    `_members_for_committee`, since one of the two tables might be backfilled for the
    subcommittee but not the full committee, or vice versa)."""
    hearing_date = ctx.get("hearing_date")
    if not hearing_date:
        return [], None
    date_only = str(hearing_date)[:10]

    thomas_ids = [t for t in (ctx.get("subcommittee_thomas_id"), ctx.get("committee_thomas_id")) if t]
    # dedupe while keeping order (subcommittee first, matching the old preference order
    # for diagnostics -- it no longer changes which candidates end up in the pool)
    seen_tids: list[str] = []
    for t in thomas_ids:
        if t not in seen_tids:
            seen_tids.append(t)
    if not seen_tids:
        return [], None

    by_id: dict[str, dict] = {}
    queries: list[str] = []
    for tid in seen_tids:
        rows, query = _members_for_committee(tid, date_only)
        queries.append(query)
        for r in rows:
            by_id.setdefault(r["bioguide_id"], r)
    return list(by_id.values()), " UNION ".join(queries)


def _chamber_candidates(chamber: str, congress: int) -> tuple[list[dict], str]:
    # [redacted: database query] The scorer reads every roster from roster_cache/, so this never runs.
    raise RuntimeError("database lookup redacted in the published copy; pass --roster-cache")


def _match_in_pool(base_surname: str, state_abbr: str | None, pool: list[dict],
                    tiebreak_sets: list[set[str]]) -> tuple[str | None, list[dict] | None]:
    """Resolve `base_surname` (+ optional state) against `pool`.

    Returns `(bioguide_id, None)` on a unique match; `(None, None)` when nothing in
    `pool` matches at all (the caller should widen to the next, broader source); or
    `(None, candidates)` when more than one candidate matches and no set in
    `tiebreak_sets` (tried in order) narrows it to exactly one -- the caller should stop
    widening and record this as an unresolved collision rather than letting a broader
    source paper over it.

    A candidate with no `cl_last` at all (a handful of [redacted: table name] rows for departed/
    vacated-seat members never got one backfilled, e.g. mid-119th-Congress deaths and
    resignations) can never surname-match anything and is skipped rather than raising.
    """
    variants = surname_variants(base_surname)
    if not variants:
        return None, None
    matches: dict[str, dict] = {}
    for c in pool:
        # allow_fuzzy=False: this is resolving a GPO print's own surname to a roster
        # bioguide id, not comparing two independent segmentations' labels -- see
        # surname_match()'s docstring and REGRESSION.md section 6. An edit-distance<=1
        # slip here ("Hasten" vs "Casten") is almost always two different people, not a
        # spelling variant, and a wrong bioguide id is worse than an unresolved one
        # (score.py falls back to the surname-only match either way).
        if not c.get("cl_last") or not surname_match(variants, c["cl_last"], allow_fuzzy=False):
            continue
        if state_abbr and c.get("state") and c["state"] != state_abbr:
            continue
        matches[c["bioguide_id"]] = c
    if not matches:
        return None, None
    if len(matches) == 1:
        return next(iter(matches)), None
    for tb in tiebreak_sets:
        narrowed = [bid for bid in matches if bid in tb]
        if len(narrowed) == 1:
            return narrowed[0], None
    return None, list(matches.values())


# ---------------------------------------------------------------------------
# Witness guard: names from the print's own witness list / "STATEMENT OF ..."
# headings never resolve to a member id, no matter how a surname otherwise matches
# the roster.
# ---------------------------------------------------------------------------

# A witness's own turn-introducing heading, in GPO's two conventions: "TESTIMONY OF
# NAME, TITLE, ORG" (House, all caps, seen wrapped across several hyphenated lines) and
# "Prepared Statement of NAME, TITLE, ORG" (both chambers, title case, reproducing a
# witness's written statement). A MEMBER's own opening-statement heading is spelled the
# same way syntactically ("OPENING STATEMENT OF HON. NAME, A REPRESENTATIVE IN CONGRESS
# FROM THE STATE OF ..., AND CHAIRMAN, ..." for the House; "STATEMENT OF SENATOR NAME"
# for the Senate) -- `_MEMBER_MARKER_RE` tells the two apart, searched anywhere in the
# heading's remainder (not just right after "OF"), since the House convention's member
# marker ("a Representative in Congress", "a U.S. Senator") comes after the member's own
# name and a comma, not before it. Only the heading's first physical line is read: GPO
# reliably puts the witness's name (and, for a single witness, their first comma) on
# that line even when the title/organization that follows wraps across several more
# lines -- reading further risks running past a missing blank-line boundary into the
# witness's own spoken/written testimony (seen on CHRG-119hhrg60878's "Prepared
# Statement of Michael Pillsbury" heading, which has no blank line before the body).
_WITNESS_HEADING_LINE_RE = re.compile(
    r"^(?:OPENING\s+)?(?:PREPARED\s+)?(?:STATEMENT|TESTIMONY)\s+OF\s+(.*)$",
    re.IGNORECASE,
)
_MEMBER_MARKER_RE = re.compile(
    r"^(?:THE\s+)?(?:SENATOR|SENATORS|REPRESENTATIVE|REPRESENTATIVES|CHAIRMAN|CHAIRWOMAN|"
    r"CHAIR\b|RANKING\s+MEMBER|VICE\s+CHAIR|VICE\s+RANKING\s+MEMBER)\b"
    r"|,\s*A\s+(?:U\.S\.\s+)?(?:SENATOR|REPRESENTATIVE)\b"
    r"|MEMBER\s+OF\s+CONGRESS",
    re.IGNORECASE,
)
_NAME_TITLE_PREFIX_RE = re.compile(
    r"^(?:THE\s+HONORABLE|HON\.?|MR\.?|MS\.?|MRS\.?|DR\.?)\s+", re.IGNORECASE,
)

# The print's own front-matter "WITNESSES" table of contents (and, separately, a
# "<bullet> Mr./Ms./.../The Honorable NAME, TITLE" witness list some House prints use
# instead) -- see module docstring's `_FRONT_MATTER_NAME`/`_WITNESS_INTRO_NAME` sibling
# functions in gpo_turns.py for the same convention read a different way. Bounded to the
# section between a bare "WITNESSES" (optionally roman-numeral-prefixed, e.g. "VII.
# WITNESSES") heading and the next all-caps section heading, so a conversational
# "Mr./Ms. NAME, ..." vocative elsewhere in the hearing body (which this same
# title+name+comma shape could otherwise match) is never in scope -- front matter never
# contains spoken dialogue.
_WITNESSES_SECTION_HEADING_RE = re.compile(r"^(?:[IVXLC]+\.\s*)?WITNESSES\s*$", re.IGNORECASE)
_TITLE_NAME_COMMA_RE = re.compile(
    r"^\s*(?:<bullet>)?\s*L?\s*(?:The\s+Honorable|Hon\.?|Mr\.?|Ms\.?|Mrs\.?|Dr\.?)\s+"
    r"([A-Z][A-Za-z.'’-]*(?:\s+[A-Z][A-Za-z.'’-]*){0,3})\s*,",
)
# Some prints letter-space a heading for visual emphasis ("W I T N E S S E S" instead of
# "WITNESSES"). Collapsed back to a normal word before matching against
# `_WITNESSES_SECTION_HEADING_RE` so this convention is recognized too.
_LETTER_SPACED_RE = re.compile(r"^(?:[A-Z]\s+){2,}[A-Z]$")
# The back-matter index some prints use instead of a bulleted witness list: one line per
# witness, "Surname, First Middle, Credential...........Page" (e.g. "Harris, Scott,
# M.D...............................................    56"), always inside the same
# WITNESSES-bounded section as the bulleted form. House Appropriations prints also use
# this same index to list a *member* who testified as a courtesy witness on their own
# district's earmark request ("Costa, Hon. Jim..................14",
# "Weber, Hon. Randy K..............1" -- both real sitting members, shipped correctly
# by their own bioguide id, the "waived on from a different committee" case the
# four-level roster widening handles) -- GPO's own "Hon." prefix is exactly how it tells
# these apart from a non-member witness's entry, which never carries a title, so an
# entry whose name portion starts with "Hon."/"The Honorable" is left out of the witness
# set entirely (it names a member, not a witness, even though it is printed in the
# WITNESSES index).
_SURNAME_PAGE_LINE_RE = re.compile(
    r"^([A-Z][A-Za-z'’-]+),\s+([A-Za-z][A-Za-z.,'’ -]*?)\.{3,}\s*\d+\s*$"
)
_HON_PREFIX_RE = re.compile(r"^(?:Hon\.?|The\s+Honorable)\b", re.IGNORECASE)


def _collapse_letter_spacing(line: str) -> str:
    return re.sub(r"\s+", "", line) if _LETTER_SPACED_RE.match(line) else line


def _is_allcaps_heading(line: str) -> bool:
    letters = re.sub(r"[^A-Za-z]", "", line)
    return len(letters) >= 10 and letters.isupper()


def _surname_from_name_text(name_text: str) -> str | None:
    name_text = _NAME_TITLE_PREFIX_RE.sub("", name_text.strip()).strip()
    toks = [t for t in name_text.split() if t]
    while len(toks) > 1 and re.match(r"^[A-Z]\.?$", toks[-1]):
        toks.pop()
    return toks[-1].strip(".,") if toks else None


def _witness_surnames_from_headings(raw: str) -> set[str]:
    names: set[str] = set()
    for line in raw.splitlines():
        m = _WITNESS_HEADING_LINE_RE.match(line.strip())
        if not m:
            continue
        remainder = m.group(1)
        if _MEMBER_MARKER_RE.search(remainder):
            continue
        for clause in remainder.split(";"):
            clause = clause.strip().rstrip(",")
            clause = re.sub(r"^(?:AND)\s+", "", clause, flags=re.IGNORECASE)
            surname = _surname_from_name_text(clause.split(",")[0])
            if surname:
                names.add(surname)
    return names


def _witness_surnames_from_section(raw: str) -> set[str]:
    names: set[str] = set()
    in_section = False
    collected = 0
    for line in raw.splitlines():
        stripped = line.strip()
        if not in_section:
            if _WITNESSES_SECTION_HEADING_RE.match(_collapse_letter_spacing(stripped)):
                in_section, collected = True, 0
            continue
        if not stripped:
            continue
        m = _TITLE_NAME_COMMA_RE.match(line)
        if m:
            surname = _surname_from_name_text(m.group(1))
            if surname:
                names.add(surname)
                collected += 1
            continue
        m = _SURNAME_PAGE_LINE_RE.match(stripped)
        if m:
            if not _HON_PREFIX_RE.match(m.group(2).strip()):
                names.add(m.group(1).strip(".,"))
            collected += 1
            continue
        if _is_allcaps_heading(stripped):
            in_section = False
            continue
        if collected >= 20:
            in_section = False
    return names


def print_witness_surnames(raw: str) -> set[str]:
    """Every surname the print's own witness list / "STATEMENT OF ..." headings name, as
    bare surname strings (not yet expanded to `surname_variants()` -- the caller does
    that, same as everywhere else a surname gets compared). Deliberately a bit noisy on
    the over-inclusive side (page-footer artifacts, a submitted-statement-for-the-record
    author who never spoke live) rather than under-inclusive: the cost of wrongly
    skipping a bioguide match for a name that was never actually a member is zero
    (`score.py` already falls back to the surname-only match whenever the bioguide path
    comes back empty), while the cost of the bug this guards against -- resolving a
    witness's surname to a sitting member's bioguide id -- is a wrong answer reported as
    fact. See REGRESSION.md section 6 (the Hasten/Casten case)."""
    return _witness_surnames_from_headings(raw) | _witness_surnames_from_section(raw)


def _resolve_token(token: str, pools: list[list[dict]], committee_ids: set[str]) -> str | None:
    """bioguide id for one "Members present" token, searched against `pools` (sources
    2-4, in order) with the committee-membership tie-break -- see module docstring. A
    token that matches no candidate anywhere, or that stays ambiguous in whichever pool
    first produced a match, resolves to None (recorded by the caller in
    `Roster.unresolved_sentence_tokens`)."""
    base, state_full = split_state_qualifier(token)
    state_abbr = US_STATE_ABBR.get(state_full.lower()) if state_full else None
    for pool in pools:
        if not pool:
            continue
        bioguide, ambiguous = _match_in_pool(base, state_abbr, pool, [committee_ids])
        if bioguide is not None or ambiguous is not None:
            return bioguide
    return None


@dataclass
class Roster:
    committee_candidates: list[dict]
    chamber_candidates: list[dict]
    other_chamber_candidates: list[dict]
    present_bioguides: set[str] | None  # None => no "Members present" sentence at all
    source: str  # "members_present_sentence" | "committee_membership" | "none"
    unresolved_sentence_tokens: list[str]
    committee_query: str | None
    roster_unresolved: list[dict] = field(default_factory=list)
    witness_variants: frozenset[str] = field(default_factory=frozenset)

    @property
    def committee_ids(self) -> set[str]:
        return {c["bioguide_id"] for c in self.committee_candidates}

    @property
    def candidates(self) -> list[dict]:
        """All distinct candidates across every source, for diagnostics (e.g. a
        candidate count in score.py's stderr summary)."""
        by_id: dict[str, dict] = {}
        for pool in (self.committee_candidates, self.chamber_candidates, self.other_chamber_candidates):
            for c in pool:
                by_id.setdefault(c["bioguide_id"], c)
        return list(by_id.values())

    def resolve(self, base_surname: str, state_abbr: str | None) -> str | None:
        """bioguide id for a gold turn's base surname (already split from any state
        qualifier -- see surname_match.split_state_qualifier), searched against sources
        1-4 in order (see module docstring). Widens to the next source only when the
        current one has zero matching candidates; an ambiguous match in whichever
        source first produces one is recorded in `roster_unresolved` and resolves to
        None (score.py falls back to the surname-only match either way).

        A surname the print's own witness list / "STATEMENT OF ..." headings name (see
        `print_witness_surnames`) never resolves to a member id here, full stop -- not
        even when it happens to also match a roster candidate by surname (the
        Hasten/Casten case this guard exists for is exactly that: a witness surname that
        collided with a sitting member's by spelling). Checked before any source is
        consulted, so it can't be bypassed by widening to a broader pool."""
        if self.witness_variants and surname_variants(base_surname) & self.witness_variants:
            return None
        present_ids = self.present_bioguides or set()
        tiebreak_sets = [self.committee_ids, present_ids]

        pools: list[tuple[str, list[dict]]] = []
        if self.present_bioguides is not None:
            present_pool = [c for c in self.candidates if c["bioguide_id"] in self.present_bioguides]
            pools.append(("members_present_sentence", present_pool))
        pools.append(("committee_membership", self.committee_candidates))
        pools.append(("chamber_membership", self.chamber_candidates))
        pools.append(("other_chamber_membership", self.other_chamber_candidates))

        for level, pool in pools:
            if not pool:
                continue
            bioguide, ambiguous = _match_in_pool(base_surname, state_abbr, pool, tiebreak_sets)
            if bioguide:
                return bioguide
            if ambiguous is not None:
                self.roster_unresolved.append({
                    "surname": base_surname, "state": state_abbr, "level": level,
                    "candidates": [{"bioguide_id": c["bioguide_id"], "name": c.get("name"),
                                     "state": c.get("state")} for c in ambiguous],
                })
                return None
        return None


def _roster_cache_path(roster_cache_dir: Path, hearing_id: str) -> Path:
    return roster_cache_dir / f"{hearing_id}.json"


def _fetch_roster_data(hearing_id: str) -> dict:
    """Every database-backed input `build_roster` needs, fetched fresh (see module
    docstring sources 2-4) and shaped for `--roster-cache` round-tripping."""
    ctx = _hearing_context(hearing_id)
    committee_candidates, committee_query = _committee_candidates(ctx)

    chamber = ctx.get("chamber")
    hearing_date = ctx.get("hearing_date")
    congress = _congress_for_date(hearing_date) if hearing_date else None

    chamber_candidates: list[dict] = []
    other_chamber_candidates: list[dict] = []
    chamber_query = other_chamber_query = None
    if congress and chamber in ("House", "Senate"):
        chamber_candidates, chamber_query = _chamber_candidates(chamber, congress)
        other = "Senate" if chamber == "House" else "House"
        other_chamber_candidates, other_chamber_query = _chamber_candidates(other, congress)
    elif congress and chamber == "Joint":
        # No single "own"/"other" chamber for a joint committee -- source 3 becomes both
        # chambers' membership together, and there is no source 4 (see module docstring).
        house_rows, house_query = _chamber_candidates("House", congress)
        senate_rows, senate_query = _chamber_candidates("Senate", congress)
        chamber_candidates = house_rows + senate_rows
        chamber_query = f"{house_query} UNION {senate_query}"

    return {
        "hearing_id": hearing_id,
        "congress": congress,
        "chamber": chamber,
        "committee_candidates": committee_candidates,
        "committee_query": committee_query,
        "chamber_candidates": chamber_candidates,
        "chamber_query": chamber_query,
        "other_chamber_candidates": other_chamber_candidates,
        "other_chamber_query": other_chamber_query,
    }


def build_roster(print_path: Path, hearing_id: str, roster_cache_dir: Path | None = None) -> Roster:
    """Builds the hearing's member roster (see module docstring). Never raises for an
    ordinary "nothing to resolve" case (no committee row, no roster sentence, no database
    rows) -- those come back as an empty/no-op Roster whose `resolve()` always returns
    None, same as if this module had never run. A real database failure (timeout, auth)
    propagates; score.py decides whether to treat that as fatal or fall back silently.

    `roster_cache_dir`, when given, makes sources 2-4 (everything backed by database)
    read/write a `<hearing_id>.json` file in that directory instead of always querying
    the database: a cache hit skips every database call (fully offline -- the print is still
    parsed locally for its roster sentence, same as always); a cache miss fetches fresh
    and writes the file for next time. Commit the cache directory to let the public kit's
    regression/demo runs work with no DB access at all.
    """
    cache_path = _roster_cache_path(roster_cache_dir, hearing_id) if roster_cache_dir else None
    if cache_path and cache_path.exists():
        data = json.loads(cache_path.read_text())
    else:
        data = _fetch_roster_data(hearing_id)
        if cache_path:
            roster_cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(data, indent=1, default=str))

    committee_candidates = data["committee_candidates"]
    chamber_candidates = data["chamber_candidates"]
    other_chamber_candidates = data["other_chamber_candidates"]
    committee_query = data.get("committee_query")

    raw = BeautifulSoup(print_path.read_text(), "html.parser").get_text("\n")
    tokens = _parse_roster_sentence(raw)

    witness_variants: frozenset[str] = frozenset(
        v for surname in print_witness_surnames(raw) for v in surname_variants(surname)
    )

    any_candidates = bool(committee_candidates or chamber_candidates or other_chamber_candidates)
    if tokens is None or not any_candidates:
        source = "committee_membership" if any_candidates else "none"
        return Roster(committee_candidates, chamber_candidates, other_chamber_candidates,
                      None, source, [], committee_query, witness_variants=witness_variants)

    committee_ids = {c["bioguide_id"] for c in committee_candidates}
    search_pools = [committee_candidates, chamber_candidates, other_chamber_candidates]
    present: set[str] = set()
    unresolved: list[str] = []
    for tok in tokens:
        bioguide = _resolve_token(tok, search_pools, committee_ids)
        if bioguide:
            present.add(bioguide)
        else:
            unresolved.append(tok)
    return Roster(committee_candidates, chamber_candidates, other_chamber_candidates,
                  present, "members_present_sentence", unresolved, committee_query,
                  witness_variants=witness_variants)
