> Published copy: a private file path shortened, a database table name replaced, and a reviewer's name replaced with their role.

# Population report — built 2026-10-26

Census file: `census_events_2026-09-25.jsonl` (2812 rows)

Plan-300 file: `plan-300.jsonl` (300 rows)


## Filter funnel

- census rows: 2812
- kind == hearing: 2121
- + non-empty chrg, not _closed, not _dropped: 442
- after dedupe by chrg (18 duplicate-chrg rows collapsed): 424
- excluded (matches plan-300.jsonl by url/event_id/chrg): 291
  remaining: 133
- excluded (HillGenius database row already completed or in progress): 1
  remaining: 132
  (of which 0 have a non-blocking db row: failed/unrequested/etc.)
- 207-hearing wordgold-tier-a development set loaded: 207 ids
- excluded (matched db id is in the 207-hearing development set): 0
- **final population: 132**

## Widening: new GovInfo CHRG packages matched to no-chrg hearings

- govinfo snapshot: `govinfo_chrg_2026-10-16.jsonl` (1047 CHRG-119 packages)
- packages not in the census's chrg set ("new"): 612
- never-processed hearings with no chrg (kind==hearing, db_status in None/unrequested/failed, not closed/dropped): 296
- one-to-one matches at title similarity >= 0.80, same chamber, dateIssued within +/-2 days: 21
- excluded (hearing also matches plan-300.jsonl by url/event_id): 0
- excluded (HillGenius database row already completed or in progress): 0
- excluded (matched db id is in the 207-hearing development set): 0
- **added to population: 21**

## Low-similarity verification (chrg_title_sim < 0.80)

