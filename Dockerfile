FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
COPY skills skills
COPY brand brand
COPY tools/search.py tools/search.py
COPY knowledge/index knowledge/index
COPY knowledge/sections knowledge/sections
# Staff precedent (real email thread, names a planner) is deliberately NOT shipped: drop it from the
# search index too, then fail the build if any trace remains. The check looks for the private data itself
# (precedent records, the planners' names), not the plain word "precedent": city code uses it legitimately
# ("a condition precedent to the approval of the final map", Chapter 19).
RUN python - <<'PY'
import json
p = "knowledge/index/chunks.jsonl"
rows = [json.loads(l) for l in open(p)]
keep = [r for r in rows if r.get("kind") != "precedent" and r.get("authority") != "staff"]
open(p, "w").write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in keep))
left = open(p).read().lower()
assert not any(r.get("doc_id", "").startswith("precedent:") for r in keep), "precedent record leaked into image"
assert "carlina" not in left and "matthew mills" not in left, "staff name leaked into image"
print(f"index: kept {len(keep)} of {len(rows)} chunks")
PY
ENV PORT=8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
