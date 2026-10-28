"""Senate-print companion to `gpo_turns.py`.

`gpo_turns.py`'s `LEADER` pattern and `gpo_turns()`/`build_ref_turn_index()`
parse the House convention -- "Mr./Ms./Mrs./Dr. NAME." witness/member turns,
plus a bare "All." for unison responses. Senate committee prints ("shrg"
packages) use a different, chamber-specific header convention that a naive
widening of `LEADER` cannot cover: widening it to also match "Senator NAME."
on CHRG-119hhrg58876 (a House print) moved that hearing from 360 to 361 turns
and, on a Senate print, resolved the whole hearing into only 2 speakers (the
committee's own roster block false-matches the widened pattern, and the House
witness-title alternative silently absorbs Senate honorifics it wasn't built
for). That approach was rejected.

This module is purely additive: it does not import `gpo_turns.LEADER`, does
not modify any `gpo_turns` module attribute, and every function here is new.
The House path (`gpo_turns.gpo_turns`, `.build_ref_turn_index`, `.LEADER`,
`._find_bounds`) is untouched by importing or using this module -- see
`tests/test_gpo_turns_senate.py`'s `test_house_path_byte_identical`, which
diffs the House parser's output on all four validated hearings against a
subprocess baseline that never imports this file.

CHAMBER DETECTION
------------------
`chamber_of(chrg_id)` reads "hhrg" vs. "shrg" out of the GPO package id
(e.g. "CHRG-119shrg61334" -> "senate", "CHRG-119hhrg58876" -> "house").
`build_ref_turn_index_auto()` uses it to dispatch to this module or to
`gpo_turns` unchanged; callers who already know the chamber can call
`gpo_turns_senate()` / `build_ref_turn_index_senate()` directly, or pass
`chamber=` explicitly to override detection.

HEADERS THIS PARSER HANDLES
-----------------------------
Validated against CHRG-119shrg61334 ("Safety First: Restoring Boeing's
Status", Senate Commerce, all-bare-role convention) and CHRG-119shrg60080
("Legislative Hearing to Review S. 222, The Whole Milk for Healthy Kids Act",
Senate Agriculture, all-named convention):

  Senator NAME.            rank-and-file senator, own turn. NAME may be two
                            capitalized words ("Blunt Rochester", "Moore
                            Capito") -- the House LEADER's witness alternative
                            deliberately stays single-word (see below), but
                            real Senate surnames are not.
  Chairman NAME.           the committee chair, named (e.g. "Chairman
                            Boozman."), and its bare-role counterpart:
  The Chairman.            the committee chair, with NO name in the header --
                            resolved from presiding-officer state, see below.
  Chairwoman NAME. / The Chairwoman.   same pair, female chair.
  The Chair.               same bare-role form, for a committee whose GPO
                            convention uses the bare word "Chair" rather than
                            "Chairman"/"Chairwoman" (added 2026-10-18;
                            CHRG-119shrg59473, Senate Small Business, roster
                            line "JONI ERNST, Iowa, Chair" -- see
                            `_ROSTER_CHAIR` and `_verify_roster_chair_surname`
                            below for the matching roster/corroboration
                            widening this form also needed). Resolved the
                            same way as "The Chairman."/"The Chairwoman.".
  Chair NAME. / Chair.     the same "Chair" convention, named ("Chair
                            Blackburn.", CHRG-119shrg61893; "Chair Cornyn.",
                            62971; "Chair Hawley.", 61837) or with no article
                            at all ("Chair.", CHRG-119shrg60614, roster line
                            "JONI ERNST, Iowa, Chair"). Added 2026-10-26 after
                            the population header scan; a named "Chair NAME."
                            sets the presiding chair like "Chairman NAME.",
                            and bare "Chair." resolves like "The Chair.". Both
                            require a paragraph-start indent, since a wrapped
                            "Madam\\nChair. Thank you..." line starts the same
                            way at indent 0.
  Ranking Member NAME.     the ranking minority member, named.
  Mr./Ms./Mrs./Dr. NAME.   witness, byte-identical alternative to the House
                            LEADER's post-PR#295 form (`\\.\\s?` for GPO's
                            occasional missing space, `+` so a lone middle
                            initial read aloud in a witness list -- "Mr. J.
                            Alfredo Gomez" -- does not open a spurious
                            single-letter turn). Deliberately single-word,
                            matching the House convention exactly, since nothing
                            in either validated Senate print needed more and
                            this is the one alternative directly modeled on
                            House witness turns.
  All.                     unison response, same as House.

  Any of the above may carry a trailing "[Presiding.]" annotation right after
  the header's period (seen in CHRG-119shrg60080: "Senator Klobuchar.
  [Presiding.] Senator Bennet.") -- GPO's own note that this speaker just
  took the gavel. It is stripped from the turn text. It does NOT feed the
  presiding-officer resolution below: that print never uses a bare "The
  Chairman."/"The Chairwoman." at all (the chair is always named), so
  "[Presiding.]" is not exercised as a resolution signal by either validated
  print; treating it as one is more machinery than the evidence supports, so
  it isn't wired up.

PRESIDING-OFFICER RESOLUTION for bare "The Chairman." / "The Chairwoman."
---------------------------------------------------------------------------
CHRG-119shrg61334 (Boeing) is the print this matters for -- every one of its
chair turns is captioned "The Chairman.", never "Chairman Cruz.". Verified
against the actual print, not assumed:

  - Sen. Moran recognizes Sen. Lujan and later opens a second round
    ("Senator Moran. Senator Lujan is recognized." / "...Senator Markey."),
    and Sen. Schmitt jokes "I will now call on myself" -- both of them
    conducting the questioning order the chair normally would -- but BOTH
    keep their own "Senator NAME." caption throughout. Neither is ever
    captioned "The Chairman.".
  - Every bare "The Chairman." in the print, before AND after those stretches
    (17 occurrences total), addresses the witness or recognizes the next
    senator in a way consistent with a single person holding the gavel
    start to finish: Sen. Cruz, the committee's actual chairman per the
    roster block. There is no GPO-captioned gavel pass in this print at all,
    despite other senators visibly running parts of the queue.

So resolution is deliberately narrow -- it does NOT move on "whoever spoke
last" or "whoever was just thanked" (both misfire on the Moran/Schmitt
stretches above). A bare "The Chairman."/"The Chairwoman." resolves to:

  1. whichever senator this SAME print most recently captioned with a NAMED
     "Chairman NAME."/"Chairwoman NAME." header -- a real, explicit title
     holder, updated live if a print ever names a new one mid-hearing
     (e.g. a chair stepping down and a successor taking the gavel by name);
     else
  2. the surname parsed off the committee roster block at the top of the
     print (the "NAME, State, Chairman" / "..., Chairwoman" line) -- which is
     where CHRG-119shrg61334 gets Cruz, since that print never uses the named
     body form at all.

Multi-word surnames in the roster line ("SHELLEY MOORE CAPITO, West
Virginia, Chairman") are reduced to their last capitalized word ("Capito"),
matching how GPO's own body text actually captions that senator elsewhere
(checked against CHRG-119shrg62718, EPW, where "SHELLEY MOORE CAPITO" is
captioned "Senator Capito." throughout) -- not verified against a case that
needed the roster fallback AND had a multi-word chair surname; flagged as a
limitation below.

KNOWN LIMITATIONS
--------------------
- Witness titles outside Mr./Ms./Mrs./Dr. (e.g. "Secretary NAME." for a
  Cabinet witness, seen in CHRG-119shrg62718) are not matched -- those lines
  fall through to the un-matched branch and are appended to the prior turn,
  same failure mode `gpo_turns.py` already has for any header shape it
  doesn't recognize.
- A bare "The Ranking Member." (no name) is not handled -- only the named
  "Ranking Member NAME." form. Neither validated print uses the bare form;
  add it the same way as the bare Chairman/Chairwoman forms if a print needs
  it.
- The roster-line chair fallback's "last capitalized word" surname heuristic
  is unverified on a print that (a) has no named "Chairman NAME." anywhere in
  the body, forcing the fallback, AND (b) has a multi-word chair surname.
  CHRG-119shrg61334 exercises (a) with a single-word surname (Cruz).
- Written "Prepared Statement of ..." reproductions after a
  "[The prepared statement of Mr./Ms. X follows:]" marker are appended to the
  witness's preceding spoken turn, duplicating content already in that turn's
  text -- this is the same behavior `gpo_turns.py` already has for House
  prints (neither module special-cases it); flagged here only because Senate
  witness statements are typically longer.
- `_front_matter_known_names` reads GPO's surname-first "Surname, Title
  First..." front-matter convention AND, since 2026-10-18, the
  title-prefix-first convention ("Chief Will Johnson, Chief Special Agent,
  ...", CHRG-119shrg61246) -- see "TITLE-FIRST FRONT-MATTER WITNESS NAMES"
  below. A convention this module's own title vocabulary (Mr./Ms./Mrs./Dr./
  Hon./The Honorable/`_TITLED_TITLE`) can't anchor on at all -- e.g. a bare
  "Given Surname, role" with no title prefix whatsoever, seen in the same
  print for "Robert Howell, Chief Supply Chain Officer, ..." -- still isn't
  read; not fixed here because Howell's own turn header ("Mr. Howell.")
  matches the unconditional `witness_name` alternative and never needed
  `known_names` in the first place. Add an unanchored fallback the same way
  if a pilot print ever needs a `titled_title` header for a witness whose
  front-matter line carries no recognizable title prefix at all.

RANK/CABINET-TITLE WITNESS HEADERS, added 2026-09-26
------------------------------------------------------
The "Witness titles outside Mr./Ms./Mrs./Dr." limitation above is exactly
what blocked CHRG-119shrg63038 (Gen. Dan Caine's nomination hearing): 428
occurrences of the line-start header "Lieutenant General Caine." (plus 1
"General Caine.") were unrecognized, so the nominee -- the single most
important speaker in the hearing -- never appeared in the parsed roster at
all. `titled_title`/`titled_name` covers this: Lieutenant General, General,
Secretary, Admiral, each followed by a single-word surname in the same shape
as the `witness_name` alternative above (Mr./Ms./Mrs./Dr. already covers the
"Dr. NAME." case for a witness with that title).

Same false-positive risk as the House Chairman/Chairwoman fix in
`gpo_turns.py` (see that module's LEADER comment for the full writeup), in
this chamber's own already-parsed pilot data: CHRG-119shrg62718 contains
"Secretary Duffy. It is good to have you here.", which is Senator Whitehouse
addressing the actual Secretary Duffy (a real, front-matter-listed witness in
that same print) mid-turn, line-wrapped to land as the first token on its own
physical line. Because Duffy IS a legitimate witness, corroborating against
the front-matter witness/member index alone is not enough to reject this
line -- only the paragraph-start check does (that line carries 0 leading
spaces in the raw print; every real "Lieutenant General Caine." turn carries
4). `_accepts_titled_candidate` requires BOTH:

  1. paragraph start -- >=4 leading spaces on the line's ORIGINAL, unstripped
     text (GPO's print-layout paragraph indent; a line-wrapped continuation
     carries none); and
  2. known participant -- the surname is one the print's own front-matter
     index lists (`_front_matter_known_names`: GPO's "Surname, Title
     First..." convention in the Member/Witness Statements table of
     contents), or was already established as a speaker earlier in this same
     parse.

Checked against the two already-shipped Senate gold prints
(CHRG-119shrg61334 "Boeing", CHRG-119shrg60080 "Whole Milk"): neither contains
any Lieutenant General/General/Secretary/Admiral header at all, so this
addition is a no-op on both -- see
test_gpo_turns_chair_and_titled_witness.py.

CIVIL-HONORIFIC WITNESS HEADERS and PRESIDING/CONTINUING BRACKET
ANNOTATION, added 2026-09-27
--------------------------------------------------------------------
Word-aligning cluster text against gold for CHRG-119shrg61324 (Senate
Judiciary) found two more gaps:

  1. `Representative NAME.` / `Professor NAME.` -- witnesses Brandon Guffey
     (a South Carolina state representative) and Mary Graw Leary (a law
     professor) were captioned "Representative Guffey."/"Professor Leary."
     throughout, never "Mr./Ms. NAME." -- neither had ANY speaker in gold
     despite testifying at length. `_TITLED_TITLE` widened to add
     Representative/Professor alongside the existing rank/cabinet titles,
     same guard (paragraph-start indent + front-matter known-participant,
     via the print's own surname-first "Guffey, Hon. Brandon...."/"Leary,
     Mary Graw...." table-of-contents lines -- already read by
     `_front_matter_known_names`, no new source needed here).

  2. `NAME [presiding].` / `NAME [continuing].` -- the SAME print also has a
     real, previously-unhandled gavel hand-off: "Senator Moody. ... I will
     turn it over to Senator Whitehouse." / "Senator Whitehouse
     [presiding]. Thank you...." -- no alternative allowed anything between
     the surname and its terminal period, so this line fell through
     unmatched and Whitehouse's answer folded into Moody's still-open turn.
     Checking the rest of this print (and the other two already-parsed
     Senate prints) for the same construct once it was found once: it is
     pervasive here -- ~30 more "[continuing]"/"[presiding]" headers across
     Senator/witness/Chairman turns in this one print alone (a speaker
     resuming after a one-line interjection, or taking the gavel) -- and it
     ALSO already appears, unhandled, in the already-shipped CHRG-119shrg60080
     "Whole Milk" print ("Mr. Gorman [continuing]. Red tape. We are able to
     focus on...", picking his sentence back up after Sen. Klobuchar
     supplies the word "Red tape." as an aside) -- silently misattributing
     Gorman's continued words to Klobuchar's still-open turn there.
     `HEADER_TAG_SUFFIX` (defined in `gpo_turns.py`, imported here read-only
     -- same reuse pattern as `ADJOURN_BRACKET`) replaces every
     alternative's bare period-then-whitespace terminator; every one of its three groups
     is optional, so it is a no-op wherever no annotation is present, and it
     only moves previously-mis-split words back onto their real,
     already-established speaker -- it never introduces a new one. See
     test_gpo_turns_senate_civil_titles_and_tags.py.

STATE-QUALIFIED SENATOR SURNAME, added 2026-10-16
----------------------------------------------------
The WRONG-TURN audit (`~/hillgenius-exports/wordgold-tier-a/out/
factcheck_1013/WRONG-TURN-AUDIT.md`) and `score_methods_batch6_shipped.py`'s
GOLD_WRONG_CLUSTERS found the Senate convention uses the same " of STATE"
disambiguation House prints do, unhandled here: "Senator Curtis. Thank
you. I'd like to yield the Senator from Florida for 5 minutes. Senator
Scott of Florida. Thank you, Chairman...." -- the old `senator` alternative
had no room for anything after the surname and its period, so the whole
~44s, 172-word statement folded into the preceding "Curtis" turn. Same
real-world motivation as the House fix in `gpo_turns.py` (two sitting
Senators can share a surname -- Rick Scott, FL and Tim Scott, SC), and the
same resolution shape: `senator_state` is an additive optional group (a
no-op wherever absent), and the resolved speaker keeps the qualifier
("Scott of Florida") rather than dropping it, so two same-surname Senators
in one print are never merged into one speaker. Unlike the House fix's
multi-token/state-qualified `member_name`, this is not gated behind a
roster-corroboration check: the plain `Senator NAME.` alternative already
accepts unconditionally (see `_accepts_titled_candidate`, which only
guards `titled_name`), and the `of STATE` suffix only narrows what can
match, it never widens the risk of a false positive beyond what the
unguarded plain form already carries.

TITLE-FIRST FRONT-MATTER WITNESS NAMES, added 2026-10-18
------------------------------------------------------------
The KNOWN LIMITATIONS entry above (present since the 2026-10-18 rank/
office-title widening, commit `bc70df60`) is fixed here: CHRG-119shrg61246
(Senate Commerce, Surface Transportation Subcommittee, "Grand Theft Cargo")
lists its first witness "Chief Will Johnson, Chief Special Agent, BNSF
Railway Police Department, Second Vice President, International
Association of Chiefs of Police" -- title, given name, surname, then the
role clause -- never "Johnson, Chief Will, ..." the way `_FRONT_MATTER_NAME`
expects. `known_names` never contained "Johnson", so every one of this
witness's "Chief Johnson." turn headers in the body (his entire opening
statement plus Q&A) failed `_accepts_titled_candidate`'s known-participant
check and folded into whichever turn was still open -- verified against the
unfixed parser: `gpo_turns_senate(path)` on this print returns 7 speakers
(Blanchard, Fischer, Howell, Lujan, Peters, Pugh, Young) and Johnson is not
among them despite being the hearing's primary nominal witness.

`_title_first_surname` is a second, additive read of the same front-matter
block `_front_matter_known_names` already scans (purely additive -- the
surname-first branch via `_FRONT_MATTER_NAME` is untouched; a line tries
that regex first and only falls through to the title-first reader on no
match). It anchors on the SAME title vocabulary `SENATE_LEADER` itself
already accepts as a witness turn header -- Mr./Ms./Mrs./Dr. (`witness_name`),
Hon./The Honorable (the front matter's own honorific for a Cabinet witness
later captioned via a `_TITLED_TITLE` word -- e.g. CHRG-119shrg60722 lists
"Hon. Kristi Noem, Secretary, U.S. Department of Homeland Security" and
captions her "Secretary Noem." in the body), and every `_TITLED_TITLE`
rank/office word -- so it can never recognize a title this module's own
header pattern wouldn't also accept as a real turn opener. The surname is
the last capitalized token before the line's first comma (or end of line),
with a trailing generational suffix ("Jr."/"Sr."/"II"/"III"/"IV"/"V") or
post-nominal ("USN"/"USA"/"USAF"/"USMC"/"Ph.D."/"M.D."/"Esq.") discarded
first -- same shape as the suffix handling `_FRONT_MATTER_NAME` already does
for the surname-first form, so a suffixed title-first witness ("Chief
Robert Olivarez Jr., National Commander, ...") still resolves to "Olivarez"
rather than "Jr.".

Surveyed across all 104 cached Senate prints
(`~/hillgenius-exports/wordgold-tier-a/cache/pilots/gpo/CHRG-*shrg*.htm`):
75 have a "Witnesses" front-matter heading at all; of those, 58 use only the
surname-first convention, 16 use both (surname-first for members, title-first
for one or more witnesses), and 1 (CHRG-119shrg61426) uses title-first
exclusively.

Re-running `gpo_turns_senate()` over all 104 prints before/after this fix
(same `speakers`/`n_turns` comparison, not just a front-matter dry run)
found it is NOT a single-print fix: two more real witnesses this guard was
already silently dropping also start resolving, both verified against the
actual print body:

  - CHRG-119shrg60722 (Noem confirmation hearing): "Hon. Kristi Noem,
    Secretary, U.S. Department of Homeland Security" -- captioned
    "Secretary Noem." dozens of times in the body (165 extra turns:
    204 -> 369 once her turns stop folding into whoever spoke before her).
  - CHRG-119shrg61202: "Rear Admiral Adam Chamie, Assistant Commandant for
    Response Policy, U.S. Coast Guard" -- captioned "Rear Admiral Chamie."
    (169 -> 180 turns).

Both are front-matter title-first witnesses whose `_TITLED_TITLE` body
header (Secretary / Rear Admiral) was already accepted by the 2026-09-26/
2026-10-18 rank-title widenings but was blocked by this exact
known-participant gap -- the same bug class as Johnson, just not yet
noticed because neither witness's name happened to collide with another
speaker's still-open turn in a way that was audited before now. No other
print's speaker set or turn count changed: 100 of the remaining 101 prints
are byte-identical before/after (Johnson's own shrg61246 plus the Noem/
Chamie prints above are the only 3 diffs across all 104), and the last one
raises the same pre-existing, unrelated error in both old and new code.
See `test_gpo_turns_front_matter_title_first.py`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_wer_pilot_scripts = str(Path(__file__).resolve().parent.parent.parent / "wer_pilot" / "scripts")
if _wer_pilot_scripts not in sys.path:
    sys.path.append(_wer_pilot_scripts)
from bs4 import BeautifulSoup  # noqa: E402
from score_one import normalize  # noqa: E402

from gpo_turns import ADJOURN_BRACKET, GPOBodyNotFound, HEADER_TAG, _find_adjourn_end  # noqa: E402 -- read-only reuse

# A Senate surname may be one capitalized word ("Cruz", "Boozman") or two
# ("Blunt Rochester", "Moore Capito", "Van Hollen" if it ever comes up).
_SURNAME = r"[A-Z][A-Za-z'’-]+(?:\s[A-Z][A-Za-z'’-]+)?"

# Witness alternative kept deliberately single-word, byte-identical in shape
# to the post-PR#295 House LEADER (`\.\s?` optional space, `+` >=2 letters) --
# and now to the House gpo_turns.LEADER fix that closed two phantom-speaker
# holes found by auditing the frozen House gold set:
#
#   negative lookahead for role words -- "Mr. Chairman." must not mint a
#   witness named "Chairman" (this is exactly how role_named/senator/bare_role
#   above are meant to be reached instead); Chairman/Chairwoman/Chair/Speaker
#   are excluded, "Ranking Member" is two words and can never match this
#   single-token capture group regardless.
#
#   stop the surname at a double hyphen -- "Mr. Schmidt--Dr. Schmidt" must not
#   let the class bridge an em/en-dash self-correction into the next
#   honorific. `(?:[A-Za-z'’]|-(?!-))+` still allows one hyphen for a real
#   hyphenated surname.
#
# See gpo_turns.py's LEADER comment for the full House incident writeup.
#
# Leading `[A-Za-z]` (not `[A-Z]`), widened 2026-10-16 after the RESIDUAL-31
# classification (`~/hillgenius-exports/wordgold-tier-a/out_parserfix_1016/
# residual31/RESIDUAL-31-CLASSIFICATION.md`, form #5) found a lowercase-
# initial apostrophized witness surname this anchor rejected outright:
# CHRG-119shrg60612 captions "Mr. d'Arbeloff." throughout -- the leading
# `[A-Z]` anchor can never match a name starting with lowercase "d", so this
# witness's entire 2,387-word opening statement + Q&A never opened its own
# turn at all. Low-risk: a bare lowercase word still can't satisfy the
# required `(?:Mr|Ms|Mrs|Dr)\.` title prefix immediately before it, so this
# only widens what can match AFTER a real title, not what can start a line
# on its own.
_WITNESS_SURNAME = r"[A-Za-z](?:[A-Za-z'’]|-(?!-))+"

# Rank/cabinet-title witness header (see module docstring's "RANK/CABINET-
# TITLE WITNESS HEADERS" section for the false-positive guard this needs).
# Widened 2026-09-27 (see "CIVIL-HONORIFIC WITNESS HEADERS" in the module
# docstring) to also cover Representative/Professor witnesses.
#
# Widened again 2026-10-18 after the House sibling (`gpo_turns.LEADER`'s
# `rank_title`) picked up the same gap on the speaker-public-test smoke
# rerun (see that module's comment above `LEADER` for the full writeup).
# This module was missing EVEN MORE of the standard rank/office titles than
# the pre-fix House list -- it didn't have Governor, Mayor, Ambassador,
# Judge, Commissioner, Director, Administrator, or Colonel at all, despite
# all being real, paragraph-start Senate witness headers in the cached
# corpus: "Governor Inslee." (CHRG-119shrg58506), "Governor Gordon."
# (CHRG-119shrg62698), "Governor Armstrong." (CHRG-119shrg62925), "Mayor
# Gallego." (CHRG-119shrg62925), "Ambassador Gavin." (CHRG-119shrg60820),
# "Colonel Gabbard." (CHRG-119shrg58632), "Colonel Cannon."
# (CHRG-119shrg60344), "Sheriff Barnes." (CHRG-119shrg61321), "Vice Admiral Downey."
# (CHRG-119shrg61561), "Vice Admiral Bradley." (CHRG-119shrg63382, which
# ALSO captions the same witness "Admiral Bradley." elsewhere in the same
# print -- both forms must resolve), "Rear Admiral Chamie."
# (CHRG-119shrg61202), and "Major General Friedrichs." (CHRG-119shrg60344).
# Same guard as every existing `titled_title` entry (`_accepts_titled_candidate`:
# paragraph-start indent + front-matter known-participant) -- unchanged in
# shape, only the alternation widened.
_TITLED_TITLE = (
    r"(?:Lieutenant General|Vice Admiral|Rear Admiral|Major General"
    r"|Brigadier General|Sergeant Major|General|Admiral|Colonel|Captain"
    r"|Commander|Chief|Secretary|Governor|Mayor|Ambassador|Judge"
    r"|Commissioner|Director|Administrator|Superintendent|Sheriff|Reverend"
    r"|Representative|Professor)"
)

SENATE_LEADER = re.compile(
    r"^(?:"
    rf"(?P<role_named>Chairman|Chairwoman|Chair|Ranking Member)\s+(?P<role_name>{_SURNAME})"
    + HEADER_TAG +
    rf"|(?P<senator>Senator)\s+(?P<senator_name>{_SURNAME})"
    rf"(?:\s+of\s+(?P<senator_state>{_SURNAME}))?"
    + HEADER_TAG +
    rf"|(?:Mr|Ms|Mrs|Dr)\.\s?(?!(?:Chairman|Chairwoman|Chair|Speaker)\.)(?P<witness_name>{_WITNESS_SURNAME})"
    + HEADER_TAG +
    rf"|(?P<titled_title>{_TITLED_TITLE})\s+(?P<titled_name>{_WITNESS_SURNAME})"
    + HEADER_TAG +
    r"|(?P<bare_role>The Chairman|The Chairwoman|The Chair|Chair)"
    + HEADER_TAG +
    r"|(?P<all>All)"
    + HEADER_TAG +
    r")\s+"
)

# The committee roster line at the top of every Senate print, e.g.
# "TED CRUZ, Texas, Chairman" or "JOHN BOOZMAN, Arkansas, Chairman". Matched
# per stripped line (not with re.MULTILINE's `^`/`$` against the raw text),
# because GPO pads these lines with leading spaces for print layout.
#
# Widened 2026-09-26: the Plan-300 backlog-sweep prebuild found this regex
# matched nothing at all on three HELP Committee prints
# (CHRG-119shrg{60604,59492,59493}), all captioned "UNKNOWN_CHAIR" wherever
# the body used a bare "The Chairman." -- verified against the actual
# prints, the roster line there is
#   "BILL CASSIDY, M.D., Louisiana, Chairman"
# which carries an extra comma-separated credential segment ("M.D.")
# between the name and the state that the old pattern's single
# `[A-Za-z .]+,` middle group has no room for (same class of format variant
# as the credentialed-witness-roster fix in 6dcd8273). Changing that group
# from exactly-one to one-or-more repetitions accepts any number of
# trailing comma-separated segments (credential, state, ...) before the
# final "Chairman"/"Chairwoman" token -- verified a no-op on every
# already-passing roster line shape in the Plan-300 cache (single-segment
# "NAME, State, Chairman" and multi-word names like "SHELLEY MOORE CAPITO,
# West Virginia, Chairman"), since one-or-more still matches exactly one
# segment when that's all there is.
#
# Widened again 2026-10-18 (bare "The Chair." fix, see SENATE_LEADER's
# `bare_role` and `_verify_roster_chair_surname` below): CHRG-119shrg59473's
# (Senate Small Business) own roster line reads "JONI ERNST, Iowa, Chair",
# not "...Chairman"/"...Chairwoman" -- this committee's GPO convention uses
# the bare word "Chair" for the title in both the roster block and the body
# ("The Chair.", "Madam Chair", "Chair Ernst"), not just the body's bare
# header. Added "Chair" as a third terminal-token alternative; a no-op on
# every roster line already ending "Chairman"/"Chairwoman" since those two
# literals still match first for lines that actually end that way.
_ROSTER_CHAIR = re.compile(
    r"^([A-Z][A-Z '.’-]+),\s*(?:[A-Za-z .]+,\s*)+(Chairman|Chairwoman|Chair)\s*$"
)

# GPO's front-matter table of contents indexes every member and witness as
# "Surname, Title First M...." (e.g. "Caine, Lieutenant General John D.,
# Retired, Nominee for", "Duffy, Hon. Sean P., U.S. Secretary of
# Transportation"). Used to corroborate a `titled_name` candidate above --
# see module docstring.
#
# Optional generational-suffix group added 2026-10-18, same fix and same
# reason as `gpo_turns._FRONT_MATTER_NAME` (see that module's comment) --
# this is a byte-identical regex, so it carries the identical gap: a
# front-matter witness line like "Griffith III, Preston Wells, nominated to
# be Under Secretary of ..." (CHRG-119shrg60024) or "Hartman Jr., Kenneth,
# President, ..." (CHRG-119shrg58674) never matched before this fix, and
# the generational suffix is consumed and discarded so the captured surname
# still matches how GPO captions that witness's own turn header in the
# body.
_FRONT_MATTER_NAME = re.compile(
    r"^([A-Z][A-Za-z'’-]+)(?:\s+(?:Jr|Sr|II|III|IV|V)\.?)?,\s"
)

# Title-first front-matter witness convention, added 2026-10-18 (see module
# docstring's KNOWN LIMITATIONS entry this closes). Some Senate prints'
# WITNESSES listing doesn't use GPO's surname-first "Surname, Title First..."
# convention `_FRONT_MATTER_NAME` reads at all -- CHRG-119shrg61246 (Senate
# Commerce, Surface Transportation Subcommittee) writes "Chief Will Johnson,
# Chief Special Agent, BNSF Railway Police Department..." instead, title
# first, so "Johnson" never reached `known_names` and every "Chief Johnson."
# turn header in the body (the witness's entire testimony) failed the
# known-participant guard. Anchored on the same title vocabulary
# `SENATE_LEADER` itself would accept as a witness turn header -- Mr./Ms./
# Mrs./Dr., Hon./The Honorable (the front matter's own honorific for a
# Cabinet-level witness later captioned by a `_TITLED_TITLE` word, e.g.
# "Hon. Kristi Noem, Secretary, ..." captioned "Secretary Noem." in the body,
# CHRG-119shrg60722), and every `_TITLED_TITLE` rank/office word -- so this
# can never recognize a title-first line this module's own header pattern
# wouldn't also accept as a real turn opener. Same reuse pattern as
# `gpo_turns._house_witness_intro_names`'s own title-prefix-first
# corroboration source, widened here to the chamber's full title vocabulary
# rather than just Mr./Ms./Mrs./Dr./Hon.
_TITLE_FIRST_PREFIX = re.compile(
    rf"^(?:The Honorable|Hon\.|Mr|Ms|Mrs|Dr|{_TITLED_TITLE})\.?\s+"
)

# After the anchor, GPO gives one or more given-name/middle-initial tokens,
# then the surname, then the role clause -- the surname is simply the LAST
# capitalized token before the first comma (or end of line). A trailing
# generational suffix ("Jr."/"Sr."/"II"/"III"/"IV"/"V", same set
# `_FRONT_MATTER_NAME` already discards from the surname-first form) or a
# military/civil post-nominal ("USN", "USA", "USAF", "USMC", "Ph.D.", "M.D.",
# "Esq.") sitting in that same span is discarded first so it is never
# mistaken for the surname itself (e.g. "Lieutenant General John D. Caine
# USAF, Retired, ..." -- a shape not yet seen in the cached corpus but the
# same class of gap the suffix fix above closed for the surname-first form).
_TITLE_FIRST_SUFFIX_TOKENS = {"jr", "sr", "ii", "iii", "iv", "v"}
_TITLE_FIRST_POST_NOMINAL_TOKENS = {"usn", "usa", "usaf", "usmc", "ph.d", "phd", "m.d", "md", "esq"}


def _title_first_surname(line: str) -> str | None:
    """The witness's surname from a title-first front-matter line (see
    `_TITLE_FIRST_PREFIX`), or `None` if `line` doesn't open with a
    recognized title at all. Leaves the surname-first convention
    `_FRONT_MATTER_NAME` reads untouched -- `_front_matter_known_names`
    tries both, this is purely additive."""
    m = _TITLE_FIRST_PREFIX.match(line)
    if not m:
        return None
    comma = line.find(",", m.end())
    name_part = line[m.end():] if comma == -1 else line[m.end():comma]
    tokens = name_part.split()
    while tokens:
        bare = tokens[-1].rstrip(".").lower()
        if bare in _TITLE_FIRST_SUFFIX_TOKENS or bare in _TITLE_FIRST_POST_NOMINAL_TOKENS:
            tokens.pop()
        else:
            break
    if not tokens:
        return None
    surname = tokens[-1]
    if not re.fullmatch(r"[A-Z][A-Za-z'’-]+", surname):
        return None
    return surname


def _front_matter_known_names(front_matter: str) -> set[str]:
    """Surnames GPO's own front-matter index lists for this print (Member
    Statements / Witness Statements table-of-contents lines). A rank-title
    witness header (see SENATE_LEADER's `titled_title`/`titled_name`) is only
    trusted as a real turn boundary when its surname is in this set -- see
    `_accepts_titled_candidate`. Reads both the surname-first convention
    (`_FRONT_MATTER_NAME`) and the title-first convention
    (`_title_first_surname`) -- see that function's comment."""
    names = set()
    for line in front_matter.splitlines():
        m = _FRONT_MATTER_NAME.match(line)
        if m:
            names.add(m.group(1))
            continue
        surname = _title_first_surname(line)
        if surname:
            names.add(surname)
    return names


def _accepts_titled_candidate(m: re.Match, raw_line: str, known_names: set[str]) -> bool:
    """True unless `m` is a `titled_title`/`titled_name` (rank/cabinet-title
    witness) match that fails the paragraph-start-and-known-participant
    guard described in the module docstring, or a "Chair NAME."/bare "Chair."
    header without a paragraph-start indent (added 2026-10-26, see the module
    docstring). Any other SENATE_LEADER match (including against an older
    pattern that never defined these named groups) is always accepted,
    unchanged."""
    gd = m.groupdict()
    indent = len(raw_line) - len(raw_line.lstrip(" "))
    if gd.get("role_named") == "Chair" or gd.get("bare_role") == "Chair":
        return indent >= 4
    titled_name = gd.get("titled_name")
    if titled_name is None:
        return True
    return indent >= 4 and titled_name in known_names


def chamber_of(chrg_id: str) -> str:
    """"senate" for an "shrg" package id, "house" for an "hhrg" one."""
    low = chrg_id.lower()
    if "shrg" in low:
        return "senate"
    if "hhrg" in low:
        return "house"
    raise ValueError(f"cannot infer chamber from CHRG id: {chrg_id!r}")


def _roster_chair_surname(front_matter: str) -> str | None:
    for line in front_matter.splitlines():
        m = _ROSTER_CHAIR.match(line.strip())
        if m:
            words = m.group(1).split()
            return words[-1].capitalize() if words else None
    return None


def _verify_roster_chair_surname(surname: str, body: str) -> None:
    """Guard on the roster-line fallback (see KNOWN LIMITATIONS: the
    "last capitalized word" heuristic is unverified on a print that both
    lacks a named "Chairman NAME." turn AND has a multi-word chair surname).
    Before letting a roster-derived surname resolve every bare "The
    Chairman."/"The Chairwoman."/"The Chair." turn in the hearing, require
    independent corroboration from the print's own body -- another member or
    witness addressing them as "Chairman/Chairwoman/Chair/Senator SURNAME"
    (e.g. CHRG-119shrg61334 has the witness saying "Thank you, Chairman
    Cruz") -- and fail loudly instead of silently attributing every
    bare-role turn to a name nothing in the print actually supports.

    "Chair" is in this alternation (added 2026-10-18, bare "The Chair." fix)
    because a committee that uses the bare "Chair" title in its roster line
    also uses it in body mentions -- CHRG-119shrg59473 has "Chair Ernst" and
    "Madam Chair" throughout, never "Chairman Ernst"/"Senator Ernst"."""
    mention = re.compile(rf"\b(?:Chairman|Chairwoman|Chair|Senator)\s+{re.escape(surname)}\b")
    if mention.search(body):
        return
    raise GPOBodyNotFound(
        f"roster-derived chair surname {surname!r} is not corroborated anywhere "
        "in the body (no 'Chairman/Chairwoman/Senator NAME' mention) -- refusing "
        "to resolve bare \"The Chairman.\"/\"The Chairwoman.\" turns to it. "
        "Check the roster-line surname heuristic against this print's format."
    )


def _find_bounds_senate(raw: str) -> tuple[int, int]:
    """Auto-detect (start_offset, end_offset) of the spoken-turn body,
    mirroring `gpo_turns._find_bounds` exactly except for which header
    pattern marks the start of the transcript body."""
    lines = raw.splitlines(keepends=True)
    offsets = []
    pos = 0
    for line in lines:
        offsets.append(pos)
        pos += len(line)

    known_names = _front_matter_known_names(raw)
    start_line = None
    for i, line in enumerate(lines):
        m = SENATE_LEADER.match(line.strip())
        if m and _accepts_titled_candidate(m, line, known_names):
            start_line = i
            break
    if start_line is None:
        raise GPOBodyNotFound(
            "No line matching the Senate speaker-turn header pattern "
            "(Senator/Chairman/Chairwoman/Ranking Member/rank-title witness/"
            "The Chairman/The Chairwoman/Mr./Ms./Mrs./Dr./All.) was found -- "
            "pass start_marker explicitly for this hearing."
        )
    start = offsets[start_line]

    end = _find_adjourn_end(raw, start)
    if end is None:
        raise GPOBodyNotFound(
            "No '[Whereupon, ... was adjourned.]' (or closed-session "
            "transition) stage direction was found after the detected "
            "start -- pass end_marker explicitly for this hearing."
        )
    return start, end


def _resolve(m: re.Match, presiding: dict) -> str:
    """Turn a SENATE_LEADER match into a bare surname, updating `presiding`
    (in place) when the match is a NAMED Chairman/Chairwoman/Chair header. A bare
    role resolved from the roster fallback is corroborated exactly once, on
    first use -- see `_verify_roster_chair_surname`."""
    if m.group("role_named"):
        role, name = m.group("role_named"), m.group("role_name")
        if role in ("Chairman", "Chairwoman", "Chair"):
            presiding["chair_surname"] = name
            presiding["source"] = "named"
        return name
    if m.group("senator"):
        senator_state = m.groupdict().get("senator_state")
        if senator_state:
            # State-qualified senator header ("Senator Scott of
            # Florida."), same convention and same reason as the House
            # LEADER's member_state fix: two sitting Senators can share a
            # surname (Rick Scott, FL and Tim Scott, SC), and GPO
            # disambiguates with " of STATE" exactly the way it does for
            # a shared House surname. Keep the qualifier in the speaker
            # label ("Scott of Florida") rather than dropping it, so the
            # two are never merged into one "Scott" speaker.
            return f"{m.group('senator_name').split()[-1]} of {senator_state}"
        return m.group("senator_name")
    if m.group("witness_name"):
        return m.group("witness_name")
    if m.group("bare_role"):
        surname = presiding.get("chair_surname")
        if surname is None:
            return "UNKNOWN_CHAIR"
        if presiding.get("source") == "roster" and not presiding.get("verified"):
            _verify_roster_chair_surname(surname, presiding["body"])
            presiding["verified"] = True
        return surname
    if m.group("all"):
        return "All"
    raise AssertionError(f"SENATE_LEADER matched with no known group set: {m.group(0)!r}")


def gpo_turns_senate(path: Path, start_marker: str | None = None, end_marker: str | None = None):
    """Senate analog of `gpo_turns.gpo_turns()`. Returns an ordered list of
    {"speaker": str, "text": str} turns. See module docstring for the header
    set handled and the bare "The Chairman."/"The Chairwoman." resolution
    rule."""
    soup = BeautifulSoup(path.read_text(), "html.parser")
    raw = soup.get_text("\n")

    if start_marker is not None and end_marker is not None:
        start = raw.index(start_marker)
        end = raw.index(end_marker, start) + len(end_marker)
    else:
        start, end = _find_bounds_senate(raw)

    turns = []  # list of {"speaker":..., "lines":[...]}
    for raw_line, line, header in senate_body_lines(raw, start, end):
        if header is None:
            continue
        if header:
            speaker, rest = header
            turns.append({"speaker": speaker, "lines": [rest]})
        elif not turns:
            # shouldn't happen given the start marker, but guard anyway
            turns.append({"speaker": "UNKNOWN", "lines": [line]})
        else:
            turns[-1]["lines"].append(line)

    out = []
    for t in turns:
        text = " ".join(t["lines"])
        out.append({"speaker": t["speaker"], "text": text})
    return out


def senate_body_lines(raw: str, start: int, end: int):
    """Senate analog of `gpo_turns.house_body_lines()`: yields `(raw_line,
    line, header)` for every physical line of `raw[start:end]` exactly as
    `gpo_turns_senate()` reads it -- `header` is None for a skipped line,
    False for a continuation line, and `(speaker, rest)` for a line that
    opens a new turn. Shared with `header_scan.py` so the scan uses the
    parser's own accept decision rather than a re-derivation of it."""
    body = raw[start:end]
    # Repair GPO's print-layout word wrapping (e.g. "thought-\nprovoking"),
    # same as gpo_turns.gpo_turns().
    body = re.sub(r"(?<=[A-Za-z])-\s*\n\s*(?=[a-z])", "", body)

    presiding = {
        "chair_surname": _roster_chair_surname(raw[:start]),
        "source": "roster",
        "verified": False,
        "body": body,
    }
    known_names = _front_matter_known_names(raw[:start])

    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("["):
            yield raw_line, line, None
            continue
        if line.upper() == line and len(line) < 160:
            yield raw_line, line, None
            continue
        m = SENATE_LEADER.match(line)
        speaker = None
        rest = None
        if m and _accepts_titled_candidate(m, raw_line, known_names):
            titled_name = m.groupdict().get("titled_name")
            if titled_name is not None:
                speaker = titled_name
            else:
                speaker = _resolve(m, presiding)
            rest = line[m.end():]
        if speaker is not None:
            known_names.add(speaker)
            yield raw_line, line, (speaker, rest)
        else:
            yield raw_line, line, False


def build_ref_turn_index_senate(path: Path, start_marker: str | None = None, end_marker: str | None = None):
    """Senate analog of `gpo_turns.build_ref_turn_index()`. Returns
    (ref_words, turn_id_per_word, turns), identical contract to the House
    function."""
    turns = gpo_turns_senate(path, start_marker, end_marker)
    ref_words = []
    turn_id = []
    for ti, t in enumerate(turns):
        toks = normalize(t["text"]).split()
        ref_words.extend(toks)
        turn_id.extend([ti] * len(toks))
    return ref_words, turn_id, turns


def build_ref_turn_index_auto(path: Path, chrg_id: str, chamber: str | None = None, **kw):
    """Dispatch to the Senate or House builder by chamber. `chamber`
    overrides `chamber_of(chrg_id)` when given explicitly. Delegates to
    `gpo_turns.build_ref_turn_index` UNCHANGED for the House case -- this
    function adds a dispatch, it does not re-implement the House path."""
    import gpo_turns  # local import: keeps this module's import-time surface

    ch = chamber or chamber_of(chrg_id)
    if ch == "senate":
        return build_ref_turn_index_senate(path, **kw)
    if ch == "house":
        return gpo_turns.build_ref_turn_index(path, **kw)
    raise ValueError(f"unknown chamber: {ch!r}")


if __name__ == "__main__":
    p = Path(sys.argv[1])
    turns = gpo_turns_senate(p)
    speakers = sorted({t["speaker"] for t in turns})
    print(f"{p.name}: {len(turns)} turns, {len(speakers)} speakers")
    print("speakers:", ", ".join(speakers))
    for t in turns[:8]:
        print(f"  [{t['speaker']}] {t['text'][:80]!r}")

    ref_words, turn_id, _ = build_ref_turn_index_senate(p)
    print(f"ref_words={len(ref_words)} turn_id={len(turn_id)}")
