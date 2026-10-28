> **Read this first** (added for publication)
>
> This is the pre-registration of the test: the population, sampler, seed rule, scoring rules and reporting
> rule, written and committed before the hearings were drawn on 2026-10-27. Two sections were added after
> scoring and are labeled [added after scoring]: "Reference corrections after scoring (2026-10-27)" and
> "What is published, and what is not". The results are in summary.json and per_hearing.csv, and the full
> report is at https://www.hillgenius.com/methodology/speaker-attribution/report.

> Published copy of the test kit's README.md, the pre-registration, with internal details cut. Each cut is marked
> [redacted: ...] and each note added here is marked [published copy: ...]. SHA-256 of the unredacted original
> (kit commit 5826159a): 7f9a9d6018518515945c2e2b0b6ced0cfc3773164fae4994abc289e06095f778. Auditors can read the original under an agreement.

# Public speaker-attribution test kit (pre-registration, nothing filed or spent)

This is the zero-spend half of a public, reproducible test of HillGenius speaker attribution
on congressional hearings. It is a pre-registration: the population, the sampler, and this
text are published before any hearing is processed and before the draw's seed exists. No API
spend, no database writes, and no processing submissions happen as part of building this kit.

Protocol precedent: [redacted: internal references]. This kit follows the same
conventions (seeded `random.Random`, a hashed frozen population, the NIST beacon seed rule)
applied to speaker attribution instead of word accuracy.

## The claim under test

HillGenius transcripts of House and Senate committee hearings correctly attribute spoken
words to the right named speaker. Names are assigned per diarized speaker turn; members of
Congress are identified by Bioguide id, witnesses and staff by name. The reference is the GPO
printed hearing (the GovInfo CHRG package for each sampled hearing), the official record of
who said what, turned into a per-word speaker reference by the blind procedure below and
frozen before any HillGenius output is compared to it.

One headline figure is reported, two ways: **by words** (fraction of spoken words carrying the
correct speaker, so a long misattributed turn counts more than a short one) and **by speaker**
(fraction of speaker turns correctly attributed). Each is given as precision (of the speakers
assigned, how many were right) and recall (of the words or turns spoken, how many carried the
right speaker). There is no corrected or adjudicated variant of the figure: the reference is
finalized first, the score is computed once.

## Population — frozen 2026-10-26

Population: printed House and Senate committee hearings from the September 2026 backlog-sweep
census (`census_events_2026-09-25.jsonl`) that HillGenius has never processed and has no
current plan to process, widened with GovInfo CHRG packages published after the census. Built by
`population.py`; full filter funnel, widening, verification, and chamber split in
`population_report.md`. As frozen on 2026-10-26:

- **143 hearings** (House 116, Senate 27)
- `population.json` sha256: `c86a8d286e82a9214ecf5d83524c3b30ba4c592d02da1e4937480b005ed58bb9`

