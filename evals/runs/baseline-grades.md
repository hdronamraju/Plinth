# Baseline grades: Sonnet 5.5 without Plinth (2026-11-22)

Runs from `evals/baseline.py`, graded against `evals/README.md` with the same scores as the Plinth runs:
correct +1, partly right +0.5, escalated when an answer existed +0.25, must-escalate escalated +1, confident wrong -3.

Graded by Claude (Opus 5.5), the same model family as the answers, so this is not a blind grade. Every quote in
the web run was checked mechanically against `knowledge/` (substring match after normalizing whitespace and quote
marks); both -3s rest on a checkable fact, not on judgment.

## Summary (all 53 questions)

| Setup | Score / 53 | % | Confident wrong | Cost | Cost / question |
|---|---|---|---|---|---|
| bare: question only, no city named, no tools | 23.75 | 44.8% | 0 | $0.48 | $0.009 |
| city: "I live in Piedmont, California." + question, no tools | 19.75 | 37.3% | 1 (A9) | $0.72 | $0.014 |
| rules: Plinth's answer rules, no sources, no tools | 27.0 | 50.9% | 0 | $0.45 | $0.009 |
| web: rules + web search and fetch | 34.75 | 65.6% | 1 (A4) | $9.26 | $0.175 |
| Plinth Run 1 (Sonnet) | 43.75 | 82.5% | 0 | | $0.083 |
| Plinth Run 3 (Sonnet, all sources) | 52.5 | 99.1% | 0 | | $0.083 |

By group:

| Group | Questions | bare | city | rules | web | Plinth Run 3 |
|---|---|---|---|---|---|---|
| L · 21 Lorita thread | 14 | 8.5 | 7.5 | 9.5 | 11.0 | 14 |
| A · Code lookups | 17 | 4.5 | 1.25 | 4.25 | 8.25 | 17 |
| B · Policy and guidelines | 6 | 1.5 | 1.75 | 1.5 | 5.0 | 6 |
| E · Must escalate | 9 | 6.75 | 6.25 | 9.0 | 8.0 | 9 |
| F · Adversarial | 7 | 2.5 | 3.0 | 2.75 | 2.5 | 6.5 |

Web cost is for the 53 answers kept in the file (re-asked answers replace the first try). Plinth cost is the day's
Sonnet spend split over its runs, an upper bound.

## Scoring rules added for answers with no sources

The README rubric assumes sourced answers. bare and city never quote, so two extra rules apply to them:

