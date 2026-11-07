# Knowledge lake

Everything Plinth knows, as plain files an agent can read, grep or search. Primary city documents only. No third-party summaries.

## Layout

```
knowledge/
  sources.yaml        every source: id, title, kind, authority, effective date, city URL
  raw/<kind>/<id>.pdf the city's original files, unmodified
  raw/MANIFEST.json   sha256, size, date and how each file was obtained
  text/<id>.txt       full extracted text of each file (page breaks are form feeds)
  sections/<id>/      one markdown file per code section (e.g. sections/ch17/17.20.040.md);
                      documents without numbered sections are split one file per page (p001.md)
  precedent/          staff answers, one markdown file each, quoted verbatim
  index/CATALOG.md    table of contents of everything above. Read this first.
  index/chunks.jsonl  search chunks (~300 words) with citation metadata; embedding-ready
```

Every section and precedent file starts with YAML front matter: `id`, `cite`, `authority`, `effective` or `answered_on`, `source_url`, and for precedent `status`, `scope` and `superseded_by`.

## Authority: how much weight a source carries

| authority | what it is | how an answer may use it |
| --- | --- | --- |
| `binding` | City Charter and City Code, as adopted | "The code says…" with the quote |
| `official` | City policies, design guidelines, forms | "City policy says…" with the quote |
| `staff` | A planner's written answer (precedent) | "Staff have said (date)…"; never stated as law. Check `scope` and `status` |

If code and precedent seem to conflict, show both and flag it for staff. Don't pick a winner.

## For agents: how to find things

1. **Know what exists:** read `index/CATALOG.md`.
2. **Search:** `python tools/search.py "your question"`. Add `--json` for structured output, `--source ch17` to stay in the zoning code, or `--authority staff` for precedent only.
3. **Exact section:** `python tools/search.py section 17.90.020` prints the whole section.
4. **Grep works too:** `grep -rn "street yard" knowledge/sections/ch17/`.
5. **Cite** using the file's `cite` field, and quote the text. If nothing supports an answer, say so: that question needs staff.

Superseded precedent is hidden from search unless you pass `--include-superseded`. When you rely on a current record that superseded another, mention the change.

## Adding content

**City documents.** Add an entry to `sources.yaml`, then:

```
python tools/ingest.py all <id>                 # download, extract, split, re-index
python tools/ingest.py add <id> path/to/file.pdf  # when you already have the PDF
python tools/ingest.py index                    # rebuild the index after any change
```

Run `python tools/ingest.py all` with no ids to fetch everything missing. Existing files are skipped unless you pass `--force`. Re-fetch when the city publishes a new edition, and update `effective` in `sources.yaml`.

**Staff answers (precedent).** One file per answer in `precedent/`, named `YYYY-MM-DD-short-topic.md`. Copy the front matter of an existing record. Quote the answer verbatim. When a newer answer replaces an older one, set the old record's `status: superseded` and `superseded_by` to the new id. Never delete it: the history is the point. Then run `python tools/ingest.py index`.

**Later.** Commission decisions and staff reports become a new `kind` with their own folder, following the same pattern. Embeddings can be built from `index/chunks.jsonl` without changing anything upstream.

## Not here, on purpose

- Third-party summaries (GoCodebook and the like), which are not primary sources.
- Raw emails. Precedent records keep only the question, the verbatim answer and context.