**Readiness check (done 2026-10-26).** Before the draw, every record was checked by hand: the
video plays and is the right hearing (Senate recordings confirmed by their caption text), and
the witness list matches the GovInfo print. Ten of the 153 hearings frozen on 2026-10-16 were
dropped (`readiness_exclusions_2026-10-26.jsonl`): five already processed under a url the
database check could not match (one of them the 2026-10-26 smoke run), four whose print
describes a different hearing, and one organizational meeting with no witnesses. Where the
scraped record had a broken video link or an incomplete witness list, the fix comes from public
sources only (the congress.gov committee-meeting record or the print's witness list) and is
applied at submission. Nominee introducers are not added to witness lists: no committee page
listed them before the hearing, so the pipeline would not have known them.

**Widening (done 2026-10-16).** `govinfo_chrg_2026-10-16.jsonl` is a committed snapshot of all
1,047 CHRG-119 packages on GovInfo as of 2026-10-16T17:40Z, built once by
`fetch_govinfo_chrg.py enumerate` with an api.data.gov key (the shared `DEMO_KEY` was
rate-limited). 612 of those packages are not in the census's chrg set. `population.py` matches
them one-to-one against the 296 never-processed census hearings that had no chrg at census
time (same chamber, dateIssued within 2 days, title similarity >= 0.80): 21 matched and were
added. Lowering the bar to the census's own 0.55 would add at most 5 more, so 0.80 stands.

**Low-similarity verification (done 2026-10-16).** The 33 population rows whose committee title
and print title differ (chrg_title_sim < 0.80) were checked against each package's GovInfo
summary (`low_sim_summaries_2026-10-16.jsonl`, fetched by `fetch_govinfo_chrg.py summaries`;
verdicts in `low_sim_verification_2026-10-16.jsonl` from `verify_low_sim.py`): 32 keep (held
date matches the census date, print title is a reformatting of the same hearing), 1 drop
(CHRG-119hhrg60951, a different hearing; title similarity 0.24). Both files are committed so
`population.py --skip-db-check` reproduces the same 143 hearings offline (step 7's exclusions
file also lists the smoke-run hearing the live check catches); only the file hash differs,
because the recorded filter counts differ.

Why never-processed only: the 207 development hearings were used to develop the system, and
[redacted: internal detail on what the system keeps from hearings it processes]. Restricting to hearings the pipeline has never seen in any form removes both
objections, and a reader can verify the restriction from the census without trusting the
database. (Decision 2026-10-16.)

Filters, in order: census rows with `kind == "hearing"`, a non-empty GovInfo `chrg` id, not
closed, not dropped (442) → dedupe by `chrg` (424, 18 duplicate-chrg rows collapsed — the same
printed hearing announced on two different committee pages) → exclude every hearing already
claimed by the 300-hearing processing plan from the same census (`plan-300.jsonl`), which
includes the 207 hearings used for development (133 remain) → re-check [redacted: database table]
by source url and exclude anything already `completed` or in progress (1 excluded, the
2026-10-26 smoke run; 132 remain) → exclude anything whose matched database id is in the
207-hearing [redacted: internal name] development set, as an independent second check (0 excluded) →
widen with GovInfo (+21) → drop verified mismatches (-1) → drop readiness exclusions (-9).
**Final: 143.**

Every hearing in the population is equally eligible; nothing about committee, date, or
chrg_title_sim enters the sampler's frame.

[redacted: internal note on widening the population]

## Sampler, seed rule, and replacement rule

`sampler.py --seed <128-hex> --n 100` draws a full permutation of `population.json` with
`random.Random(int(seed, 16))`, starting from the population's own frozen order (sorted by
`chrg`). The first `n` positions of that permutation are the **sample** that gets processed;
positions `n+1..N` are the pre-registered, ordered **replacement list**. `--dry-run`
substitutes a stand-in all-zero seed and is for testing the mechanics only — it is never the
real draw. `sample.json`/`sample_dry_run.json` record the position of every hearing in the
permutation (1..N), the full population hash drawn from, and the seed used.

**Replacement rule, pre-registered before the draw.** A sampled hearing that cannot be
processed for a reason outside the pipeline's control — no public video available for it, the
GovInfo print turns out to describe a different event than the one HillGenius would capture,
or the available video runs under 10 minutes — is replaced by the next unused hearing in the
ordered replacement list (position n+1, then n+2, and so on). No one picks the substitute by
hand; it is whichever hearing the pre-drawn permutation names next. Every replacement is
published with the hearing it replaced and the specific reason, at the time it happens, not
after the fact.

A hearing that fails for a reason **inside** the pipeline — a bad diarization, a crash, a
timeout, a roster mismatch — is **not** replaced. It stays in the sample and is reported as a
failure, the same as any other scored outcome. Replacement exists only for hearings this test
was never able to measure in the first place, not for hearings the pipeline measured badly.

