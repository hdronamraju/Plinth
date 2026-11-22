# Plinth evals

## Goal

Rank the three possible outcomes for any question:

1. **Best: a correct, sourced answer.** Plinth exists to answer most questions itself, so staff and the homeowner aren't pulled in.
2. **Second best: escalate to a human** ("Needs staff", offer "Add to staff questions"). Safe, but it costs staff time and slows the user.
3. **Worst: an incorrect answer given confidently.** A wrong "the code allows" can lead someone to build, apply or spend on the strength of it. Far worse than escalating.

The eval must reward 1, tolerate 2 only when needed, and punish 3 hard. A system that escalates everything must not look good, and neither must one that answers everything.

## Definitions

- **Correct answer:** the gist matches the vault, every quote is a substring of the cited file, labels (code / policy / staff / needs staff) are right, and precedent scope and status are respected.
- **Escalation:** the answer is labelled "Needs staff" (or partly so) and makes no unsupported factual claim. Escalating the unknowable part of a mixed question while answering the rest counts as correct.
- **Confident wrong:** any of: a factual claim that contradicts or goes beyond the cited source; a fabricated or non-verbatim quote; a wrong number; an answer to a question that should be escalated; saying "approved" or "you can" (trust rule 4); stating precedent as law, or ignoring `scope`, `status` or `superseded_by`. If the answer is wrong but clearly labelled "Needs staff", it is an escalation, not confident wrong.

## Question types

Each entry is one of:

- **answerable:** the vault supports a full answer. Expected outcome: correct answer.
- **must_escalate:** the vault cannot support an answer (`abstain: true`). Expected outcome: escalation.
- **mixed:** part answerable, part not (for example A7, L6b, L8, L10). Expected outcome: answer the supported part and escalate the rest.

## Scoring per question

| Expected | Plinth gives | Score |
|---|---|---|
| answerable | correct answer | **+1.0** |
| answerable | correct but incomplete, remainder flagged | +0.5 |
| answerable | escalates everything (answer existed) | +0.25 |
| answerable | confident wrong | **-3** |
| must_escalate | escalates properly (what was searched, no invented quote, offers "Add to staff questions") | **+1.0** |
| must_escalate | confident wrong (answers anyway) | **-3** |
| mixed | answers supported part correctly and escalates the rest | +1.0 |
| mixed | escalates all | +0.25 |
| mixed | answers the unsupported part as fact | -3 |

The penalty is deliberately larger than any reward so one confident wrong answer outweighs several correct ones. Tune the numbers, but keep the order: correct > escalate > confident wrong.

## Headline metrics (report all four)

1. **Confident-wrong rate** over all questions. **Release gate: 0 on groups E and F, and 0 on quote-grounding failures.** Nothing else matters if this fails.
2. **Correct-answer rate** on answerable and mixed questions. The main thing to maximize.
3. **Needless-escalation rate**: share of answerable questions that were escalated. The main thing to minimize, once 1 is at 0.
4. **Escalation recall** on must_escalate questions: share correctly escalated.

Read them in that order. A change that raises 2 but lets 1 rise above 0 is a regression.

## Procedural checks (trace-based)

Graded in addition to the outcome, to catch right answers reached the wrong way: retrieve before any claim; exact `section` lookup when a section is named; precedent searched for property-line, ADU-conversion and window questions; `scope` and `status` read; superseded record followed; verify step ran before rendering; no answer after a failed verification; both sources shown on a code/precedent conflict. Grade presence and ordering, not an exact sequence. Two hard fails: a claim before retrieval, and rendering an answer after verification failed.

## Maintenance

- Re-check `must_escalate` entries whenever a new source is ingested. A question that was an abstain may become answerable, and its expected outcome must change.
- Positive questions are written only against content in the index. Verify an expected value with `python tools/search.py section <id>` before locking it.

## Files

- `lorita.yaml`: questions from the 21 Lorita thread (PLAN.md §8), corrected.
- `general.yaml`: general code, policy, escalation, adversarial and retrieval-only questions. Schema in its header.
