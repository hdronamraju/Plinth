# Project Plinth — Build Plan

Owner: Harsha Dronamraju · Drafted 2026-11-07 · For implementation in Claude Code

## 1. What we're building

A web app where a Piedmont, CA homeowner (or their architect):

1. Enters an address and sees the property's public facts, each with its source.
2. Asks plain questions ("Can I add a window?") and gets answers that quote the code, or an honest "this needs staff."
3. Turns the questions the app can't answer into a **clean, fillable PDF for the planner**. The homeowner sends it however they like. The app never sends email.
4. Uploads the planner's filled-in PDF, and her answers are saved as **precedent** that future answers can cite.

**Design goal for the PDF:** when the planner opens it, she thinks "this is easy to fill out." Every question is numbered, has its context and code citation, states the applicant's proposed reading, and has a tick-box plus a notes field for her answer.

**Non-goals:** sending or reading email, filing permits, building-code (Title 24) review, legal advice, and anything that looks like a permit decision.

## 2. Why: the 21 Lorita thread (the founding case)

From Sep 24 to Nov 9, 2026 it took 46 days and about 20 emails, relayed through the architect, to reach a meeting. Lessons:

- **Some questions are already answered in published text.** A window question got a reply in 8 minutes because the Window Replacement Policy covers it. The app should answer these instantly.
- **Some need staff interpretation where the code is silent.** Example: floor area and FAR for a structure that crosses the property line. Staff ruled the whole footprint counts, the opposite of the architect's reading of §17.90.020. This is precedent worth keeping.
- **Some are judgment calls across departments.** Example: what can be done about the encroachment. The app's job here is to frame the question well, not answer it.
- **Answers change.** On Oct 29 staff said the garage couldn't be converted; on Nov 6 they said there's "a path forward." Precedent needs a date, a scope and a "superseded by" link.
- **The fastest reply had a clear shape.** The Oct 22 email cited the section, stated the proposed reading, and asked staff to confirm or correct. The planner answered inline, point by point. The PDF copies this shape.
- **Public records miss things.** The encroachment only showed up in a new survey. The property page must list what records cannot confirm.

## 3. Trust rules (enforce in code, not just copy)

1. No factual claim without a source: a code section, policy document, city form, or a precedent record. Show the quoted text inline.
2. Every answer is stamped with the code edition (Chapter 17, effective 2026-05-20) and the corpus check date.
3. Every answer part is labeled **Code says** / **Staff have said** (precedent, dated) / **Needs staff**.
4. If retrieval finds nothing that supports an answer, the app says so and offers "Add to staff questions." It doesn't guess.
5. The app never says "approved" or "you can." It says "the code allows," followed by the quote.
6. No ads, no referrals, no lead capture.

## 4. Core user flows (v1)

### 4.1 Property page
- Input: address. v1 resolves to a property record that the user confirms.
- Fields: address, APN, zone, lot size, year built, existing structures, recorded easements, known permits, survey on file (y/n + date).
- **Each field stores `value`, `source` (label + URL or "entered by owner"), `as_of`.** v1 can be mostly owner-entered with source fields. Automated county lookups come later (see §9).
- An always-visible **"Not confirmed by records"** box. It defaults to: boundaries not verified by a recent survey; unpermitted work unknown; permit history may be incomplete.
- Attachments: owner uploads plans, survey, deeds. Each is labeled and referenced by sheet in the PDF.

### 4.2 Ask
- Free-text question in the context of one property.
- Pipeline: retrieve code sections, policies and precedent → draft the answer under the quote-or-abstain rule → verify each claim against its quote → render.
- Output: short answer, quoted sources, labels, and "paths forward" when the answer is no (variance, alternative design, ask staff).
- Every question gets a status: `answered`, `needs_staff`, or `partially_answered`.
- One-click "Add to staff questions," which pre-fills context, cited sections and a suggested proposed reading.

### 4.3 Staff questions → PDF
- A list of `needs_staff` questions. The user edits wording, orders them, and writes or accepts the **proposed reading** for each.
- Optional: the planner's name and the meeting date.
- **Generate PDF** produces a fillable PDF (see §5).
- Each generated PDF gets an ID and version, so a returned PDF matches its questions.

### 4.4 Import the planner's answers
- Upload the returned PDF.
- Read the form fields (checkbox + notes per question). If fields are empty because she printed it and wrote by hand, fall back to manual entry beside a page image.
- The user reviews each parsed answer and sets its **scope**: `this_property` or `general`.
- Save each as a precedent record. If it contradicts an earlier record on the same topic, prompt: "Supersede the earlier answer?"

