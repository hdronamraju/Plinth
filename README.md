# Project Plinth

Plinth helps Piedmont, CA homeowners and their architects check a project against the planning code before they spend weeks on back-and-forth with the city.

1. **Property facts.** Enter an address; see zone, lot size, recorded easements and permits, each with its source, plus what the records can't confirm.
2. **Cited answers.** Ask "Can I add a window?" and get an answer that quotes the code, cites staff precedent, or honestly says "needs staff."
3. **Staff PDF.** Turn unanswered questions into a clean, fillable PDF for the city planner: numbered questions, code references, a proposed reading, and tick-boxes for her answer.
4. **Precedent.** Upload the filled-in PDF; her answers become dated precedent that future answers can cite.

Plinth never sends email, files permits, or makes permit decisions.

See [PLAN.md](PLAN.md) for the full build plan.

## Repo layout

- `PLAN.md`: product and build plan
- `knowledge/`: the knowledge lake (city code, policies, staff precedent). See `knowledge/README.md`.
- `tools/ingest.py`: fetch city documents and split them into sections; build the index
- `tools/search.py`: search the lake (`python tools/search.py "front setback"`)
- `CLAUDE.md`: instructions for coding agents