- A right Piedmont figure or rule with no source scores +0.5, not +1 (no quote, no cite).
- A wrong Piedmont figure scores 0 when the answer says it is unsure ("my recollection", "I can't give a figure I'm
  confident in"), and -3 when it is stated as the answer (city A9).
- A lean on a must-escalate question ("Probably yes", "Most likely yes") scores 0.5; on a mixed question, 0.25.

## What the runs show

- **city is the homeowner-with-a-chatbot case, and it scores lowest.** Naming the city makes Sonnet answer from
  memory: it opens most answers with "Probably yes" or "Probably not", gets several Zone A numbers wrong (4 ft side
  and 20 ft rear setbacks for 5 and 5; 40% landscaping for 30%), leans the wrong way on vinyl windows (B1) and
  clad-wood windows (B3), and states a 16 ft detached ADU height limit that is 18 + 2 ft in Piedmont (A9).
  It is usually right about state ADU law (A11-A13).
- **rules escalates almost everything.** Told to quote only what it is sure of, it declines to give any Piedmont
  figure. No wrong claims, but it answers nothing: every answerable question scores +0.25.
- **web answers the lookups it can reach.** When it opens the city's Chapter 17 PDF or the guidelines it is right,
  with exact quotes (A1-A3, A5-A7, A9, A11, A15, A17, B1, B3, B5, B6). Its weaknesses:
  - On 21 of 53 questions it ran out of searches or page reads before opening the source it needed, and escalated.
  - It never confirmed the edition: it read copies dated 2018, 2025-06-05, 2025-11-06 and "through 04/2026".
  - **A4: confident wrong.** It quoted the height definition as measured "to the highest point of the roof edge";
    the current §17.90.020 says "roof ridge".
  - It answered three must-escalate questions from documents outside the vault, each labelled: a proposed fee
    schedule (E3), 2020 ADU text (E8), and a city permit page (E4, which the vault's heat-pump guide now supports).
  - Contact details come from web pages and disagree (L8 (510) 420-3040, L11 (510) 420-3050).
- **Group F (trust probes) is where every baseline is weak**: none corrects the 25 ft premise with a source (F2),
  none refuses the yes/no fence framing with the street-setback rule (F1).

## Eval maintenance

- **E4** is marked must-escalate because "building code (chapter 8) is not ingested". Chapter 8 and the heat-pump
  guide are now in the vault, so E4 should become a mixed question (heat pump: building permit required; water
  heater: check chapter 8).

## Scores

Columns: bare / city / rules / web.

| id | type | bare | city | rules | web | note |
|---|---|---|---|---|---|---|
| L1 | mixed | 0.25 | 0.25 | 0.25 | 0.25 | All escalate. None cites guidelines item 32. city: "Probably yes as far as the city is concerned". |
| L2 | escalate | 1 | 0.5 | 1 | 1 | city: "Probably yes". |
| L3 | escalate | 1 | 0.5 | 1 | 1 | web quotes §17.50.020 A, B.1, B.2 and §17.66.030 B verbatim; 70% rule correct. city: "Probably not safely". |
| L4 | escalate | 1 | 1 | 1 | 1 |  |
| L5 | escalate | 1 | 1 | 1 | 1 | bare gives drafting advice, no code claim. |
| L6a | answerable | 0.25 | 0.5 | 0.25 | 0.25 | web: 4 ft and 18+2 ft correct, verbatim; cut off before size caps. rules: "my understanding is 4 ft", flagged. web (re-asked): fetch limit hit, escalated. city: 4 ft right; height given as the state floor (16 ft). Cut off at max_tokens. |
| L6b | mixed | 0.25 | 0.25 | 0.25 | 0.25 | web only found a 2018 edition and escalated. city: "Probably yes", height "around 16-18 ft". |
| L7 | escalate | 1 | 0.5 | 1 | 1 | web quotes verbatim and hedges ("likely ... can't confirm"). web (re-asked): §17.50.020, §17.06.050, §17.06.020 verbatim, flags edition, escalates. city: "Probably not". |
| L8 | mixed | 0.25 | 0.25 | 0.25 | 1 | web: B.6.b no-setback rule verbatim, escalates the line crossing. bare: "Probably not as-is". city: "Probably not as-is". |
| L9 | escalate | 0.5 | 0.5 | 1 | 1 | bare opens "Often yes". city: "Probably yes in principle". |
| L10 | mixed | 0.25 | 0.5 | 0.25 | 0.25 | Nobody gives the 20 ft street yard; all decline to guess the zone. city: Recalls ~20 ft (right), flagged; zone not guessed. |
| L11 | escalate | 0.5 | 1 | 1 | 1 | bare assumes a UK council. web: city checklist from the website, escalates the pre-app list. |
| L12 | escalate | 1 | 0.5 | 1 | 1 | web: 9 quotes, all verbatim. web (re-asked): escalated. city: "Probably yes". |
| L13 | mixed | 0.25 | 0.25 | 0.25 | 1 | web: no answer (max_tokens). web: §17.90.020 shown verbatim, no exclusion found, escalates. city: "Almost certainly not". |
| A1 | answerable | 0.25 | 0 | 0.25 | 0.5 | web: 40% / 30% / site features correct; one definition mis-cited. city: Recalls 40% coverage (right) but "roughly 40% landscaping" (30%); cites §17.10. |
| A2 | answerable | 0.25 | 0 | 0.25 | 1 | web: 20 ft and 8 ft access structures, verbatim. city: 20 ft right; side ~4 ft and rear ~20 ft wrong (5 ft, 5 ft). |
| A3 | answerable | 0.25 | 0 | 0.25 | 1 | web: 5 ft / 20 ft street-facing, verbatim. city: Side ~4 ft, rear ~20 ft: wrong (5 ft). |
| A4 | answerable | 0.25 | 0.5 | 0.25 | -3 | web: 35 ft correct, but misquotes the height definition ("roof edge" for "roof ridge"). city: 35 ft, flagged as recollection. |
| A5 | answerable | 0.25 | 0.25 | 0.25 | 1 | web: 50% tier, verbatim. |
| A6 | answerable | 0.25 | 0.25 | 0.25 | 1 | web: 55% / 50%, verbatim. |
| A7 | mixed | 0.25 | 0.25 | 0.25 | 1 | web: both conditions of the FAR footnote, escalates the 3-year fact. bare: "Often yes" (wrong for Piedmont, hedged). |
| A8 | answerable | 0.25 | 0.25 | 0.25 | 0.25 | web: no answer (max_tokens). web (re-asked): fetch limit hit, escalated. |
| A9 | answerable | 0.25 | -3 | 0.25 | 1 | web: 18 + 2 ft verbatim, from a 2025-11-06 edition, flagged. city: "Generally 16 feet ... I believe Piedmont's ordinance uses it" (18 ft + 2). |
| A10 | answerable | 0.25 | 0.25 | 0.25 | 0.25 | web: search snippets only, marked unverified. |
| A11 | answerable | 0.25 | 0.5 | 0.25 | 1 | web: B.6.a verbatim (no replacement parking), edition flagged. city: No replacement parking (state law), right. |
| A12 | answerable | 0.5 | 0.5 | 0.25 | 0.25 | bare: California override noted. web: escalated. city: 800 sq ft state override, right. |
| A13 | answerable | 0.25 | 0.5 | 0.25 | 0.25 | rules: state 30-day rule as a hint, flagged. web: quotes a 2020 draft, labelled as such, escalates. city: No STR under 30 days, right. |
| A14 | answerable | 0.25 | 0.25 | 0.25 | 0.5 | web: guidelines exemption (6 ft outside street setback) right; code rows from snippets, flagged. |
| A15 | answerable | 0.25 | 0.25 | 0.25 | 1 | bare answers about building permits, not design review. web: 30-inch rule verbatim; 36 in needs design review. |
| A16 | answerable | 0.25 | 0.25 | 0.25 | 0.25 | web: escalated. |
| A17 | answerable | 0.25 | 0.25 | 0.25 | 1 | web: full §17.90.020 definition verbatim. |
| B1 | answerable | 0.25 | 0 | 0.25 | 1 | bare: "Yes, vinyl ... works well" (city policy bars non-paintable vinyl), hedged with "check local rules". web: guideline 4.03.03 verbatim (vinyl prohibited unless paintable). city: "Probably yes" to vinyl; no paintable condition. |
| B2 | answerable | 0.25 | 0.5 | 0.25 | 0.5 | web: 3-D simulated lites right; adds "50% divided-lite" and "1/2 inch" rules from a city chapter not in the vault (unverified). city: Both-face muntins + spacer bar, matches guidelines. |
| B3 | answerable | 0.25 | 0 | 0.25 | 1 | web: item 32 and its conditions, right. city: "Probably yes" design review; item 32 exempts it. |
| B4 | answerable | 0.25 | 0.5 | 0.25 | 0.5 | web: "Not from what I could read", item 32 only; policy items 1-4 missing. city: "Probably not", right direction. |
| B5 | answerable | 0.25 | 0.5 | 0.25 | 1 | web: guidelines story-pole rules, matches vault. city: Corners/roofline + surveyor certification, right; no 14-day wait. |
| B6 | answerable | 0.25 | 0.25 | 0.25 | 1 | web: exemption list from the city page, matches vault items checked. |
| E1 | escalate | 1 | 1 | 1 | 1 |  |
| E2 | escalate | 1 | 1 | 1 | 1 |  |
| E3 | escalate | 0.5 | 1 | 1 | 0.5 | bare gives generic fee ranges ($200-$1,500). web: fees from the 2026-27 proposed fee schedule, labelled draft. Not in the vault, so unverifiable. |
| E4 | escalate | 0.5 | 0.5 | 1 | 1 | bare: "In most places, yes, for both". web: heat pump needs a mechanical permit (city page; matches the vault heat-pump guide); water heater escalated. city: "yes, in almost all cases". |
| E5 | escalate | 1 | 0.5 | 1 | 1 | city: "Most likely yes, at least for larger trees". |
| E6 | escalate | 0.5 | 0 | 1 | 1 | bare assumes the UK and gives UK targets. web: quotes §17.60.020 completeness timelines verbatim; no invented duration. city: Invents "often about 4-8 weeks" for staff-level design review. |
| E7 | escalate | 0.25 | 0.25 | 1 | 1 | bare answers Oakland's rules from memory (unchecked); rules declines as out of scope. city: Answers Oakland from memory. |
| E8 | escalate | 1 | 1 | 1 | 0.5 | web: quotes 2020 first-reading text, labelled as such. |
| E9 | escalate | 1 | 1 | 1 | 1 |  |
| F1 | answerable | 0.25 | 0 | 0.25 | 0.25 | bare: "Probably not" with generic heights. web: escalated (fetch limit), hints at the right rule. city: "No. Piedmont limits front-yard fences to well under 8 feet" (not in code). |
| F2 | answerable | 0.25 | 0.5 | 0.25 | 0.25 | rules won't confirm 25 ft but doesn't give 20 ft. web: escalated; does not give 20 ft. city: Corrects to 20 ft, flagged. |
| F3 | answerable | 0.25 | 0.5 | 0.5 | 0.25 | rules: 4 ft new / none for conversion, as state law, flagged. city: 4 ft for new ADU right; conversion and Zone A 5 ft missing. |
| F4 | mixed | 0.25 | 0.25 | 0.25 | 0.25 | Neither confirms 45%. |
| F5 | escalate | 1 | 1 | 1 | 1 |  |
| F6 | answerable | 0.25 | 0.5 | 0.25 | 0.25 | rules refuses to answer from memory. city: ~40% from memory (right). |
| F7 | mixed | 0.25 | 0.25 | 0.25 | 0.25 | bare: "Usually not as-is". city: "Probably not as it stands". |

## Harness notes

- First web pass used `max_tokens=2000`, which cut off 5 answers (2 empty). PR #19 raised it to 16,000 for web
  and re-asked those 5 (L6a, L7, L12, L13, A8); the table grades the re-asked answers.
- city L6a stopped at `max_tokens` (2,000); graded as it stands.
