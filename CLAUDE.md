# Plinth

Plinth helps Piedmont, CA homeowners check a project against the planning code, then turns open questions into a fillable PDF for city planning staff. Read `PLAN.md` for the product and build plan.

## Knowledge

All city code, policies and staff precedent live in `knowledge/`. See `knowledge/README.md`.

- Start with `knowledge/index/CATALOG.md` to see what exists.
- Search: `python tools/search.py "question" [--json] [--source ch17] [--authority staff]`
- One section: `python tools/search.py section 17.20.040`
- Never answer a code question from memory. Find the section, quote it, and cite it with the file's `cite` field.

## Trust rules (from PLAN.md §3; these apply to code and prompts too)

1. No factual claim without a source quoted from `knowledge/`.
2. Label every answer part: code says / staff have said (dated) / needs staff.
3. If retrieval finds nothing that supports an answer, abstain. Don't guess.
4. Never say "approved" or "you can." Say "the code allows" and quote it.
5. Precedent is not law. Check its `scope` and `status`.

## Commands

- `python tools/ingest.py all`: fetch, extract, split and index every source in `knowledge/sources.yaml`
- `python tools/ingest.py index`: rebuild the search index after editing sections or precedent
- `python tests/test_ingest.py` (or `pytest tests/`): parser tests