**Seed rule:** the `outputValue` of one NIST Randomness Beacon v2 pulse
(`https://beacon.nist.gov/beacon/2.0/pulse/time/<unix ms>`), at a UTC timestamp announced at
least 3 hours in advance of the pulse. A pulse's value can't be known before it is published,
so the lead only has to put the pulse clearly after the announcement commit is public; 3 hours
does that with room to spare. (An earlier draft asked for 24 hours; it was shortened on
2026-10-26 to fit the publication date, with the population, rules and sampler already frozen.)
The sampler never fetches the beacon itself — the 128-hex `outputValue` is pasted in by hand
after the pulse exists, so anyone can rerun the exact draw offline once they have
`population.json` and the announced pulse value.

- Beacon pulse timestamp: **`2026-10-27T03:30:00Z`** (unix ms `1793071800000`,
  `https://beacon.nist.gov/beacon/2.0/pulse/time/1793071800000`), announced in this commit
  on 2026-10-27 at about 00:05Z, 3h25m before the pulse. (A pulse at 2026-10-17T18:00:00Z was announced on
  2026-10-16 and withdrawn the same day when the reference-finalization and publication rules
  were rewritten; the seed comes after the final text, so a new time is announced.)
- Seed: `6C8B84729D863158FC71E44D05EE63E8E1C61DDFE85298176AC892190F95E8B6A104075721B43AE69A2B76AC7530432E6D5DAFA27004E9E31D5721BCE44491DA`
  (the pulse's `outputValue`; pulse index 2001207, chain 2, fetched 2026-10-27 03:32Z).
  `python3 sampler.py --seed <seed> --n 100` writes `sample.json`, sha256
  `35cb7bd0ddac5202bd3190bf2f7e401ff214a55f2305a8a738f9df20ba5a5396`: 100 hearings (House 79,
  Senate 21), replacements at positions 101-143.

## Pipeline freeze

Production is frozen at a specific git SHA on [redacted: branch name] before the seed is
drawn. Nothing on the speaker-attribution path (diarization, roster matching, name assignment)
may change between the freeze and the run.

- Production SHA: `9f3d03d0` ([redacted: branch name and host] verified at this
  SHA on 2026-10-26; re-pinned from `f88790af`, the 2026-10-16 freeze, because production moved on
  before the draw). The 2026-10-26 smoke run (`91744d47`) processed at `201ecf5a`; the only code
  between `201ecf5a` and `9f3d03d0` is [redacted: internal file names], none of it on the
  speaker-attribution path. [redacted: internal deployment detail], so every worker SHA reported during the run is checked against
  `9f3d03d0` and any processing-code difference is recorded here. Sample size: n = 100.

## Processing rule

The 100 (or `n`) sampled hearings are processed **fresh in production** at the frozen SHA, in
batches of 25. Nothing is served from cache: any existing transcript, diarization, or
intermediate artifact for a sampled hearing is set aside before the run, so the result reflects
what the frozen pipeline actually produces today, not a previously cached attempt.

## Scorer

Self-contained under `scorer/`, reproducing the matching/alignment logic already used for
development ([redacted: internal paths]) against a plain segments-jsonl + GPO-print input instead of that harness's cached
pipeline artifacts. `scorer/score.py --hearing-id <uuid> --chrg <CHRG id> --print <path>
--segments <path> --out <dir> --reference reference/<uuid>/reference_final.json` scores one
hearing against its frozen reference with no hand exclusions; `scorer/pool.py` pools many
hearings' output into the headline figure, both by cluster and by word (its `--adjudications`
option is unused in this test: the reference is final before scoring). `score.py` checks that
the reference was built on the same print words it reads (a recorded sha256) and refuses
otherwise; without `--reference` it scores against the parser's own turns, which is how
`scorer/REGRESSION.md` was run. With every span decided "parser", the two give identical
output (checked on a development hearing). Before scoring, `score.py` runs a header-scan
precheck (`scorer/header_scan.py`) over the print and refuses to score (nonzero exit) if it
finds a turn-header-like line the vendored GPO parser didn't recognize, unless the reference
records that line as reviewed (see "Reference finalization") — catching a reference slip
before it can be scored, rather than in review after. `fetch_inputs.py` (kit root) fetches a hearing's two inputs: the shipped
transcript ([redacted: storage path], one row per diarized turn with its cluster id,
name and Bioguide id), and the GPO print from GovInfo. Checked against the
development scorer on 3 hearings with no hand exclusions to compare against (28 clusters, 0
diffs) and against the 207-hearing development pool re-scored under the fixed parser (3,793
clusters, 0 residual alignment slips found) — see `scorer/REGRESSION.md`. `scorer/PROVENANCE.md`
documents every vendored file's source commit.

