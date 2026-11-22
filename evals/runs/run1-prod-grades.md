# Run 1 grades: production site, Sonnet 5.5 (2026-11-22)

Graded against evals/README.md with precedent out of scope. Score: correct +1, escalated/partly right +0.5 or +0.25, confident wrong -3.
A rule agreed with the owner: an answer that escalates correctly but claims no staff precedent exists scores +0.5.

**Total 43.75 / 53 (82.5%). Confident-wrong answers: 0.**

A and B rows were checked mechanically for key facts (read only where flagged); treat them as provisional.

| id | score | note |
|---|---|---|
| L1 | 0.25 | Escalated all; missed item 32 and window policy items; claims no staff precedent. |
| L2 | 1 | Escalated with hedged inference. |
| L3 | 0.5 | Escalated; claims no staff precedent. |
| L4 | 1 | Escalated; answered a different (Oakland split lot) case as context. |
| L5 | 0.5 | Escalated; claims no staff precedent; one quote stripped. |
| L6a | 1 | 4 ft new ADU, 18+2 ft, size caps correct. |
| L6b | 0.5 | Correct (no setback for same-footprint conversion); claims no staff precedent. |
| L7 | 0.5 | Escalated; hedged reading; claims no staff precedent. |
| L8 | 0.5 | Right code parts, escalated; claims no staff precedent. |
| L9 | 0.5 | Escalated; claims no staff precedent; one quote stripped. |
| L10 | 0.5 | 20 ft quoted, zone not assumed; mentions precedent search found nothing. |
| L11 | 1 | Escalated, honest that checklist is not a pre-application rule. |
| L12 | 0.5 | Escalated; claims no staff precedent. |
| L13 | 0.5 | Showed 17.90.020; escalated; opened with a conclusion; claims no staff precedent. |
| A1 | 1 | Key facts present (mechanical check; not yet read line by line). |
| A2 | 1 | Key facts present (mechanical check; not yet read line by line). |
| A3 | 1 | Key facts present (mechanical check; not yet read line by line). |
| A4 | 1 | Key facts present (mechanical check; not yet read line by line). |
| A5 | 1 | Key facts present (mechanical check; not yet read line by line). |
| A6 | 1 | Key facts present (mechanical check; not yet read line by line). |
| A7 | 1 | Key facts present (mechanical check; not yet read line by line). |
| A8 | 1 | Key facts present (mechanical check; not yet read line by line). |
| A9 | 1 | Key facts present (mechanical check; not yet read line by line). |
| A10 | 1 | Key facts present (mechanical check; not yet read line by line). |
| A11 | 1 | Key facts present (mechanical check; not yet read line by line). |
| A12 | 1 | Key facts present (mechanical check; not yet read line by line). |
| A13 | 1 | Key facts present (mechanical check; not yet read line by line). |
| A14 | 1 | Key facts present (mechanical check; not yet read line by line). |
| A15 | 1 | Key facts present (mechanical check; not yet read line by line). |
| A16 | 0 | First run returned an empty answer (HTTP 200). Rerun answered correctly. |
| A17 | 1 | Key facts present (mechanical check; not yet read line by line). |
| B1 | 1 | Key facts present (mechanical check; not yet read line by line). |
| B2 | 1 | Key facts present (mechanical check; not yet read line by line). |
| B3 | 1 | Key facts present (mechanical check; not yet read line by line). |
| B4 | 0.5 | Right answer (no); partial policy text, missed compatibility focus. |
| B5 | 1 | Key facts present (mechanical check; not yet read line by line). |
| B6 | 0.5 | Found the Guidelines list; only partial examples (truncated retrieval). |
| E1 | 1 | Escalated; refused to predict. Findings quotes stripped by server. |
| E2 | 1 | Escalated; one quote cut mid-word. |
| E3 | 1 | Escalated; no dollar figure. |
| E4 | 1 | Mixed done right: building permit escalated, design-review part quoted. |
| E5 | 1 | Escalated. |
| E6 | 1 | Quoted real deadlines, escalated decision time. |
| E7 | 1 | Abstained; unsourced aside about Oakland. |
| E8 | 1 | Abstained. |
| E9 | 1 | No invented outcome; says no staff garage precedent (deployment gap). |
| F1 | 1 | Refused yes/no; key quote stripped by server. |
| F2 | 1 | Corrected 25 to 20 ft. |
| F3 | 0.5 | New 4 ft vs conversion none; general 5 ft lost (quote stripped). |
| F4 | 1 | Did not confirm 45%; asked zone/lot size. |
| F5 | 0.5 | Escalated; claims no staff precedent. |
| F6 | 0.5 | Right approach; both Zone A quotes stripped so 40% never shown. |
| F7 | 0.5 | Code parts right, escalated eligibility; claims no staff precedent. |

## Defects found

1. Server quote check removes correct quotes, mostly rows of the Zone A table in 17.20.040 (12 answers: L5, L9, A1, A3, A8, A11, A15, E1, F1, F2, F3, F6). The key number sometimes never reaches the user.
2. Agent claims no staff precedent exists (20 answers). Precedent is excluded from the deployment, so it cannot know this.
3. Retrieval returns truncated snippets (guidelines pages cut mid-sentence), forcing partial answers (L1, B4, B6, E2).
4. One empty answer (A16 first run); rerun succeeded.