- verdicts file: `low_sim_verification_2026-10-16.jsonl` (33 packages checked)
- kept after verification: 31
- dropped (date mismatch or clearly a different hearing): 1
  - KEEP CHRG-119hhrg59390: govinfo title 'FULL BLAST: CONTRASTING MOMENTUM IN THE SPACE MINING ECONOMY', heldDates ['2025-02-25'] — heldDates ['2025-02-25'] within 2 days of census date 2025-02-25; recomputed title similarity 0.58 against print title 'FULL BLAST: CONTRASTING MOMENTUM IN THE SPACE MINING ECONOMY'
  - KEEP CHRG-119hhrg59876: govinfo title 'H.R. 276, H.R. 845, H.R. 1897, AND H.R. 1917', heldDates ['2025-03-25'] — heldDates ['2025-03-25'] within 2 days of census date 2025-03-25; recomputed title similarity 0.49 against print title 'H.R. 276, H.R. 845, H.R. 1897, AND H.R. 1917'
  - KEEP CHRG-119hhrg59901: govinfo title 'MOVING THE GOALPOSTS: HOW NIL IS RESHAPING COLLEGE ATHLETICS', heldDates ['2025-03-04'] — heldDates ['2025-03-04'] within 2 days of census date 2025-03-04; recomputed title similarity 0.72 against print title 'MOVING THE GOALPOSTS: HOW NIL IS RESHAPING COLLEGE ATHLETICS'
  - KEEP CHRG-119hhrg59922: govinfo title "FIXING BIDEN'S BROADBAND BLUNDER", heldDates ['2025-03-05'] — heldDates ['2025-03-05'] within 2 days of census date 2025-03-05; recomputed title similarity 0.62 against print title "FIXING BIDEN'S BROADBAND BLUNDER"
  - KEEP CHRG-119hhrg60446: govinfo title 'Examining the Growth of the Welfare State, Part II', heldDates ['2025-05-07'] — heldDates ['2025-05-07'] within 2 days of census date 2025-05-07; recomputed title similarity 1.00 against print title 'Examining the Growth of the Welfare State, Part II'
  - KEEP CHRG-119hhrg60455: govinfo title 'INTERNATIONAL NARCOTICS AND LAW ENFORCEMENT SHOULD FIGHT CRIME, NOT FIGHT CONSERVATIVES', heldDates ['2025-03-27'] — heldDates ['2025-03-27'] within 2 days of census date 2025-03-27; recomputed title similarity 0.70 against print title 'INTERNATIONAL NARCOTICS AND LAW ENFORCEMENT SHOULD FIGHT CRIME, NOT FIGHT CONSERVATIVES'
  - KEEP CHRG-119hhrg60631: govinfo title 'AI REGULATION AND THE FUTURE OF U.S. LEADERSHIP', heldDates ['2025-05-21'] — heldDates ['2025-05-21'] within 2 days of census date 2025-05-21; recomputed title similarity 0.66 against print title 'AI REGULATION AND THE FUTURE OF U.S. LEADERSHIP'
  - KEEP CHRG-119hhrg60989: govinfo title 'MEMBER DAY', heldDates ['2025-06-24'] — heldDates ['2025-06-24'] within 2 days of census date 2025-06-24; recomputed title similarity 0.54 against print title 'MEMBER DAY'
  - KEEP CHRG-119hhrg62293: govinfo title 'AMERICA BUILDS: THE ROLE OF INNOVATION AND TECHNOLOGY IN RAIL MODERNIZATION', heldDates ['2025-06-24'] — heldDates ['2025-06-24'] within 2 days of census date 2025-06-24; recomputed title similarity 0.77 against print title 'AMERICA BUILDS: THE ROLE OF INNOVATION AND TECHNOLOGY IN RAIL MODERNIZATION'
  - KEEP CHRG-119hhrg62534: govinfo title 'SCREENTIME IN SCHOOLS . Tuesday, June 10, 2025', heldDates ['2025-06-10'] — heldDates ['2025-06-10'] within 2 days of census date 2025-06-10; recomputed title similarity 0.67 against print title 'SCREENTIME IN SCHOOLS . Tuesday, June 10, 2025'
  - KEEP CHRG-119hhrg63300: govinfo title 'LEGISLATIVE HEARING', heldDates ['2026-01-13'] — heldDates ['2026-01-13'] within 2 days of census date 2026-01-13; recomputed title similarity 0.76 against print title 'LEGISLATIVE HEARING'
  - KEEP CHRG-119shrg60343: govinfo title 'DEPARTMENT OF DEFENSE AUTHORIZATION REQUEST FOR APPROPRIATIONS FOR FISCAL YEAR 2026 AND THE FUTURE YEARS DEFENSE PROGRAM', heldDates ['2025-03-05'] — heldDates ['2025-03-05'] within 2 days of census date 2025-03-05; recomputed title similarity 0.60 against print title 'DEPARTMENT OF DEFENSE AUTHORIZATION REQUEST FOR APPROPRIATIONS FOR FISCAL YEAR 2026 AND THE FUTURE YEARS DEFENSE PROGRAM'
  - KEEP CHRG-119shrg60836: govinfo title 'HARNESSING ARTIFICIAL INTELLIGENCE CYBER CAPABILITIES', heldDates ['2025-03-25'] — heldDates ['2025-03-25'] within 2 days of census date 2025-03-25; recomputed title similarity 0.75 against print title 'HARNESSING ARTIFICIAL INTELLIGENCE CYBER CAPABILITIES'
  - KEEP CHRG-119shrg61270: govinfo title 'HEARING TO CONSIDER PENDING NOMINATIONS', heldDates ['2025-07-23'] — heldDates ['2025-07-23'] within 2 days of census date 2025-07-22; recomputed title similarity 0.44 against print title 'HEARING TO CONSIDER PENDING NOMINATIONS'
  - KEEP CHRG-119shrg61560: govinfo title 'THE CURRENT READINESS OF THE JOINT FORCE', heldDates ['2025-03-12'] — heldDates ['2025-03-12'] within 2 days of census date 2025-03-12; recomputed title similarity 0.77 against print title 'THE CURRENT READINESS OF THE JOINT FORCE'
  - KEEP CHRG-119shrg61564: govinfo title 'THE STATUS OF MILITARY SERVICE ACADEMIES', heldDates ['2025-03-26'] — heldDates ['2025-03-26'] within 2 days of census date 2025-03-26; recomputed title similarity 0.62 against print title 'THE STATUS OF MILITARY SERVICE ACADEMIES'
  - KEEP CHRG-119shrg61611: govinfo title 'DEFENSE OF THE DEPARTMENT OF DEFENSE INFORMATION NETWORK', heldDates ['2025-05-21'] — heldDates ['2025-05-21'] within 2 days of census date 2025-05-21; recomputed title similarity 0.76 against print title 'DEFENSE OF THE DEPARTMENT OF DEFENSE INFORMATION NETWORK'
  - KEEP CHRG-119shrg61892: govinfo title "BIDEN'S BORDER BETRAYAL: CRIMINAL ALIENS IN AMERICA", heldDates ['2025-07-22'] — heldDates ['2025-07-22'] within 2 days of census date 2025-07-23; recomputed title similarity 0.58 against print title "BIDEN'S BORDER BETRAYAL: CRIMINAL ALIENS IN AMERICA"
  - KEEP CHRG-119shrg61928: govinfo title 'NOMINATION OF HON. SEAN DUFFY, NOMINEE TO BE SECRETARY, U.S. DEPARTMENT OF TRANSPORTATION', heldDates ['2025-01-15'] — heldDates ['2025-01-15'] within 2 days of census date 2025-01-15; recomputed title similarity 0.68 against print title 'NOMINATION OF HON. SEAN DUFFY, NOMINEE TO BE SECRETARY, U.S. DEPARTMENT OF TRANSPORTATION'
  - KEEP CHRG-119shrg61929: govinfo title 'NOMINATION OF HOWARD LUTNICK, NOMINEE TO BE SECRETARY, U.S. DEPARTMENT OF COMMERCE', heldDates ['2025-01-29'] — heldDates ['2025-01-29'] within 2 days of census date 2025-01-29; recomputed title similarity 0.65 against print title 'NOMINATION OF HOWARD LUTNICK, NOMINEE TO BE SECRETARY, U.S. DEPARTMENT OF COMMERCE'
  - KEEP CHRG-119shrg61983: govinfo title 'DEPARTMENT OF DEFENSE AUTHORIZATION REQUEST FOR APPROPRIATIONS FOR FISCAL YEAR 2026 AND THE FUTURE YEARS DEFENSE PROGRAM', heldDates ['2025-04-08'] — heldDates ['2025-04-08'] within 2 days of census date 2025-04-08; recomputed title similarity 0.63 against print title 'DEPARTMENT OF DEFENSE AUTHORIZATION REQUEST FOR APPROPRIATIONS FOR FISCAL YEAR 2026 AND THE FUTURE YEARS DEFENSE PROGRAM'
  - KEEP CHRG-119shrg61984: govinfo title 'DEPARTMENT OF DEFENSE AUTHORIZATION REQUEST FOR APPROPRIATIONS FOR FISCAL YEAR 2026 AND THE FUTURE YEARS DEFENSE PROGRAM', heldDates ['2025-04-09'] — heldDates ['2025-04-09'] within 2 days of census date 2025-04-09; recomputed title similarity 0.67 against print title 'DEPARTMENT OF DEFENSE AUTHORIZATION REQUEST FOR APPROPRIATIONS FOR FISCAL YEAR 2026 AND THE FUTURE YEARS DEFENSE PROGRAM'
  - KEEP CHRG-119shrg61985: govinfo title 'DEPARTMENT OF DEFENSE AUTHORIZATION FOR APPROPRIATIONS FOR FISCAL YEAR 2026 AND THE FUTURE YEARS DEFENSE PROGRAM', heldDates ['2025-03-26', '2025-05-13', '2025-05-20'] — heldDates ['2025-03-26', '2025-05-13', '2025-05-20'] within 2 days of census date 2025-03-26; recomputed title similarity 0.57 against print title 'DEPARTMENT OF DEFENSE AUTHORIZATION FOR APPROPRIATIONS FOR FISCAL YEAR 2026 AND THE FUTURE YEARS DEFENSE PROGRAM'
  - KEEP CHRG-119shrg62167: govinfo title 'NOMINATION OF STEVEN BRADBURY, NOMINEE TO BE DEPUTY SECRETARY, U.S. DEPARTMENT OF TRANSPORTATION', heldDates ['2025-02-20'] — heldDates ['2025-02-20'] within 2 days of census date 2025-02-20; recomputed title similarity 0.70 against print title 'NOMINATION OF STEVEN BRADBURY, NOMINEE TO BE DEPUTY SECRETARY, U.S. DEPARTMENT OF TRANSPORTATION'
  - KEEP CHRG-119shrg62231: govinfo title 'NOMINATION OF ARIELLE ROTH, NOMINEE TO BE ASSISTANT SECRETARY OF COMMERCE FOR COMMUNICATIONS AND INFORMATION, NATIONAL TELECOMMUNICATIONS AND INFORMATION ADMINISTRATION', heldDates ['2025-03-27'] — heldDates ['2025-03-27'] within 2 days of census date 2025-03-27; recomputed title similarity 0.65 against print title 'NOMINATION OF ARIELLE ROTH, NOMINEE TO BE ASSISTANT SECRETARY OF COMMERCE FOR COMMUNICATIONS AND INFORMATION, NATIONAL TELECOMMUNICATIONS AND INFORMATION ADMINISTRATION'
  - KEEP CHRG-119shrg62250: govinfo title 'PENDING LEGISLATION', heldDates ['2025-12-02'] — heldDates ['2025-12-02'] within 2 days of census date 2025-12-03; recomputed title similarity 0.43 against print title 'PENDING LEGISLATION'
  - KEEP CHRG-119shrg62324: govinfo title 'NOMINATION OF PAUL DABBAR, NOMINEE TO BE DEPUTY SECRETARY, U.S. DEPARTMENT OF COMMERCE', heldDates ['2025-05-01'] — heldDates ['2025-05-01'] within 2 days of census date 2025-05-01; recomputed title similarity 0.68 against print title 'NOMINATION OF PAUL DABBAR, NOMINEE TO BE DEPUTY SECRETARY, U.S. DEPARTMENT OF COMMERCE'
  - KEEP CHRG-119shrg62647: govinfo title 'THE STATE OF NUCLEAR SHIPBUILDING', heldDates ['2025-04-08'] — heldDates ['2025-04-08'] within 2 days of census date 2025-04-08; recomputed title similarity 0.73 against print title 'THE STATE OF NUCLEAR SHIPBUILDING'
  - KEEP CHRG-119shrg62667: govinfo title 'NOMINATION TO THE NATIONAL AERONAUTICS AND SPACE ADMINISTRATION AND THE FEDERAL COMMUNICATIONS COMMISSION', heldDates ['2025-04-09'] — heldDates ['2025-04-09'] within 2 days of census date 2025-04-09; recomputed title similarity 0.72 against print title 'NOMINATION TO THE NATIONAL AERONAUTICS AND SPACE ADMINISTRATION AND THE FEDERAL COMMUNICATIONS COMMISSION'
  - KEEP CHRG-119shrg62766: govinfo title 'NOMINATIONS TO THE UNITED STATES DEPARTMENT OF COMMERCE', heldDates ['2025-07-09'] — heldDates ['2025-07-09'] within 2 days of census date 2025-07-09; recomputed title similarity 0.69 against print title 'NOMINATIONS TO THE UNITED STATES DEPARTMENT OF COMMERCE'
  - KEEP CHRG-119shrg63393: govinfo title 'NOMINATIONS TO THE UNITED STATES DEPARTMENT OF TRANSPORTATION', heldDates ['2025-07-23'] — heldDates ['2025-07-23'] within 2 days of census date 2025-07-23; recomputed title similarity 0.58 against print title 'NOMINATIONS TO THE UNITED STATES DEPARTMENT OF TRANSPORTATION'
  - DROP CHRG-119hhrg60951: govinfo title 'LEGISLATIVE HEARING ON H.R. 1676, MAKE SWAPS EFFICIENT ACT OF 2025; H.R. 3538, WILDLIFE CONFISCATIONS NETWORK ACT OF 2025; H.R. 3857, SNOW WATER SUPPLY FORECASTING REAUTHORIZATION ACT OF 2025; AND H.R. 3858, SPORT FISH RESTORATION, RECREATIONAL BOATING SAFETY, AND WILDLIFE RESTORATION ACT OF 2025', heldDates ['2025-06-24'] — recomputed title similarity 0.24 against print title 'LEGISLATIVE HEARING ON H.R. 1676, MAKE SWAPS EFFICIENT ACT OF 2025; H.R. 3538, WILDLIFE CONFISCATIONS NETWORK ACT OF 2025; H.R. 3857, SNOW WATER SUPPLY FORECASTING REAUTHORIZATION ACT OF 2025; AND H.R. 3858, SPORT FISH RESTORATION, RECREATIONAL BOATING SAFETY, AND WILDLIFE RESTORATION ACT OF 2025' is below the 0.4 floor; clearly a different hearing