- Scorer sha256 (of `scorer/SHA256SUMS`, which hashes every non-test file in `scorer/`):
  `583888d4d0de59addde847347af779fff19f522d882a8b4dc6a3ffe6f9c4c509`

## Reference finalization — blind, before scoring

The reference is built from the print alone. Nobody who touches it sees a HillGenius name
until it is frozen.

1. **Two machine readings of the print.** The deterministic turn-header parser (vendored in
   `scorer/`, hash recorded above) and an LLM segmentation (Gemini; model id and prompt hash
   below) each assign a speaker to every word of the print, independently. The parser sees the
   print and the committee roster (names, states, Bioguide ids); the LLM sees the print alone —
   it returns a name, never an id, and the roster attaches a Bioguide id to both sides afterward
   by the same deterministic rule (see "The LLM reference" below). The header scan
   (`scorer/header_scan.py`) flags any header-looking line the parser rejected.
2. **Where the two readings agree, that is the reference.**
3. **Where they disagree, or the header scan flags a line, the span goes to a reviewer** who
   sees only the print excerpt and the roster, and answers one question: who is speaking here
   according to the print. The reviewer is an AI agent (Claude, the agent running this test),
   disclosed as such. A span the agent can't settle from the print goes to HillGenius's
   founder, who may also check the hearing video; `review_log.jsonl` names the reviewer on
   every row. The review happens before any HillGenius transcript of a sampled hearing is read
   (the scorer's input fetch, `fetch_inputs.py`, runs only after the reference hashes are
   committed), so the reviewer cannot know which answer helps HillGenius.
4. **The reference is frozen and hashed** before the first HillGenius transcript is scored.
   Every reviewed span is published with the print excerpt, both machine readings, and the
   reviewer's answer. The per-hearing file layout and hashing rule are in "Reference files"
   below.

### The LLM reference

The second machine reading (`scorer/llm_segment.py`) is deliberately kept small: it reads print
text and nothing else, and all it returns per turn is a name — no roster, no Bioguide id, no
committee membership. Identity resolution is a separate, deterministic step applied the same
way to both machine readings, not something asked of a model that was never shown the roster it
would need to answer correctly.

- **Model:** `gemini-2.5-pro`, chosen on a five-hearing bake-off before the draw (fewest
  flagged spans: 12 versus 59 for flash-lite and 73 for flash; see `scorer/LLM_REFERENCE.md`).
- **Backend:** [redacted: internal detail]
- **Prompt hash:** the fixed instructions template (`PROMPT_INSTRUCTIONS_HEAD`) hashes to
  `8eee074ece07042f853ff871a7df84485eb71b7f0226ff27b9867303838b97a3` (sha256), recorded per
  hearing too, since the per-chunk prompt is this fixed template plus that chunk's print text —
  it doesn't vary by hearing, only by chunk.
- **Chunking:** [redacted: internal detail]
- **Names in, ids out:** the model returns `speaker` (a bare surname) and a nullable
  `display_name` (a fuller name the print's own text happens to make available, e.g. a
  self-introduction) — never a Bioguide id. `compare_refs.py` resolves both the parser's and the
  LLM's speaker label to a Bioguide id through the identical `roster.py` `Roster.resolve()` call,
  so identity never depends on either machine's own say-so about who a person is, only on its
  read of whose name is on the line.

Full detail ([redacted: internal detail]) is in `scorer/LLM_REFERENCE.md` [published copy: withheld; see README.md].