### 4.5 Precedent library
- A list of records: question, answer, decision, staff role, date, code sections, scope, status (`current`/`superseded`), source PDF.
- Retrieval includes `current` precedent and labels it "Staff have said (date)."

## 5. The PDF: spec

Letter size, simple and calm: one sans-serif font, black text, a single accent color, plenty of white space. It should look like a well-made city form, not a marketing piece.

**Page 1: Cover**
- Title: "Planning questions for [address]"
- Submitted by / on behalf of; contact; date; document ID + version
- Property summary table: APN, zone, lot size, year built, relevant existing conditions. Every value has a small source note.
- Project in one or two sentences
- Attachments list with sheet references (e.g. "A1 Existing site plan," "Survey, 2026-10")
- "How to use this form": "Each question has a proposed reading. Tick Confirmed, Not as proposed, or Need more info, and add notes. Typing directly into this PDF works in Acrobat, Preview or a browser."
- Index: one line per question, with page numbers

**Pages 2+: one block per question (target 2 to 3 per page; never split a block across pages)**
- `Q3 · Floor area for structure over property line`
- **Context:** 1 to 3 sentences, referencing attachment sheets
- **Code reference:** section number + short quote (or "No section found that addresses this")
- **Precedent found:** if any, with date
- **Our proposed reading:** one or two sentences, specific enough to confirm or correct
- **Response** (fillable form fields):
  - ☐ Confirmed ☐ Not as proposed ☐ Need more info (radio group)
  - Notes / conditions (multi-line text field)
  - Code section relied on (single-line text field, optional)

**Last page:** reviewer name, title, date (text fields) and "General questions or notes" (multi-line).

**Footer every page:** address · doc ID v# · page X of Y · "Prepared with Plinth. Not an application or permit."

Field names must be stable and parseable, e.g. `q3_decision`, `q3_notes`, `q3_section`, `reviewer_name`, `reviewer_date`. Embed the doc ID and a question-ID map in PDF metadata.

**Acceptance test for the PDF:** generate the 21 Lorita sample; fill it in macOS Preview, Adobe Acrobat and Chrome's PDF viewer; save; re-import; all values parse correctly.

## 6. Architecture

- **App:** Next.js (App Router) + TypeScript. Single user in v1 (no auth; a local or simple password gate is fine).
- **DB:** Postgres + pgvector, or SQLite + sqlite-vec for v1 simplicity. Use Drizzle or Prisma.
- **LLM:** Anthropic API (Claude), with citations/document grounding. Prompts are versioned in the repo.
- **Retrieval:** hybrid search, BM25 + embeddings, over code sections, policies and precedent. Exact terms ("street yard," "17.90.020") matter.
- **PDF generation:** `pdf-lib`, which supports AcroForm text fields, radio groups and metadata. Lay out with a small custom layout helper. Don't use react-pdf: it doesn't make fillable fields.
- **PDF import:** `pdf-lib` to read field values; `pdfjs-dist` to render page images for manual-entry fallback.
- **Storage:** local disk or S3-compatible storage for uploads and generated PDFs.

### Data model (sketch)
```
property(id, address, apn, zone, lot_size_sqft, year_built, notes, created_at)
property_fact(id, property_id, key, value, source_label, source_url, as_of)
attachment(id, property_id, label, sheet_ref, file_path, uploaded_at)
code_section(id, edition, section_id, title, text, source_url)       -- e.g. "17.90.020"
policy_doc(id, title, text, source_url, as_of)
question(id, property_id, text, status, answer_json, created_at)    -- answer_json holds parts with labels + citations
staff_question(id, question_id, order, context, proposed_reading, code_refs_json, precedent_refs_json)
staff_packet(id, property_id, version, doc_uid, pdf_path, generated_at)
staff_packet_item(packet_id, staff_question_id, q_number)
precedent(id, question_text, answer_text, decision, staff_role, staff_name, answered_on,
          code_refs_json, scope, property_id NULL, status, superseded_by NULL, source_packet_id)
```

## 7. Corpus (primary sources only)

