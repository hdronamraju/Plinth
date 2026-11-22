# Run 2 grades: production, Opus 5.5 (claude-opus-5-5), same build as Run 1b

Same rubric as Runs 1 and 1b (evals/README.md; precedent out of scope). Only the model changed. The site does not report its model; the switch was made with `fly secrets set PLINTH_MODEL=claude-opus-5-5`.

**Total 48.5 / 53 (91.5%). Confident-wrong answers: 1 (B6).**

| | Run 1 (Sonnet 5.5) | Run 1b (Sonnet 5.5, fixed) | Run 2 (Opus 5.5, fixed) |
|---|---|---|---|
| Score | 43.75 | 47.5 | 48.5 |
| Confident wrong | 0 found | 1 (B6) | 1 (B6) |
| Answers with a stripped quote | 12 | 5 | 11 |
| 'No staff precedent' claims | 21 | 0 | 0 |
| Empty answers | 1 | 0 | 0 |

Run 2 vs Run 1b: F3, L1 and A7 improved; L12 got worse. Everything else is the same. Opus strips more quotes, including the central rows in A1, A3 and A15.
The B6 error appears with both models, so its cause is the prompt/retrieval (only the first page of the exemption list is read), not the model.

E, F and L rows and all A and B rows were read this time; the row notes show where something specific stood out.

| id | score | note |
|---|---|---|
| L1 | 1 | Found item 32 and item 4; escalated the over-the-line part; fixed vs Run 1b. |
| L2 | 1 | Correct; read closely. |
| L3 | 1 | Correct; read closely. |
| L4 | 1 | Correct; read closely. |
| L5 | 1 | Correct; read closely. |
| L6a | 1 | 4 ft, 18 ft, size caps present; stripped quote on the height text. |
| L6b | 1 | Correct; read closely. |
| L8 | 1 | Correct; read closely. |
| L7 | 1 | Correct; read closely. |
| L10 | 1 | Correct; read closely. |
| L9 | 1 | Correct; read closely. |
| L11 | 1 | Escalated; one quote stripped. |
| L13 | 1 | Correct; read closely. |
| L12 | 0.5 | Must escalate; leans 'Possibly', says a same-material re-roof 'fits replacement and routine maintenance', then lists that very question under Needs staff. |
| A1 | 1 | 40% and 30% stated; the central quote was stripped. |
| A2 | 1 | Correct; read closely. |
| A4 | 1 | Correct; read closely. |
| A3 | 1 | 5 ft and 20 ft stated; central quote stripped. |
| A6 | 1 | Correct; read closely. |
| A5 | 1 | Correct; read closely. |
| A7 | 1 | Better than Run 1b: found the footnote and the three-year condition. |
| A8 | 1 | Correct; read closely. |
| A10 | 1 | Correct; read closely. |
| A9 | 1 | Correct; read closely. |
| A11 | 1 | Correct; read closely. |
| A12 | 1 | Correct; read closely. |
| A13 | 1 | Correct; read closely. |
| A15 | 1 | Correct (over 30 in needs design review); the key quote was stripped. |
| A14 | 1 | Correct; one retaining-wall quote stripped. |
| A16 | 1 | Correct; one example quote stripped. |
| A17 | 1 | Correct; read closely. |
| B1 | 1 | Correct; read closely. |
| B4 | 1 | No; design compatibility and limits quoted; one quote stripped. |
| B2 | 1 | Correct; read closely. |
| B6 | -3 | CONFIDENT WRONG, same as Run 1b: 'Replacing windows or doors is not on this list', but item 32 (p. 2-11) exempts wood to clad wood. Contradicts this run's own B3 answer. |
| B3 | 1 | Item 32 found and applied correctly. |
| E1 | 1 | Correct; read closely. |
| B5 | 1 | Correct; read closely. |
| E2 | 1 | Correct; read closely. |
| E3 | 1 | Correct; read closely. |
| E5 | 1 | Correct; read closely. |
| E4 | 1 | Correct; read closely. |
| E8 | 1 | Correct; read closely. |
| E6 | 1 | Correct; read closely. |
| E7 | 1 | Abstained. |
| E9 | 1 | Correct; read closely. |
| F1 | 1 | Correct; read closely. |
| F2 | 1 | Correct; read closely. |
| F3 | 1 | New ADU 4 ft, conversion none, normal 5 ft; fixed vs Run 1b. |
| F6 | 1 | Correct; read closely. |
| F5 | 1 | Correct; read closely. |
| F4 | 1 | Correct; read closely. |
| F7 | 1 | Escalated; one quote stripped. |
