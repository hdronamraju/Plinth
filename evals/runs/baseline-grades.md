# Baseline grades: Sonnet 5.5 without Plinth (2026-11-22)

Runs from `evals/baseline.py`, graded against `evals/README.md` with the same scores as the Plinth runs:
correct +1, partly right +0.5, escalated when an answer existed +0.25, must-escalate escalated +1, confident wrong -3.

Graded by Claude (Opus 5.5), the same model family as the answers, so this is not a blind grade.
Every quote in the web run was checked mechanically against `knowledge/` (substring match after normalizing
whitespace and quote marks). The one -3 below rests on that check, not on judgment.

## Summary

| Run | Questions | Score | % | Confident wrong | Cost | Cost / question |
|---|---|---|---|---|---|---|
| bare (question only, no city named) | 53 | 23.75 | 44.8% | 0 | $0.48 | $0.009 |
| rules (Plinth's rules, no tools) | 53 | 27.0 | 50.9% | 0 | $0.45 | $0.009 |
| web (rules + web search and fetch), partial | 22 graded of 24 | 14.0 / 22 | 63.6% | 1 (A4) | $4.92 | $0.205 |
| Plinth run 1 (Sonnet), same 22 questions | 22 | 17.25 / 22 | 78.4% | 0 | | $0.083 |
| Plinth run 3 (Sonnet, all sources), same 22 questions | 22 | 22.0 / 22 | 100% | 0 | | $0.083 |
| rules, same 22 questions | 22 | 11.5 / 22 | 52.3% | 0 | | |
| bare, same 22 questions | 22 | 10.5 / 22 | 47.7% | 0 | | |

The web run covers L1-L13 and A1-A10 only (it was stopped early). L13 and A8 have no answer: the call hit
`max_tokens` while the server-side search was still running, so they are not scored. That is a harness limit
(`max_tokens=2000` is too low once web search's own code execution counts toward output), not a model answer.
L6a, L7 and L12 were also cut off by `max_tokens` but had already said enough to grade.

## What the runs show

- **bare** never knew the city: the questions don't name Piedmont, so every answer is generic ("depends on your
  jurisdiction"). It mostly scores as escalation. Some generic leanings would mislead a Piedmont homeowner
  (B1 "Yes, vinyl ... works well"; A7 "Often yes" on attic FAR; L11 and E6 assume the UK), but each is hedged,
  so none is counted as confident wrong. This run is not a fair test of a homeowner using a chatbot, who would
  name the city. Re-run it with "In Piedmont, CA:" prepended to each question before charting it.
- **rules** escalated almost everything. Told to quote only what it was sure of, it declined to give any Piedmont
  figure (not the 20 ft setback, not the 40% coverage, not the FAR tiers). Safe, but it answers nothing: every
  answerable question scores +0.25. It made no wrong claims.
- **web** answered the code-lookup questions well when it could open the city's Chapter 17 PDF (A1-A3, A5-A7, A9
  correct, with verbatim quotes), and escalated the property-line questions much as Plinth does. Its problems:
  - It often hit its search or fetch limit before reading anything and then escalated (L1, L2, L4, L5, L6b, L9,
    L10, A10).
  - It could not tell which edition it had read: several answers say the PDF showed amendments through 02-04/2026
    but no effective date, and A9 read a 2025-11-06 edition.
  - **A4: confident wrong.** It quoted the height definition as measured "to the highest point of the roof edge".
    The current code (§17.90.020) says "roof ridge". This is the old-edition risk in one line.
  - A1 cited the "Coverage means" definition to §17.90.010; it is in §17.90.020.
  - Contact details came from web pages and differ between answers (L8 gives (510) 420-3040, L11 gives
    (510) 420-3050). At least one is wrong. Not scored, but worth knowing.

## Scores

Columns: bare / rules / web. "esc" = escalated; "n/a" = not asked or no answer.

| id | type | bare | rules | web | note |
|---|---|---|---|---|---|
| L1 | mixed | 0.25 | 0.25 | 0.25 | All escalate. None cites guidelines item 32. |
| L2 | escalate | 1 | 1 | 1 | |
| L3 | escalate | 1 | 1 | 1 | web quotes §17.50.020 A, B.1, B.2 and §17.66.030 B verbatim; 70% rule correct. |
| L4 | escalate | 1 | 1 | 1 | |
| L5 | escalate | 1 | 1 | 1 | bare gives drafting advice, no code claim. |
| L6a | answerable | 0.25 | 0.25 | 0.5 | web: 4 ft and 18+2 ft correct, verbatim; cut off before size caps. rules: "my understanding is 4 ft", flagged. |
| L6b | mixed | 0.25 | 0.25 | 0.25 | web only found a 2018 edition and escalated. |
| L7 | escalate | 1 | 1 | 1 | web quotes verbatim and hedges ("likely ... can't confirm"). |
| L8 | mixed | 0.25 | 0.25 | 1 | web: B.6.b no-setback rule verbatim, escalates the line crossing. bare: "Probably not as-is". |
| L9 | escalate | 0.5 | 1 | 1 | bare opens "Often yes". |
| L10 | mixed | 0.25 | 0.25 | 0.25 | Nobody gives the 20 ft street yard; all decline to guess the zone. |
| L11 | escalate | 0.5 | 1 | 1 | bare assumes a UK council. web: city checklist from the website, escalates the pre-app list. |
| L12 | escalate | 1 | 1 | 1 | web: 9 quotes, all verbatim. |
| L13 | mixed | 0.25 | 0.25 | n/a | web: no answer (max_tokens). |
| A1 | answerable | 0.25 | 0.25 | 0.5 | web: 40% / 30% / site features correct; one definition mis-cited. |
| A2 | answerable | 0.25 | 0.25 | 1 | web: 20 ft and 8 ft access structures, verbatim. |
| A3 | answerable | 0.25 | 0.25 | 1 | web: 5 ft / 20 ft street-facing, verbatim. |
| A4 | answerable | 0.25 | 0.25 | -3 | web: 35 ft correct, but misquotes the height definition ("roof edge" for "roof ridge"). |
| A5 | answerable | 0.25 | 0.25 | 1 | web: 50% tier, verbatim. |
| A6 | answerable | 0.25 | 0.25 | 1 | web: 55% / 50%, verbatim. |
| A7 | mixed | 0.25 | 0.25 | 1 | web: both conditions of the FAR footnote, escalates the 3-year fact. bare: "Often yes" (wrong for Piedmont, hedged). |
| A8 | answerable | 0.25 | 0.25 | n/a | web: no answer (max_tokens). |
| A9 | answerable | 0.25 | 0.25 | 1 | web: 18 + 2 ft verbatim, from a 2025-11-06 edition, flagged. |
| A10 | answerable | 0.25 | 0.25 | 0.25 | web: search snippets only, marked unverified. |
| A11 | answerable | 0.25 | 0.25 | n/a | |
| A12 | answerable | 0.5 | 0.25 | n/a | bare: California override noted. |
| A13 | answerable | 0.25 | 0.25 | n/a | rules: state 30-day rule as a hint, flagged. |
| A14 | answerable | 0.25 | 0.25 | n/a | |
| A15 | answerable | 0.25 | 0.25 | n/a | bare answers about building permits, not design review. |
| A16 | answerable | 0.25 | 0.25 | n/a | |
| A17 | answerable | 0.25 | 0.25 | n/a | |
| B1 | answerable | 0.25 | 0.25 | n/a | bare: "Yes, vinyl ... works well" (city policy bars non-paintable vinyl), hedged with "check local rules". |
| B2 | answerable | 0.25 | 0.25 | n/a | |
| B3 | answerable | 0.25 | 0.25 | n/a | |
| B4 | answerable | 0.25 | 0.25 | n/a | |
| B5 | answerable | 0.25 | 0.25 | n/a | |
| B6 | answerable | 0.25 | 0.25 | n/a | |
| E1 | escalate | 1 | 1 | n/a | |
| E2 | escalate | 1 | 1 | n/a | |
| E3 | escalate | 0.5 | 1 | n/a | bare gives generic fee ranges ($200-$1,500). |
| E4 | escalate | 0.5 | 1 | n/a | bare: "In most places, yes, for both". |
| E5 | escalate | 1 | 1 | n/a | |
| E6 | escalate | 0.5 | 1 | n/a | bare assumes the UK and gives UK targets. |
| E7 | escalate | 0.25 | 1 | n/a | bare answers Oakland's rules from memory (unchecked); rules declines as out of scope. |
| E8 | escalate | 1 | 1 | n/a | |
| E9 | escalate | 1 | 1 | n/a | |
| F1 | answerable | 0.25 | 0.25 | n/a | bare: "Probably not" with generic heights. |
| F2 | answerable | 0.25 | 0.25 | n/a | rules won't confirm 25 ft but doesn't give 20 ft. |
| F3 | answerable | 0.25 | 0.5 | n/a | rules: 4 ft new / none for conversion, as state law, flagged. |
| F4 | mixed | 0.25 | 0.25 | n/a | Neither confirms 45%. |
| F5 | escalate | 1 | 1 | n/a | |
| F6 | answerable | 0.25 | 0.25 | n/a | rules refuses to answer from memory. |
| F7 | mixed | 0.25 | 0.25 | n/a | bare: "Usually not as-is". |

## Harness follow-ups

- Raise `max_tokens` for the web condition (5 of 24 answers stopped at 2000 output tokens; 2 produced nothing).
- Name the city in the bare condition, or add a `bare-city` condition, so it tests what a homeowner would type.
- Web cost came to $0.205 per question across the 24, higher than the 3-question test ($0.12). All 53 would be
  about $11.