| Source | URL |
| --- | --- |
| Chapter 17, Planning and Land Use (effective 2026-05-20) | https://piedmont.ca.gov/UserFiles/Servers/Server_13659739/File/Government/City%20Charter%20&%20Code/2026/May/Chapter%2017%20%28Effective%202026-05-20%29.pdf |
| Design Review page + linked policies (window replacement, parking/driveway, height calc example, FAR/coverage graphic example, story poles) | https://piedmont.ca.gov/services/permits/planning/types/design-review |
| Design Guidelines | https://piedmont.ca.gov/services___departments/planning___building/about_planning_/design_standards_and_guidelines |
| Projects exempt from planning permits | https://piedmont.ca.gov/services/permits/planning/no-planning-permit-required |
| Design review FAQ | https://piedmont.ca.gov/services/permits/planning/types/design-review/design_review_f_a_q |

Ingestion: parse Chapter 17 into sections keyed by section number (17.20.040, 17.38.xxx, 17.66.060, 17.90.020). Keep the edition on every row. Don't ingest third-party summaries (for example, GoCodebook).

## 8. Test set (seed from 21 Lorita)

Build `evals/lorita.yaml` with question, expected label, expected answer gist, and expected source. The app must pass before any demo.

| # | Question | Expected label | Expected gist |
| --- | --- | --- | --- |
| 1 | Can I replace a window with a same-size double-pane window on the part of the house over the property line? | Code/policy (+ precedent once imported) | Yes, if size, location, operation, recess and lite pattern don't change (Design Guidelines p. 2-11, item 32; staff, 2026-10-26) |
| 2 | Can I put a smaller window in the existing opening there? | Precedent | No; not an in-kind repair (staff, 2026-10-26) |
| 3 | Can I do interior work in the portion over the line? | Precedent | Yes, if the exterior is unaffected (staff, 2026-10-26) |
| 4 | How do I count FAR and lot coverage for a structure crossing the property line? | Precedent | Include the entire footprint and habitable floor area regardless of location (staff, 2026-10-26) |
| 5 | How do I show the side setback where the house crosses the line? | Precedent | A negative value with a note (staff, 2026-10-26) |
| 6 | Can I add an ADU above the existing garage? | Code | Cite Division 17.38 ADU standards (4 ft side/rear setbacks; height limits); verify exact numbers against the text |
| 7 | Can I alter the roof over the portion past the property line? | Precedent | No (staff, 2026-10-20 and 2026-10-28) |
| 8 | Can I convert the garage that crosses the property line into an ADU? | Precedent, **superseded** | 2026-10-29: no → 2026-11-06: "path forward," pending meeting. The app must show both and flag it as unsettled |
| 9 | Can we rebuild the garage shifted fully onto our lot? | Needs staff | Abstain; add to staff questions |
| 10 | Is 21 Lorita in Zone A, and what is the street setback? | Code + property fact | Zone from property record; 20 ft street yard per §17.20.040 (verify against the text) |

Precedent for #2 to #5, #7 and #8 is entered by importing a filled PDF built from the thread. This also tests the import flow end to end.

## 9. Build phases

**Phase 1: Corpus + Ask (week 1–2)**
- Ingest Chapter 17 + policies into sections; build hybrid retrieval.
- Ask endpoint with quote-or-abstain and claim verification.
- Eval runner over `evals/lorita.yaml`, code-only items first.
- Done when: eval items 1, 6 and 10 are answered with correct citations; item 9 abstains.

**Phase 2: Property + staff PDF (week 3–4)**
- Property page with sourced facts, the "Not confirmed by records" box, attachments.
- Staff-question editor; fillable PDF generator per §5.
- Done when: a 21 Lorita packet generates, fills in three viewers, and looks clean when printed.

**Phase 3: Import + precedent (week 5–6)**
- PDF field import, manual fallback, review screen, scope, supersede.
- Retrieval includes precedent with "Staff have said (date)."
- Done when: the full eval passes, including #8's superseded handling.

**Phase 4: Real-world test**
- Use it for the next real 21 Lorita question round. Ask the planner for feedback on the PDF format and iterate.
- Later: county assessor/recorder lookups by address, an FAR/coverage calculator that shows its arithmetic (§17.90 rules), more zones, and shared general precedent if the city agrees.

## 10. Open questions

- Will the planner fill in a PDF digitally, or print and handwrite? This decides how much the manual-entry fallback matters.
- Is the user the homeowner, the architect, or both? Architects may be the heavier users.
- Can general staff rulings be shared with other residents, without names or addresses, if the city agrees?
- Which county data sources can be queried by address without scraping? Check the Alameda County assessor and recorder for terms and APIs before Phase 4.
