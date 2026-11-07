FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
COPY skills skills
COPY tools/search.py tools/search.py
COPY knowledge/index knowledge/index
COPY knowledge/sections knowledge/sections
COPY knowledge/precedent knowledge/precedent
ENV PORT=8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