## Readiness exclusions (every record checked by hand, 2026-10-26)

- exclusions file: `readiness_exclusions_2026-10-26.jsonl` (10 hearings)
- dropped: 9
  - DROP CHRG-119hhrg61513: HASC organizational meeting, no witnesses (HillGenius reviewer 10-26: exclude)
  - DROP CHRG-119hhrg62735: GPO print is a different hearing
  - DROP CHRG-119hhrg63300: GPO print is a different hearing
  - DROP CHRG-119shrg61270: GPO print is a different hearing
  - DROP CHRG-119shrg61892: GPO print is a different hearing
  - DROP CHRG-119shrg62250: GPO print is a different hearing; also already processed (0b2386d6)
  - DROP CHRG-119shrg62667: already processed (e9480fd3, transcript contains Isaacman + Trusty)
  - DROP CHRG-119shrg64113: already processed (6ae91460)
  - DROP CHRG-119shrg64226: already processed (38514348)

## Chamber split (final, after widening and verification)

- House: 116
- Senate: 27

## Data-quality notes

- 26 of 143 final survivors have chrg_title_sim < 0.8 (committee-listed title and GovInfo print title differ more than cosmetically; see the verification section above for which of these have been independently checked).
- missing chrg_url: 0
- malformed dates: 0
- duplicate-chrg rows collapsed in step 1 (18): same printed hearing announced on two different committee listing pages (joint hearings, multi-day nomination hearings GovInfo prints as one package, or a hearing's page URL changing between a reschedule).
- **final population after widening and verification: 143**

population.json sha256 `c86a8d286e82a9214ecf5d83524c3b30ba4c592d02da1e4937480b005ed58bb9`
