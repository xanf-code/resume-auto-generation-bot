# --- Stage 1: build the Vite/React frontend -----------------------------
FROM node:22-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
# npm install, not `npm ci` - frontend/package-lock.json is gitignored in
# this repo, so a fresh clone has no lockfile for `ci` to consume.
RUN npm install
COPY frontend/ ./
# Uses vite directly (not `npm run build`/`tsc -b`) - the production bundle
# doesn't need the full-project type-check, which also covers test files.
RUN npx vite build

# --- Stage 2: runtime ------------------------------------------------------
FROM python:3.11-slim-bookworm

# tectonic (statically-linked musl build - no fontconfig/harfbuzz/icu needed)
# and poppler-utils (pdfinfo, used by count_pdf_pages with a manual fallback).
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates poppler-utils \
    && curl -fsSL https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%400.17.0/tectonic-0.17.0-x86_64-unknown-linux-musl.tar.gz \
      | tar -xz -C /usr/local/bin \
    && chmod +x /usr/local/bin/tectonic \
    && apt-get purge -y curl && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config/ ./config/
COPY src/ ./src/
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

ENV RESUMEBOT_HOST=0.0.0.0 \
    RESUMEBOT_PORT=8000

EXPOSE 8000
CMD ["uvicorn", "src.web.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