### Reference files

`scorer/finalize_reference.py` builds these in three steps per hearing: `prepare` (runs both
readings, the word-level comparison and the header scan), `review` (records one decision per
span: the parser's speaker, the LLM's, a third speaker, or a split where the speaker changes
inside the span), and `freeze` (applies the decisions and writes the frozen reference; it
refuses while any span lacks a decision, or if two decisions give the same word different
speakers). A header-scan span runs from the flagged line to the end of the parser turn it sits
in; deciding "parser" there records that the line is not a turn header. Word positions in
every file are positions in the scorer's own reference word stream (the parser's turn texts,
tokenized as `score.py` tokenizes them), so a reader can line any span or turn up against the
scored words directly.

Each sampled hearing gets a folder `reference/<hearing_id>/`:

| File | What it holds |
|---|---|
| `parser_turns.json` | The deterministic parser's reading of the print: every turn it assigned, independent of the LLM reading. |
| `llm_turns.json` | The LLM's reading of the same print (`scorer/llm_segment.py`'s output — see "The LLM reference" above). |
| `disagreements.json` | Every word-level span where the two readings disagree, or the header scan flagged a line (see `scorer/LLM_REFERENCE.md` for how a span is located and matched). |
| `review_sheet.md` | The same spans with their print excerpts, as the reviewer read them. |
| `review_log.jsonl` | One row per reviewed span: span id, the reviewer's decision, the evidence type consulted (print excerpt only, or print plus video), a note, the reviewer, and a timestamp. Published in full — every decision, not a summary of them. |
| `reference_final.json` | The frozen turn list: each turn's word range, speaker and resolved Bioguide id, after every disagreement is settled, plus the sha256 of the print, of its reference words, of the scorer, and of `review_log.jsonl`, and the header-scan lines reviewed. This is the only file the scored transcript is ever compared against — `parser_turns.json` and `llm_turns.json` feed the reference, they aren't it. |
| `SHA256` | The sha256 of that hearing's `reference_final.json`, in `shasum -a 256 -c` format. |

The frozen reference hashes are committed before the first sampled hearing's transcript is
scored — scoring starts only once every `SHA256` file in `reference/` is in the commit history,
so nobody can tune a reference against output they've already seen.

**Print errors count against HillGenius.** When the official print itself names the wrong
speaker, the reference inherits that error, and the HillGenius transcript, if right, is scored
wrong. Such cases can only be noticed after scoring, so they are not corrected. They are
listed in a footnote with the video timestamp and the spoken evidence, and their count is
stated beside the headline. In the 207-hearing development pool there were 3 such cases in
about 3,700 speaker turns.

**Audit of the reference.** Once every hearing's reference is frozen, `audit_sample.py` draws a
seeded sample of 200 *agreeing* turns — turns that were never a disagreement span, drawn across
all 100 hearings and weighted by word count, using the same beacon `outputValue` as the sample
draw itself. Each sampled turn is reviewed the same way a disagreement span is: by the agent from
the print excerpt, with the founder (and the video) only for a turn the print can't settle —
nothing from the scored transcript. The count of corrections
found is published beside the headline, and if any corrections are found, the implied error rate
of the agreeing portion (corrections found / 200, carried across the full agreeing population)
is reported alongside it, so a reader can see how good the blind reference is where nobody
flagged it, not just where the two machine readings happened to disagree.

**Calibration on the development pool.** Before the draw, the same two readings are run on the
207 development hearings, where the reference has been checked by hand over several weeks.
The agreement rate between the parser and the LLM, and which was right on each disagreement,
is published in `scorer/LLM_REFERENCE.md`, so readers know what the cross-check catches.

## Reporting rule

The published result includes: the headline figure (by words and by speaker, precision and
recall), a per-hearing table (one row per sampled hearing), the per-cluster score rows for the
whole sample (speaker HillGenius gave, speaker in the reference, word count, match rule,
verdict), every reviewed reference span with its evidence, the 200-turn reference audit, and
the print-error footnote. Counts of spans reviewed and of turns scored wrong are stated in the
summary.

