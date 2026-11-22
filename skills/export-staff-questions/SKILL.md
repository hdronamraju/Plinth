---
name: export-staff-questions
description: Turn the homeowner's open staff questions into a clean, fillable PDF for Piedmont planning staff. Use when the user asks to export, print, or send open questions to the planner/permit person.
---

# Export open staff questions to PDF

The PDF is what the user takes (outside Plinth) to planning staff. A planner should think
"this is easy to fill out." Plinth never emails anything.

## Steps
1. Call `list_staff_questions`. If empty, say so and offer to add some. Do not invent questions.
2. Curate with the user (briefly, in chat):
   - Merge duplicates; one decision per question; plain language, no legalese.
   - Order from most blocking to least.
   - Each question needs a **proposed reading** that staff can confirm or correct
     ("We read §X as ..., is that right?"). The fastest staff replies come from this pattern.
   - Never write "approved" or "you can". Say "the code says" and quote it.
3. For each question make sure `code_refs` are filled from sections you actually retrieved
   (`get_section`). The export step re-fetches and quotes the text itself. If no section is
   found the PDF says "No section found"; do not paper over that.
   Mention any staff precedent only if it is `current` and its scope fits; give its date.
4. Update questions with `update_staff_question` where needed, then ask for a short project
   description if the property has none.
5. Call `export_staff_pdf` with `project_description` and optional ordered `question_ids`.
6. Tell the user the PDF is ready (the link appears in the UI), that it has fillable fields
   (response, notes, code section), and that they send it themselves.

## PDF rules (enforced by export.py)
Letter size, one sans font, black text plus one accent. Cover: property summary with sources,
project description, how-to-use, index. Question blocks: Context, Code reference, Precedent
found, Our proposed reading, then response radio + notes + section fields. Last page: reviewer
name/title/date and general notes. Footer carries address, doc ID + version, page X of Y,
"Prepared with Plinth. Not an application or permit."