## Reference corrections after scoring (2026-10-27) [added after scoring]

**Result: 99.4% of words and 98.8% of speakers correctly attributed** (1,639,116 of 1,649,095
words; 1,669 of 1,690 clusters; precision equals recall). Files: `results/`.

The locked run scored the 100 hearings once against the frozen references: 99.1% by words and
98.5% by speaker (`results/locked_run/`). After that run, every member id the references
resolved was checked against each print's own member list (`audit_bioguides.py`, output
`results/bioguide_check.txt`). The check found reference errors where HillGenius matched the
official print and was scored wrong. The corrections below were applied the same way to every
hearing, and all 100 were rescored (`rescore_corrected.py`). The frozen reference files are
unchanged; the script builds the corrected copies from them. Six clusters changed, all listed
here, and none moved against HillGenius.

1. **Member identity.** [redacted: database column] was empty for Mark E. Green (TN), Sylvester Turner
   (TX) and Marjorie Taylor Greene (GA). As a result the roster could resolve "Green" and
   "Turner" only to Al Green and Michael Turner. The surnames were filled in every hearing's
   roster cache. The two frozen references that carried those wrong member ids get corrected
   copies: 60649 Green G000553 → G000590 and Turner T000463 → T000489, and 60692 Turner
   T000463 → T000489. Both prints' committee rosters list Mark E. Green (Chairman) and
   Sylvester Turner. The scorer resolves member ids from the roster, so these copies change no
   verdict; they make the published reference agree with the identity scored. Three clusters
   went from wrong to correct: 60649 Green (2,908 words), 60649 Turner (499) and 60692 Turner
   (418).
2. **One speaker labeled two ways in the reference**, which split the cluster vote: 61366
   RUBIO/Rubio and MAST/Mast, 61418 "Kim of California"/Kim, and 64242 "VAN DUYNE" (the
   uppercase label did not resolve to Beth Van Duyne). 61366 Rubio (12,650 words) and 61418
   Kim (1,395) went from ambiguous to scored, both correct. 64242 Van Duyne (312) went from
   wrong to correct. 61366 Mast stays ambiguous.
3. **Print error.** 59601 prints "Mr. Murray." for the witness Nicholas McMurray. Those turns
   were relabeled McMurray. No outcome changed: the cluster stays ambiguous.

**Member ids cross-checked** (added after review, changes no score). The scorer matches a
member by Bioguide id only when it can resolve the print's speaker on the roster, and by surname
otherwise. `check_member_ids.py` compares every scored cluster's shipped member id with the ids
in the reference the score used; it runs on the published folder and writes
`results/member_id_check.jsonl` there. Of the 1,669 clusters scored
correct, 1,189 carry the reference's id and none carries a different one. Two (64314 Horsford
and Jack) name the member in full but carry no id. The other 478 have no member id in the
reference, mostly witnesses. For 12 of those, another member of the chamber shares the surname;
each print was read, and each names the member labeled (`member_id_review.md`). No cluster
scored wrong carries the reference's id.

## What is published, and what is not [added after scoring]

Published, for agents and people:
- The population (`population.json`, `population_report.md`, `population.py`), the beacon
  pulse and seed, and the sampler.
- The scoring rules in prose and the scorer's hash; the per-cluster score rows for all sampled
  hearings (no timestamps, no cluster boundaries).
- The per-hearing table and a JSON summary of the headline figure.
- The frozen per-hearing reference files and their hashes, every reviewed span with its print
  excerpt and both machine readings, the reference audit, and the print-error footnote with
  video timestamps.
- Every sampled hearing's HillGenius transcript, viewable per hearing on hillgenius.com as
  speaker-labeled text beside a link to the official print.

Not published as a bulk download: word and segment timestamps, diarization cluster boundaries,
the alignment code that builds the machine reference, and the 207-hearing development pool's
rows. The time alignment of the official print to the audio is the one artifact here with
training value to a competitor, and the published material above is enough to check every
step of the claim without it. The full reproduction kit, including the alignment code and
timestamps, is available to named auditors under an agreement; ask.

## Files in this kit

| File | What it is |
|---|---|
| `census_events_2026-09-25.jsonl` | The September 2026 backlog-sweep census, copied in so the kit doesn't depend on files outside the repo. |
| `population.py` | Rebuilds `population.json` from the census (plus a live, read-only [redacted: database table] check), then widens with GovInfo packages and applies low-similarity verdicts if those files are present. |
| `population.json`, `population.sha256` | The frozen population and its hash. |
| `population_report.md` | The filter funnel, widening step, low-similarity verification, chamber split, and data-quality notes from the last `population.py` run. |
| `fetch_govinfo_chrg.py` | One-time live fetcher: `enumerate` builds the GovInfo CHRG snapshot `population.py` widens from; `summaries` fetches package summaries for the low-similarity verification. Not run by `population.py` itself — its outputs are committed, then read offline. |
| `verify_low_sim.py` | Turns fetched GovInfo summaries into keep/drop verdicts for the 33 chrg_title_sim < 0.80 rows, offline. |
| `sampler.py` | Draws a full permutation of the population once the seed exists; the first `n` positions are `sample.json`, the rest are the pre-registered, ordered replacement list. `--dry-run` for testing. |
| `audit_sample.py` | Draws the 200-turn reference audit sample from the frozen `reference/` folders once they exist: agreeing turns only, weighted by word count, seeded from the same beacon `outputValue` as `sampler.py`. See "Audit of the reference." |
| `sample_dry_run.json` | A dry-run draw (stand-in all-zero seed, `--n 100`) — not the real test. |
| `make_plan.py` | Splits the drawn sample into four submission batches of 25 (`plan_batch1-4.jsonl`) and the ordered replacement list (`replacements.jsonl`). |
| `readiness_2026-10-26.json`, `readiness_exclusions_2026-10-26.jsonl` | The hand readiness check (see "Readiness check"): per hearing, the confirmed video, the witness list, any public-source fix, and how it enters production; and the ten exclusions with reasons. |
| `make_submit_sql.py` | [redacted: internal operations detail] |
| `batch_status.py` | [redacted: internal operations detail] |
| `fetch_inputs.py` | Fetches a hearing's two scoring inputs: the shipped transcript from storage and the GPO print from GovInfo. Run only after the reference hashes are committed. |
| `audit_bioguides.py` | Checks every member id the frozen references resolved against each print's own member list; output in `results/bioguide_check.txt`. |
| `rescore_corrected.py` | Rebuilds corrected copies of the roster cache and of six references from the frozen files, then rescores all 100 hearings (see "Reference corrections after scoring"). |
| `check_member_ids.py`, `member_id_review.md` | Compares every scored cluster's member id with the reference's (`results/member_id_check.jsonl`), and the hand check of the 12 surname matches where another member shares the name. |
| `results/` | The reported scores: `pooled.json`, `per_hearing.tsv`, `per_cluster.jsonl`. `results/locked_run/` holds the same files from the locked run, before the corrections. |
| `audit_sample.json`, `audit_review.md` | The 200-turn reference audit sample and the verdict on each turn. |
| `RUNBOOK.md` | The operator's steps for the run: draw, submission, monitoring, replacements, cost. |
| `scorer/` | The print parser, the LLM reading (`llm_segment.py`), the word-level comparison (`compare_words.py`), reference finalization (`finalize_reference.py`), the scorer (`score.py`) and the pooler (`pool.py`), with tests; hashed by `scorer/SHA256SUMS` (see "Scorer"). [published copy: llm_segment.py, compare_words.py, finalize_reference.py, the internal notes and the tests are withheld; see README.md] |
| `README.md` | This file. |

The drawn sample (`sample.json`), the `reference/` folders and the scores are added as the run
produces them.
